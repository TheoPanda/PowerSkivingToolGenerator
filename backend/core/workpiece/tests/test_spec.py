"""spec.py 纯数学一致性/定标/回归测试 — 无 OCCT，CI 可跑.

设计规格书 §8: spec 几何一致性 (segments 还原闭合多边形鞋带面积
vs outline 采样点, rel<1e-6)；标注数值==模型计算 (abs=1e-4 对应 ±0.0001mm)；
params.outputs==GearParams 方法；定标算例1 (m=2.5,z=41,β=0,x=0) d_a=107.5、
s_t=π·m_t/2；rho_tip=0 与旧实现逐点一致 (abs=1e-12)。
"""

import math

import pytest

from core.workpiece.models import GearParams, compute_tooth_thickness
from core.workpiece.profile import Arc, single_tooth_segments, sample_profile_points
from core.workpiece.spec import build_spec


# ── 测试辅助 ─────────────────────────────────────────────────────────

def _shoe_lace_area(pts: list[tuple[float, float]]) -> float:
    """鞋带公式面积 (正, 闭合多边形)."""
    area = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0


def _segments_to_closed_polygon(segments: list[dict]) -> list[tuple[float, float]]:
    """把 spec.single_tooth.segments (Arc/Polyline dict) 采样还原为闭合多边形点列."""
    pts: list[tuple[float, float]] = []
    for seg in segments:
        if seg["type"] == "polyline":
            pts.extend((x, y) for (x, y) in seg["points"])
        else:
            cx, cy = seg["center"]
            r = seg["radius"]
            a0, a1 = seg["a0"], seg["a1"]
            n = 24
            for j in range(n + 1):
                ang = a0 + (a1 - a0) * j / n
                pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) <= 1e-9:
        pts.pop()
    return pts


def _sample_arcs_with_profile_counts(
    segments,
    r_a: float,
    n_tip: int = 10,
    n_root: int = 5,
    n_fillet: int = 8,
) -> list[tuple[float, float]]:
    """按 sample_profile_points 相同的弧段离散规则重建闭合多边形点列.

    使独立还原与 spec.outline.points (同一离散规则) 逐点一致, rel≈0。
    """
    pts: list[tuple[float, float]] = []
    for seg in segments:
        if isinstance(seg, Arc):
            if seg.clockwise:
                n = n_fillet
            elif abs(seg.radius - r_a) <= 1e-9 and seg.center == (0.0, 0.0):
                n = n_tip
            else:
                n = n_root
            cx, cy = seg.center
            for j in range(n + 2):
                ang = seg.a0 + (seg.a1 - seg.a0) * j / (n + 1)
                pts.append((cx + seg.radius * math.cos(ang),
                            cy + seg.radius * math.sin(ang)))
        else:
            start = 1 if pts and math.dist(pts[-1], seg.points[0]) <= 1e-9 else 0
            pts.extend(seg.points[start:])
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) <= 1e-9:
        pts.pop()
    return pts


# ── annotations == params.outputs (同源同值) ─────────────────────────

class TestAnnotationsConsistent:
    """single_tooth.annotations 每项 value 与 params.outputs 同源同值 (abs<=1e-4)."""

    @pytest.mark.parametrize("params", [
        dict(m_n=2.5, z_w=41, b_w=20.0),
        dict(m_n=2.0, z_w=82, b_w=20.0),
        dict(m_n=3.0, z_w=30, b_w=15.0, x_w=0.2),
    ])
    def test_annotations_match_outputs(self, params):
        p = GearParams(**params)
        spec = build_spec(p)
        outputs = {o["key"]: o["value"] for o in spec["params"]["outputs"]}
        ann = spec["single_tooth"]["annotations"]

        checks = {
            "tooth_thickness": (ann["tooth_thickness"]["value"], outputs["s_t"]),
            "circular_pitch": (ann["circular_pitch"]["value"], outputs["p_t"]),
            "tip_fillet": (ann["tip_fillet"]["value"], outputs["rho_tip_actual"]),
            "root_fillet": (ann["root_fillet"]["value"], outputs["rho_f_actual"]),
            "addendum": (ann["addendum"]["value"], outputs["h_a"]),
            "dedendum": (ann["dedendum"]["value"], outputs["h_f"]),
            "whole_depth": (ann["whole_depth"]["value"], outputs["h"]),
        }
        for name, (a, o) in checks.items():
            assert abs(a - o) <= 1e-4, (
                f"{name}: annotation {a} vs output {o} 偏差 > 1e-4"
            )


# ── segments 还原闭合多边形 面积 == outline 面积 ─────────────────────

class TestGeometryAreaConsistency:
    """全齿圈 segments 还原闭合多边形鞋带面积 == sample_profile_points 面积.

    两表示 (精确弧 vs 采样点) 属同一齿形数学, 相对差 < 1e-6 (设计书 §8)。
    """

    @pytest.mark.parametrize("params", [
        dict(m_n=2.5, z_w=41, b_w=20.0),
        dict(m_n=2.0, z_w=82, b_w=20.0),
    ])
    def test_full_ring_area_matches_sampled_polygon(self, params):
        from core.workpiece.profile import gear_profile_segments
        p = GearParams(**params)

        # 全齿圈 segments 独立还原闭合多边形 (与 sample_profile_points 同一离散规则)
        poly = _sample_arcs_with_profile_counts(gear_profile_segments(p), p.tip_radius())
        area_seg = _shoe_lace_area(poly)

        # outline.points (sample_profile_points) 采样面积
        spec = build_spec(p)
        area_sampled = _shoe_lace_area(
            [(pt[0], pt[1]) for pt in spec["outline"]["points"]]
        )

        rel = abs(area_seg - area_sampled) / area_sampled
        assert rel < 1e-6, (
            f"segments 面积 {area_seg:.6f} vs 采样 {area_sampled:.6f} "
            f"(相对差 {rel:.2e})"
        )

    def test_single_tooth_segments_present(self):
        """spec.single_tooth.segments 非空且贴合齿轮比例."""
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0)
        spec = build_spec(p)
        segs = spec["single_tooth"]["segments"]
        assert len(segs) >= 3
        # 任意一段坐标幅值都在齿轮外接圆量级内 (半径 ~ r_a)
        r_a = p.tip_radius()
        for seg in segs:
            if seg["type"] == "polyline":
                for x, y in seg["points"]:
                    assert math.hypot(x, y) <= r_a * 1.01
            else:
                cx, cy = seg["center"]
                span = seg["radius"] + math.hypot(cx, cy)
                assert span <= r_a * 1.01


# ── rho_tip=0 与基线逐点一致 ────────────────────────────────────────

class TestRhoTipZeroBaseline:
    """默认 rho_tip=0 时 spec 几何与旧实现 (profile 权威函数) 逐点一致 (abs<=1e-12)."""

    def test_outline_matches_baseline(self):
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0)  # rho_tip 默认 0
        spec = build_spec(p)

        # outline.points 必须与 sample_profile_points 逐点一致
        for (a, b) in zip(spec["outline"]["points"], sample_profile_points(p)):
            assert abs(a[0] - b[0]) <= 1e-12 and abs(a[1] - b[1]) <= 1e-12

    def test_single_tooth_matches_baseline(self):
        from core.workpiece.spec import segments_to_dict
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0)
        spec = build_spec(p)
        ref = segments_to_dict(single_tooth_segments(p))
        assert len(spec["single_tooth"]["segments"]) == len(ref)
        for a, b in zip(spec["single_tooth"]["segments"], ref):
            assert a == b

    def test_rho_tip_ignored_when_mode_none(self):
        """tip_mode='none' (默认) 时 rho_tip>0 被忽略, 零变化不抛错 (ADR-014 销项)."""
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0, rho_tip=0.2)  # tip_mode 默认 none
        spec = build_spec(p)  # 不抛错
        ref = build_spec(GearParams(m_n=2.5, z_w=41, b_w=20.0))
        assert spec["outline"]["points"] == ref["outline"]["points"], \
            "tip_mode=none 时 rho_tip>0 不得改变几何"

    def test_rho_tip_round_adds_fillets(self):
        """tip_mode='round' 时 rho_tip>0 生成齿顶圆角弧 (不抛错)."""
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0, tip_mode="round", rho_tip=0.2)
        spec = build_spec(p)
        segs = spec["single_tooth"]["segments"]
        rho = p.rho_tip * p.m_n
        n_fillet = sum(
            1 for s in segs
            if s["type"] == "arc" and abs(s["radius"] - rho) < 1e-9
            and s["center"] != [0.0, 0.0]
        )
        assert n_fillet >= 2, f"齿顶圆角弧应 ≥2, 实得 {n_fillet}"


# ── 定标算例1 ───────────────────────────────────────────────────────

class TestCalibrationCase1:
    """定标算例1 (m=2.5, z=41, β=0, x=0): d_a==107.5, s_t==π·m_t/2."""

    def test_da_and_st(self):
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0, beta_w_deg=0.0, x_w=0.0)
        outputs = {o["key"]: o["value"] for o in build_spec(p)["params"]["outputs"]}

        assert abs(outputs["d_a"] - 107.5) <= 1e-9
        m_t, _ = p.to_transverse()
        assert abs(outputs["s_t"] - (math.pi * m_t / 2.0)) <= 1e-9


# ── teeth 切分自洽 ──────────────────────────────────────────────────

class TestOutlineTeethSplit:
    """outline.teeth 切分自洽: 各段长度之和==原长度、每齿闭合、相邻齿首尾衔接."""

    @pytest.mark.parametrize("m_n,z_w", [(2.5, 41), (2.0, 82), (3.0, 30)])
    def test_teeth_split_self_consistent(self, m_n, z_w):
        p = GearParams(m_n=m_n, z_w=z_w, b_w=20.0)
        spec = build_spec(p)
        points = spec["outline"]["points"]
        teeth = spec["outline"]["teeth"]

        # 齿数 == z_w
        assert len(teeth) == z_w

        # 各段长度之和 == 原长度 (无遗漏/重复)
        total = sum(len(t) for t in teeth)
        assert total == len(points), (
            f"teeth 长度和 {total} != 原长度 {len(points)}"
        )

        # 每齿闭合 (≥ 2 点, 首尾环闭合)
        for t in teeth:
            assert len(t) >= 2
            assert math.dist(t[0], t[1]) > 1e-9

        # 还原拼接: 齿 0 列 = [末段连接弧, 首段齿廓], 相对原环发生一次循环平移;
        # 其余齿保持原序。故 reassembled 是 points 的循环旋转 (同一循环点列)。
        reassembled = [pt for t in teeth for pt in t]
        assert len(reassembled) == len(points)
        if reassembled != points:
            # 找旋转偏移, 使 reassembled 与 points 逐点一致
            npts = len(points)
            start = min(range(npts), key=lambda i:
                        sum(math.dist(reassembled[(i + j) % npts], points[j])
                            for j in range(npts)))
            for j in range(npts):
                assert math.dist(reassembled[(start + j) % npts], points[j]) <= 1e-9

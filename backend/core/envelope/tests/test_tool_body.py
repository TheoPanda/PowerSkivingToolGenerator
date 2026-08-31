"""模块③ K-3.2 刀体结构（ADR-021）纯数学测试 — 可入 CI.

断言（规格 docs/specs/2026-08-31-tool-body-design.md 测试决策）：
- 对档规则边界值（向下取档、低于 φ40 钳制）；
- 厚度默认 = 档内标准系列中 ≥L 最小值、全 <L → None；
- 键槽宽随（档×模数段）、键槽深 GB/T 6132 最近档表；
- resolve 软硬分流：硬拒（非系列孔径 / 孔缘含键槽底越谷底圆 / B<L / 键槽无壁），
  软警（厚度非标 → warnings）；
- 双闭环 quad-strip 网格：水密（每条无向边恰被两三角反向共用）、有向体积 > 0 且
  ≈ 解析体积（环形面积+键槽矩形）× 厚度（Cavalieri：直拉伸截面恒定）、键槽笔直
  （前后环对应点差 = (0,0,−B)）、描述包字段。
"""

import math
from collections import Counter

import pytest

from core.envelope.rake import build_plane_rake
from core.envelope.tool_body import (
    ToolBodyResolved,
    build_tool_body,
    default_bore,
    default_keyway_b,
    default_thickness,
    keyway_depth_default,
    resolve_tool_body_params,
    select_segment,
)


def _seg(dia: float) -> dict:
    return select_segment(dia)


def _resolved_bore_keyway(**kw) -> ToolBodyResolved:
    base = dict(mounting="bore_keyway", d_pt=84.9, m_n=2.0, L=16.0, r_root=25.0)
    base.update(kw)
    return resolve_tool_body_params(**base)


# ── 对档规则（Q8）──


class TestSelectSegment:
    def test_downward_tier(self):
        assert _seg(75.0)["dia"] == 75.0
        assert _seg(84.9)["dia"] == 75.0  # 算例1 产形轮 φ84.9 → φ75 档
        assert _seg(74.9)["dia"] == 63.0
        assert _seg(100.0)["dia"] == 100.0
        assert _seg(124.9)["dia"] == 100.0
        assert _seg(201.0)["dia"] == 200.0

    def test_below_smallest_clamps_to_40(self):
        assert _seg(30.8)["dia"] == 40.0  # 算例2 刀具 → φ40 档
        assert _seg(0.1)["dia"] == 40.0

    def test_non_positive_rejected(self):
        with pytest.raises(ValueError, match="> 0"):
            select_segment(0.0)


# ── 表驱动默认值 ──


class TestDefaults:
    def test_default_thickness_min_ge_L(self):
        seg = _seg(75.0)
        assert default_thickness(seg, 4.0) == 15.0
        assert default_thickness(seg, 16.0) == 17.0
        assert default_thickness(seg, 20.0) == 20.0
        assert default_thickness(seg, 21.0) is None  # 全档 <L → 软警口径

    def test_default_keyway_b_by_module(self):
        assert default_keyway_b(_seg(100.0), 1.2) == 10.0
        assert default_keyway_b(_seg(100.0), 2.0) == 12.0
        assert default_keyway_b(_seg(40.0), 0.5) == 6.0
        assert default_keyway_b(_seg(40.0), 1.0) == 7.0
        assert default_keyway_b(_seg(125.0), 5.0) == 13.0

    def test_default_bore_first_of_series(self):
        assert default_bore(_seg(100.0)) == 31.743
        assert default_bore(_seg(160.0)) == 88.9

    def test_keyway_depth_gbt6132(self):
        assert keyway_depth_default(31.743) == 2.8
        assert keyway_depth_default(44.45) == 3.5
        assert keyway_depth_default(88.9) == 5.5
        assert keyway_depth_default(101.6) == 7.0
        assert keyway_depth_default(99.9) is None  # 非系列孔径


# ── resolve：软硬分流（Q10）──


class TestResolve:
    def test_defaults_bore(self):
        r = resolve_tool_body_params(
            mounting="bore", d_pt=84.9, m_n=2.0, L=16.0, r_root=25.0
        )
        assert (r.d_bore, r.keyway_b, r.keyway_t1) == (31.743, None, None)
        assert (r.B, r.segment_dia) == (17.0, 75.0)
        assert r.thickness_is_standard and r.warnings == []

    def test_bore_keyway_full_chain(self):
        r = _resolved_bore_keyway()
        assert r.keyway_b == 10.0  # φ75 档 b=10
        assert r.keyway_t1 == 2.8  # GB/T 6132 d=32 档

    def test_nonstandard_thickness_warns_but_passes(self):
        r = _resolved_bore_keyway(B=19.0)
        assert r.B == 19.0 and not r.thickness_is_standard
        assert len(r.warnings) == 1 and "软警" in r.warnings[0]

    def test_hard_B_below_L(self):
        with pytest.raises(ValueError, match="硬拒"):
            _resolved_bore_keyway(B=15.0, L=16.0)

    def test_hard_nonseries_bore(self):
        with pytest.raises(ValueError, match="标准系列"):
            _resolved_bore_keyway(d_bore=40.0)

    def test_hard_bore_edge_crosses_root(self):
        # φ100 档孔 44.443：r_bore=22.22 ≥ r_root=22 → 硬拒
        with pytest.raises(ValueError, match="越谷底圆"):
            resolve_tool_body_params(
                mounting="bore", d_pt=100.0, m_n=2.0, L=18.0, r_root=22.0,
                d_bore=44.443,
            )

    def test_hard_keyway_bottom_crosses_root(self):
        # φ75 键槽底 r_bore+t1 = 15.8715+2.8 = 18.67 ≥ 18.5 → 硬拒（键槽底判据）
        with pytest.raises(ValueError, match="键槽底越谷底圆"):
            _resolved_bore_keyway(r_root=18.5)

    def test_hard_keyway_no_wall(self):
        with pytest.raises(ValueError, match="无壁"):
            _resolved_bore_keyway(keyway_b=40.0)

    def test_invalid_mounting(self):
        with pytest.raises(ValueError, match="装夹形式"):
            resolve_tool_body_params(
                mounting="flange", d_pt=84.9, m_n=2.0, L=16.0, r_root=25.0
            )


# ── 几何：双闭环 quad-strip ──

_RAKE = build_plane_rake(gamma_deg=5.0, beta_t_deg=0.0, r_pt=42.45)


def _build(**kw):
    base = dict(mounting="bore_keyway", d_pt=84.9, m_n=2.0, L=12.0, B=12.0, r_root=30.0)
    base.update(kw)
    resolved = resolve_tool_body_params(**base)
    return build_tool_body(_RAKE, r_root=30.0, resolved=resolved)


def _edge_stats(indices: list[int]):
    und: Counter = Counter()
    dir_: Counter = Counter()
    for t in range(0, len(indices), 3):
        a, b, c = indices[t], indices[t + 1], indices[t + 2]
        for u, v in ((a, b), (b, c), (c, a)):
            und[tuple(sorted((u, v)))] += 1
            dir_[(u, v)] += 1
    return und, dir_


class TestToolBodyMesh:
    @pytest.fixture()
    def mesh(self):
        spec, desc = _build()
        return spec, desc

    def test_watertight_each_edge_twice_opposite(self, mesh):
        spec, _ = mesh
        und, dir_ = _edge_stats(spec.indices)
        assert und and set(und.values()) == {2}
        for (u, v), cnt in und.items():
            assert cnt == 2
            assert dir_[(u, v)] == 1 and dir_[(v, u)] == 1  # 可定向（绕向一致）

    def test_volume_matches_analytic(self, mesh):
        spec, desc = mesh
        pos, idx = spec.positions, spec.indices
        vol = 0.0
        for t in range(0, len(idx), 3):
            a, b, c = idx[t], idx[t + 1], idx[t + 2]
            ax, ay, az = pos[3 * a], pos[3 * a + 1], pos[3 * a + 2]
            bx, by, bz = pos[3 * b], pos[3 * b + 1], pos[3 * b + 2]
            cx, cy, cz = pos[3 * c], pos[3 * c + 1], pos[3 * c + 2]
            vol += ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)
        vol /= 6.0
        r_root, r_bore, B = 30.0, 31.743 / 2.0, 12.0
        # Cavalieri：直拉伸截面积恒定 → V = (π(R²−r²) − b·t1)·B（键槽矩形从环形扣除；
        # 口部月牙薄楔并入 void，欠 ~0.3% 落入容差）
        analytic = (math.pi * (r_root**2 - r_bore**2) - 10.0 * 2.8) * B
        assert vol > 0
        assert abs(vol - analytic) / analytic < 5e-3  # 圆弦采样欠估 + 薄楔 + 前刀面微斜

    def test_keyway_is_straight(self, mesh):
        spec, _ = mesh
        pos = spec.positions
        n = len(pos) // 3 // 4  # 每环点数
        fi, ri = n, 3 * n  # 前内环 / 后内环
        # 键槽底 = 内环上 x 最大的顶点；前后环对应点应严格差 (0,0,−B)
        j_max = max(range(n), key=lambda j: pos[3 * (fi + j)])
        dx = pos[3 * (ri + j_max)] - pos[3 * (fi + j_max)]
        dy = pos[3 * (ri + j_max) + 1] - pos[3 * (fi + j_max) + 1]
        dz = pos[3 * (ri + j_max) + 2] - pos[3 * (fi + j_max) + 2]
        assert abs(dx) < 1e-12 and abs(dy) < 1e-12 and abs(dz + 12.0) < 1e-9

    def test_description_fields(self, mesh):
        spec, desc = mesh
        assert spec.layer_id == "toolBody"
        assert desc["loop"]["outer_radius"] == 30.0
        assert desc["loop"]["bore_radius"] == pytest.approx(31.743 / 2.0)
        assert desc["loop"]["keyway"] == {"width": 10.0, "depth": 2.8, "polar_deg": 0.0}
        assert desc["extrusion"] == {"axis": [0.0, 0.0, -1.0], "length": 12.0}
        assert desc["boolean_def"]["cut"] == ["bore_cylinder", "keyway_box"]
        assert desc["grade"] == "preview"

    def test_plain_bore_has_no_keyway(self):
        resolved = resolve_tool_body_params(
            mounting="bore", d_pt=84.9, m_n=2.0, L=12.0, r_root=30.0
        )
        spec, desc = build_tool_body(_RAKE, r_root=30.0, resolved=resolved)
        assert desc["loop"]["keyway"] is None
        assert desc["boolean_def"]["cut"] == ["bore_cylinder"]
        und, _ = _edge_stats(spec.indices)
        assert set(und.values()) == {2}

    def test_degenerate_guard_r_root_le_bore(self):
        # 绕过 resolve（其「越谷底圆」硬校验先拦）直接构造，打构建器自身的护栏
        resolved = ToolBodyResolved(
            mounting="bore", d_bore=31.743, keyway_b=None, keyway_t1=None,
            B=12.0, segment_dia=75.0, thickness_is_standard=True, warnings=[],
        )
        with pytest.raises(ValueError, match="≤ 孔半径"):
            build_tool_body(_RAKE, r_root=15.0, resolved=resolved)

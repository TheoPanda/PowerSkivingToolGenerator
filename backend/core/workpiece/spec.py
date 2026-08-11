"""Module ① 齿轮规格呈现窗口 spec 组装 — 纯 Python，无 OCCT.

设计规格书: docs/specs/2026-08-10-gear-spec-presentation-design.md §5.3.

核心约束: spec 只消费 profile.py / models.py 的权威输出，**不做任何二次公式**。
表格数值、单齿廓标注、整体轮廓三者几何由 build_spec(p) 从**同一 GearParams
实例、同一次计算**产出，与 3D GLB 属同一齿形数学。

本模块禁止 import OCCT / OCP，可进 CI。
"""

import math

from core.workpiece import models
from core.workpiece.models import GearParams
from core.workpiece.profile import (
    Arc,
    Polyline,
    Segment,
    single_tooth_segments,
    neighborhood_segments,
    sample_profile_points,
    tip_fillet_actual_mm,
    tip_chamfer_actual_mm,
    root_fillet_actual_mm,
)


# ── Arc / Polyline 序列化 ─────────────────────────────────────────────

def arc_to_dict(arc: Arc) -> dict:
    """Arc → {type, radius, a0, a1, center, clockwise}.

    a0/a1 为 rad，调用方保证已 unwrap 为短弧 (见 profile._cw_unwrap/_ccw_unwrap)。
    clockwise=true → CW 凹角，SVG sweep=0。
    """
    return {
        "type": "arc",
        "radius": arc.radius,
        "a0": arc.a0,
        "a1": arc.a1,
        "center": [arc.center[0], arc.center[1]],
        "clockwise": arc.clockwise,
    }


def polyline_to_dict(pl: Polyline) -> dict:
    """Polyline → {type, points:[[x,y],...]}."""
    return {
        "type": "polyline",
        "points": [[x, y] for (x, y) in pl.points],
    }


def segments_to_dict(segs: list[Segment]) -> list[dict]:
    """段序列序列化 (Arc/Polyline 统一到 JSON 字典)."""
    out: list[dict] = []
    for seg in segs:
        if isinstance(seg, Arc):
            out.append(arc_to_dict(seg))
        else:
            out.append(polyline_to_dict(seg))
    return out


def _shoe_lace_area(pts: list[tuple[float, float]]) -> float:
    """鞋带公式计算多边形有向面积 (正 = CCW). 纯数学，不依赖 OCCT."""
    area = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0


# ── spec.params — 参数规格表 ──────────────────────────────────────────

_ITEM_KEYS = ("key", "label", "symbol", "value", "unit")

INPUT_ITEMS: list[dict] = [
    # (key, label, symbol, 取值函数, unit)
    ("m_n", "法向模数", "m_n", lambda p: p.m_n, "mm"),
    ("z_w", "工件齿数", "z_w", lambda p: float(p.z_w), ""),
    ("alpha_n_deg", "法向压力角", "α_n", lambda p: p.alpha_n_deg, "°"),
    ("beta_w_deg", "螺旋角", "β_w", lambda p: p.beta_w_deg, "°"),
    ("j_w", "旋向", "j_w", lambda p: float(p.j_w), ""),
    ("x_w", "变位系数", "x_w", lambda p: p.x_w, ""),
    ("b_w", "齿宽", "b_w", lambda p: p.b_w, "mm"),
    ("k_io", "内/外齿", "k_io", lambda p: float(p.k_io), ""),
    ("h_an", "齿顶高系数", "h_an*", lambda p: p.h_an, ""),
    ("c_n", "顶隙系数", "c_n*", lambda p: p.c_n, ""),
    ("rho_f", "齿根圆角系数", "ρ*_f", lambda p: p.rho_f, ""),
    ("rho_tip", "齿顶倒圆系数", "ρ*_tip", lambda p: p.rho_tip, ""),
    ("root_fillet", "齿根圆角", "root_fillet", lambda p: p.root_fillet, ""),
    ("tip_mode", "齿顶处理", "tip_mode", lambda p: p.tip_mode, ""),
    ("chamfer_tip", "齿顶倒角系数", "c*_tip", lambda p: p.chamfer_tip, ""),
    ("tooth_method", "齿厚方式", "tooth_method", lambda p: p.tooth_method, ""),
]

OUTPUT_ITEM_SPECS: list[tuple[str, str, str, object, str]] = [
    # (key, label, symbol, 取值 (models 现有方法), unit)
    ("d_pw", "分度圆直径", "d_pw", lambda p: 2.0 * p.pitch_radius(), "mm"),
    ("d_a", "齿顶圆直径", "d_a", lambda p: p.tip_diameter(), "mm"),
    ("d_f", "齿根圆直径", "d_f", lambda p: p.root_diameter(), "mm"),
    ("d_b", "基圆直径", "d_b", lambda p: 2.0 * p.base_radius(), "mm"),
    ("m_t", "端面模数", "m_t", lambda p: p.to_transverse()[0], "mm"),
    ("alpha_t_deg", "端面压力角", "α_t", lambda p: p.to_transverse()[1], "°"),
    ("s_t", "分度圆弧齿厚", "s_t", lambda p: models.compute_tooth_thickness(p), "mm"),
    ("s_n", "法向齿厚", "s_n", lambda p: models.compute_tooth_thickness(p)
        * math.cos(math.radians(p.beta_w_deg)), "mm"),
    ("p_t", "端面齿距", "p_t", lambda p: math.pi * p.to_transverse()[0], "mm"),
    ("h_a", "齿顶高", "h_a", lambda p: p.h_an * p.m_n, "mm"),
    ("h_f", "齿底高", "h_f", lambda p: (p.h_an + p.c_n) * p.m_n, "mm"),
    ("h", "齿全高", "h", lambda p: (p.h_an + p.c_n) * p.m_n + p.h_an * p.m_n, "mm"),
    ("rho_f_actual", "齿根圆角半径", "ρ_f", lambda p: root_fillet_actual_mm(p), "mm"),
    ("rho_tip_actual", "齿顶倒圆半径", "ρ_tip", lambda p: tip_fillet_actual_mm(p), "mm"),
    ("chamfer_actual", "齿顶倒角尺寸", "c*_tip", lambda p: tip_chamfer_actual_mm(p), "mm"),
]


def _item(key: str, label: str, symbol: str, value: float | str | bool, unit: str) -> dict:
    """组装单项 {key, label, symbol, value, unit}."""
    return {"key": key, "label": label, "symbol": symbol, "value": value, "unit": unit}


def params_table(p: GearParams) -> dict:
    """参数规格表 — inputs(约 13 项) + outputs(约 14 项).

    outputs 全部只调用 GearParams/models 现有方法，禁止二次实现公式。
    """
    inputs = [
        _item(key, label, symbol, getter(p), unit)
        for (key, label, symbol, getter, unit) in INPUT_ITEMS
    ]
    outputs = [
        _item(key, label, symbol, getter(p), unit)
        for (key, label, symbol, getter, unit) in OUTPUT_ITEM_SPECS
    ]
    return {"inputs": inputs, "outputs": outputs}


# ── spec.single_tooth — 单齿廓 + 标注 ────────────────────────────────

def single_tooth_spec(p: GearParams) -> dict:
    """单齿廓段序列化 + 中心线/分度线 + 7 项标注.

    annotations 每项 value 与 params.outputs 同源同值 (同一 GearParams 推导)。
    """
    segs = single_tooth_segments(p)
    segments = segments_to_dict(segs)

    # 中心线: 过齿中心 (i=0, 齿中心极角 0) 与原点 — 点划线，端面 -π/2~π/2 示意
    center_line = {"from_angle_deg": -90.0, "to_angle_deg": 90.0}
    # 分度线半径: 点划线
    pitch_line = {"r": p.pitch_radius()}

    s_t = models.compute_tooth_thickness(p)
    p_t = math.pi * p.to_transverse()[0]
    h_a = p.h_an * p.m_n
    h_f = (p.h_an + p.c_n) * p.m_n
    h = h_a + h_f
    rho_tip = tip_fillet_actual_mm(p)
    rho_f = root_fillet_actual_mm(p)  # 开关关/不可构 → 0 (与几何一致)
    # 齿顶标注随 tip_mode: round→实际圆角半径, chamfer→实际倒角尺寸 (C×45°), none→0
    if p.tip_mode == "chamfer":
        tip_ann = {"value": tip_chamfer_actual_mm(p), "label": "齿顶倒角", "symbol": "c*_tip"}
    else:
        tip_ann = {"value": rho_tip, "label": "齿顶圆角", "symbol": "ρ_tip"}

    # 标注：每项只出 value/label/symbol。弧角/半径等定位几何由前端（画图者）推导，
    # 后端不再重复输出——此前序列化的 r/a0_deg/a1_deg/center 前端从未消费（死几何），
    # 且齿厚半角后端用 p_t/2 而前端用 s_t/2，变位齿下两者不一致。见架构审查 C4。
    annotations = {
        "tooth_thickness": {"value": s_t, "label": "齿厚", "symbol": "s_t"},
        "circular_pitch": {"value": p_t, "label": "齿距", "symbol": "p_t"},
        "tip_fillet": tip_ann,
        "root_fillet": {"value": rho_f, "label": "齿根圆角", "symbol": "ρ_f"},
        "addendum": {"value": h_a, "label": "齿顶高", "symbol": "h_a"},
        "dedendum": {"value": h_f, "label": "齿底高", "symbol": "h_f"},
        "whole_depth": {"value": h, "label": "齿全高", "symbol": "h"},
    }

    return {
        "segments": segments,
        "neighborhood": segments_to_dict(neighborhood_segments(p, 3)),
        "center_line": center_line,
        "pitch_line": pitch_line,
        "annotations": annotations,
    }


# ── spec.outline — 整体轮廓 ──────────────────────────────────────────

def _split_teeth_by_phase(
    points: list[tuple[float, float]], z_w: int
) -> list[list[tuple[float, float]]]:
    """按 2π/z_w 相位把连续闭合点列切分为每齿闭合点列 (CCW 遍历序).

    点列由 sample_profile_points 产生: 首尾不重复的简单闭合多边形,
    从第 0 齿左齿根起 CCW 遍历。每齿中心极角 = i·2π/z_w。
    把各点按其极角归属到最近的齿扇区, 因遍历单调递增扇区号,
    相邻同扇区点聚成一段 → 每齿一个连续子列, 顺序与环一致。

    Returns:
        [[(x,y),...], ...] 每齿一个闭合点列 (首尾经环闭合, 不额外补点)。
    """
    pitch = 2.0 * math.pi / z_w
    runs: list[list[tuple[float, float]]] = []
    prev_idx: int | None = None
    for (x, y) in points:
        ang = math.atan2(y, x)
        u = (ang + pitch / 2.0) % (2.0 * math.pi)
        idx = int(u // pitch)
        if idx != prev_idx:
            runs.append([])
            prev_idx = idx
        runs[-1].append((x, y))

    # 环首尾同扇区 (遍历从齿0左齿根起、经全部齿再回到齿0左齿根):
    # 首末 run 同属齿 0, 需按环序合并 (末段连接弧在前, 首段齿廓在后)。
    if len(runs) > 1 and runs[0] and runs[-1]:
        # 判断首末是否同扇区: 以首 run 首点扇区为基准, 末 run 首点扇区==0 即同属齿0
        _x0, _y0 = runs[0][0]
        _u0 = int(((math.atan2(_y0, _x0) + pitch / 2.0) % (2.0 * math.pi)) // pitch)
        _xt, _yt = runs[-1][0]
        _ut = int(((math.atan2(_yt, _xt) + pitch / 2.0) % (2.0 * math.pi)) // pitch)
        if _u0 == _ut:
            # 合并: 齿0 完整列 = 末 run + 首 run
            runs[-1].extend(runs[0])
            runs.pop(0)
    return runs


def outline_spec(p: GearParams) -> dict:
    """整体轮廓: points + teeth (按相位切分) + circles.

    points 为 sample_profile_points(p) 连续闭合点列, 供测试比对;
    teeth 供前端悬停高亮, 每齿闭合点列 [[[x,y],...], ...]。
    """
    pts = sample_profile_points(p)
    teeth = _split_teeth_by_phase(pts, p.z_w)
    circles = {
        "tip_radius": p.tip_radius(),
        "root_radius": p.root_radius(),
        "pitch_radius": p.pitch_radius(),
        "base_radius": p.base_radius(),
    }
    return {
        "points": [[x, y] for (x, y) in pts],
        "teeth": [[[x, y] for (x, y) in run] for run in teeth],
        "circles": circles,
    }


# ── build_spec ───────────────────────────────────────────────────────

def build_spec(p: GearParams) -> dict:
    """从同一 GearParams 组装 spec 字典 {params, single_tooth, outline}."""
    return {
        "params": params_table(p),
        "single_tooth": single_tooth_spec(p),
        "outline": outline_spec(p),
    }

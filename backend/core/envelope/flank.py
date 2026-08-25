"""模块②c 后刀面 — 设计书 K-2.18/2.19 分截面包络 + 三角网连片拟合（纯数学）.

由前刀面刃形 + 各重磨截面刃形按「距前刀面由近及远」顺序三角网连片成后刀面。
重磨同时含两个正交分量（[23] 式(3-1)/(3-2)「重磨使截面沿轴向移动，变位系数线性变化」）：
  - 径向：K-2.18 Δa_i = ΔL_i·tan(α₀)，a_i = a − k_io·Δa_i（内齿轮 +、外齿轮 −，后者推导）。
  - 轴向：前刀面沿 −Z 后退 ΔL_i（const += C·ΔL_i，C=cosγ·cosβ₁；设计书 K-2.19 伪代码
    原遗漏此分量，2026-08-14 补正）。
K-2.19 分截面重跑 K-2.8 离散刃形（轨迹 ∩ 后退后的前刀面）。不依赖 OCCT。
"""

import math
from dataclasses import dataclass, replace

import numpy as np

from core.common.mesh import compute_vertex_normals
from core.envelope.edge import extract_edge
from core.envelope.process_plan import ProcessPlan
from core.envelope.rake import RakeSurface


@dataclass(frozen=True)
class ResharpenStep:
    """一个重磨截面（K-2.18）."""

    i: int
    dL: float   # 累计重磨量 [mm]
    da: float   # 中心距变动量 [mm]
    a_i: float  # 截面中心距 [mm]


def compute_resharpen_schedule(
    a: float,
    L: float,
    n_L: int,
    alpha_0_deg: float,
    k_io: int,
) -> list[ResharpenStep]:
    """K-2.18 重磨截面中心距序列.

    Δa_i = ΔL_i·tan(α₀)，ΔL_i = i·L/n_L；a_i = a − k_io·Δa_i
    （内齿轮 k_io=−1 → a + Δa_i，刀具磨薄中心距增大；外齿轮 k_io=+1 → a − Δa_i，
    推导、文献未发表，T14）。

    Args:
        a: 原始中心距 [mm]
        L: 总重磨量 [mm]
        n_L: 等分数
        alpha_0_deg: 后角 α₀ [°]
        k_io: 内/外齿轮系数 (+1 外 / −1 内)

    Returns:
        [ResharpenStep]（i = 1..n_L）
    """
    if n_L < 1:
        raise ValueError(f"等分数 n_L={n_L} 必须 ≥ 1")
    if L <= 0:
        raise ValueError(f"总重磨量 L={L} 必须 > 0")
    tan_a0 = math.tan(math.radians(alpha_0_deg))
    steps = []
    for i in range(1, n_L + 1):
        dL = i * L / n_L
        da = dL * tan_a0
        a_i = a - k_io * da
        steps.append(ResharpenStep(i=i, dL=dL, da=da, a_i=a_i))
    return steps


def _edge_polylines(profile_pts, plan, rake, *, m, theta_range_deg, k_io, normals=None, b_w: float = 0.0, n_z: int = 21):
    """对给定 plan 跑 K-2.8 刃形（直齿消元 / 斜齿数值求交），返回刃形折线列表."""
    edge = extract_edge(
        profile_pts, plan, rake,
        m=m, theta_range_deg=theta_range_deg, k_io=k_io, normals=normals,
        b_w=b_w, n_z=n_z,
    )
    return [seg.pts for seg in edge.segments]


def _ribbon(poly_a, poly_b):
    """连接两条折线成三角网带（对应点逐点连，取较短者）."""
    n = min(len(poly_a), len(poly_b))
    positions: list[float] = []
    indices: list[int] = []
    for j in range(n - 1):
        a0, a1 = poly_a[j], poly_a[j + 1]
        b0, b1 = poly_b[j], poly_b[j + 1]
        base = len(positions) // 3
        positions += [*a0, *a1, *b0, *b1]
        indices += [base, base + 2, base + 1, base + 1, base + 2, base + 3]
    return positions, indices


@dataclass
class FlankSurface:
    """后刀面（坐标 T）."""

    schedule: list[ResharpenStep]
    mesh_positions: list[float]
    mesh_indices: list[int]
    mesh_normals: list[float]
    lead_pitch: float = 0.0  # 螺旋导程 Ltp [mm]（螺旋导程法有效；重磨集成法为 0）


def generate_flank(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    L: float,
    n_L: int,
    alpha_0_deg: float,
    k_io: int,
    m: int = 181,
    theta_range_deg: float = 40.0,
    normals=None,
) -> FlankSurface:
    """K-2.18/2.19 后刀面生成：前刀面刃形 + 分截面刃形 → 三角网连片.

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]
        plan: ProcessPlan（中心距 a 为原始值）
        rake: RakeSurface（前刀面，刃形 = 前刀面 ∩ 生成面）
        L: 总重磨量 [mm]
        n_L: 等分数
        alpha_0_deg: 后角 α₀ [°]
        k_io: 内/外齿轮系数

    Returns:
        FlankSurface（schedule + 三角网 mesh）
    """
    schedule = compute_resharpen_schedule(plan.a, L, n_L, alpha_0_deg, k_io)
    # 前刀面刃形（a_0 = a，i=0）+ 分截面刃形（a_1..a_nL）
    sections = [_edge_polylines(profile_pts, plan, rake, m=m, theta_range_deg=theta_range_deg, k_io=k_io, normals=normals)]
    if not sections[0]:
        # 外齿轮（k_io=+1）前刀面 p_ref=+r_pt 与节圆切点 −r_pt 相反侧 → 刃形为空（T14）
        raise ValueError("刃形为空（外齿轮前刀面符号 T14 未销项）：请使用内齿轮（k_io=−1）")
    for step in schedule:
        plan_i = replace(plan, a=step.a_i)
        # 轴向分量：前刀面沿 −Z 后退 ΔL_i（const += C·ΔL_i，C=cosγ·cosβ₁）
        rake_i = replace(rake, const=rake.const + rake.C * step.dL)
        section = _edge_polylines(profile_pts, plan_i, rake_i, m=m, theta_range_deg=theta_range_deg, k_io=k_io, normals=normals)
        if not section:
            raise ValueError(
                f"重磨截面 i={step.i} 刃形为空：重磨量 L={L} 使前刀面后退 ΔL={step.dL:.2f}mm "
                f"超出轨迹范围（theta_range={theta_range_deg}°），请减小 L 或增大 theta_range"
            )
        sections.append(section)

    # 三角网连片：连接相邻截面（每条 ribbon 独立）
    n_ribbons = min(len(s) for s in sections)
    positions: list[float] = []
    indices: list[int] = []
    for r in range(n_ribbons):
        for i in range(len(sections) - 1):
            pos, idx = _ribbon(sections[i][r], sections[i + 1][r])
            if pos:
                offset = len(positions) // 3
                positions += pos
                indices += [k + offset for k in idx]
    normals = compute_vertex_normals(positions, indices)
    return FlankSurface(schedule=schedule, mesh_positions=positions, mesh_indices=indices, mesh_normals=normals)

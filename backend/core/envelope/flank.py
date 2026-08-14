"""模块②c 后刀面 — 设计书 K-2.18/2.19 分截面包络 + 三角网连片拟合（纯数学）.

由前刀面刃形 + 各重磨截面刃形按「距前刀面由近及远」顺序三角网连片成后刀面。
K-2.18 Δa_i = ΔL_i·tan(α₀)，a_i = a − k_io·Δa_i（内齿轮 +、外齿轮 −，后者推导）。
K-2.19 分截面重跑 ②b 离散包络。不依赖 OCCT。
"""

import math
from dataclasses import dataclass, replace

import numpy as np

from core.envelope.edge import extract_edge
from core.envelope.process_plan import ProcessPlan
from core.envelope.swept_cloud import generate_envelope_cloud


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


def _edge_polylines(profile_pts, plan, *, m, theta_range_deg, NR):
    """对给定 plan 跑 ②b 离散包络，返回刃形折线列表（upper/lower 各一条）."""
    cloud = generate_envelope_cloud(profile_pts, plan, m=m, theta_range_deg=theta_range_deg)
    edge = extract_edge(cloud.cloud, profile_pts, plan, NR=NR)
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


def _compute_normals(positions, indices):
    """三角网顶点法向（面积加权平均，numpy 向量化）."""
    n_vertices = len(positions) // 3
    if n_vertices == 0:
        return []
    pts = np.array(positions, dtype=np.float64).reshape(-1, 3)
    idx = np.array(indices, dtype=np.int64).reshape(-1, 3)
    v0 = pts[idx[:, 0]]
    v1 = pts[idx[:, 1]]
    v2 = pts[idx[:, 2]]
    face_normals = np.cross(v1 - v0, v2 - v0)
    normals = np.zeros((n_vertices, 3), dtype=np.float64)
    np.add.at(normals, idx[:, 0], face_normals)
    np.add.at(normals, idx[:, 1], face_normals)
    np.add.at(normals, idx[:, 2], face_normals)
    lens = np.linalg.norm(normals, axis=1, keepdims=True)
    lens[lens < 1e-12] = 1.0
    normals = normals / lens
    return normals.reshape(-1).tolist()


@dataclass
class FlankSurface:
    """后刀面（坐标 T）."""

    schedule: list[ResharpenStep]
    mesh_positions: list[float]
    mesh_indices: list[int]
    mesh_normals: list[float]


def generate_flank(
    profile_pts,
    plan: ProcessPlan,
    *,
    L: float,
    n_L: int,
    alpha_0_deg: float,
    k_io: int,
    m: int = 181,
    theta_range_deg: float = 20.0,
    NR: int = 200,
) -> FlankSurface:
    """K-2.18/2.19 后刀面生成：前刀面刃形 + 分截面刃形 → 三角网连片.

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]
        plan: ProcessPlan（中心距 a 为原始值）
        L: 总重磨量 [mm]
        n_L: 等分数
        alpha_0_deg: 后角 α₀ [°]
        k_io: 内/外齿轮系数

    Returns:
        FlankSurface（schedule + 三角网 mesh）
    """
    schedule = compute_resharpen_schedule(plan.a, L, n_L, alpha_0_deg, k_io)
    # 前刀面刃形（a_0 = a，i=0）+ 分截面刃形（a_1..a_nL）
    sections = [_edge_polylines(profile_pts, plan, m=m, theta_range_deg=theta_range_deg, NR=NR)]
    for step in schedule:
        plan_i = replace(plan, a=step.a_i)
        sections.append(_edge_polylines(profile_pts, plan_i, m=m, theta_range_deg=theta_range_deg, NR=NR))

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
    normals = _compute_normals(positions, indices)
    return FlankSurface(schedule=schedule, mesh_positions=positions, mesh_indices=indices, mesh_normals=normals)

"""模块②b 刃形提取 + 覆盖判据 + ffα 复算 — 设计书 K-2.10~K-2.13 纯数学.

由扫掠点云点云投影（K-2.10）→ [25] 径向圆环法内边界提取（K-2.11）得刃形
（左右两条，多段）；覆盖判据（K-2.12）验工件廓形每点对应一个刃形点；
双向包络复算 ffα（K-2.13，简化自证闭环）。不依赖 OCCT。

⚠️ ffα 只证「闭环自洽」非「绝对正确」（正向与反向共享同一变换时，
符号 bug 会互相抵消）——绝对正确性由算例2 矩阵/单点轨迹参考值独立校验。
"""

import math
from dataclasses import dataclass

import numpy as np

from core.common.transforms import (
    apply_transform_batch,
    tool_to_workpiece_chain,
    workpiece_to_tool_chain,
)
from core.envelope.process_plan import ProcessPlan


@dataclass
class EdgeSegment:
    """一段刃形（有序 3D 点列，z≈0 投影刃形）."""

    pts: list[list[float]]  # [[x,y,z], ...] 有序
    continuity: str  # 'continuous' | 'discontinuous'


@dataclass
class EdgeResult:
    """刃形提取结果."""

    segments: list[EdgeSegment]
    coverage_report: dict
    ffa_um: float


def project_to_xy(cloud: np.ndarray) -> np.ndarray:
    """K-2.10 投影 z=0（取 x,y 分量）.

    Args:
        cloud: (..., 3) 点云

    Returns:
        (..., 2) 投影点云
    """
    return cloud[..., :2]


def extract_inner_boundary(
    cloud2d: np.ndarray,
    NR: int = 200,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """K-2.11 [25] 径向圆环法内边界提取.

    以 O_c（刀具轴 = 原点）为圆心设 NR 个均匀半径圆环，每环取距 X_c 轴
    （x 轴）最近两点（y 最接近 0 的两侧点）→ 刃形点。

    Args:
        cloud2d: (N, 2) 投影点云（x, y）
        NR: 径向圆环数

    Returns:
        (upper, lower)：y>0 / y<0 两侧刃形点列，各自按半径递增
    """
    if cloud2d.shape[0] == 0:
        return [], []
    x = cloud2d[:, 0]
    y = cloud2d[:, 1]
    r = np.hypot(x, y)
    r_min, r_max = float(r.min()), float(r.max())
    if r_max - r_min < 1e-12:
        return [], []
    radii = np.linspace(r_min, r_max, NR)
    dr = (r_max - r_min) / (NR - 1)

    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []
    for R in radii:
        band = np.where(np.abs(r - R) <= dr * 0.5)[0]
        if len(band) == 0:
            continue
        bx, by = x[band], y[band]
        pos = by > 0
        neg = by < 0
        if pos.any():
            k = band[pos][np.argmin(by[pos])]  # y>0 侧取 y 最小（最接近 x 轴）
            upper.append((float(x[k]), float(y[k])))
        if neg.any():
            k = band[neg][np.argmax(by[neg])]  # y<0 侧取 y 最大（最接近 x 轴）
            lower.append((float(x[k]), float(y[k])))
    return upper, lower


def compute_coverage(
    profile_pts: list[tuple[float, float]],
    edge_pts: np.ndarray,
    plan: ProcessPlan,
    dr: float,
) -> dict:
    """K-2.12 覆盖判据：工件廓形每点对应一个刃形点.

    工件廓形点经 φ_t=0 变换到刀具系，与刃形点按「半径最近」配对；
    最近径向距离 > dr（环间距）判未覆盖。

    Args:
        profile_pts: 工件廓形点 [(x,y), ...]，n 个
        edge_pts: (M, 2) 刃形点（刀具系投影，合并上下两侧）
        plan: ProcessPlan
        dr: 半径匹配阈值（= NR 环间距）

    Returns:
        coverage_report {total_points, uncovered, coverage_ratio, pass}
    """
    n = len(profile_pts)
    if n == 0:
        return {"total_points": 0, "uncovered": [], "coverage_ratio": 1.0, "pass": True}
    if edge_pts.shape[0] == 0:
        return {
            "total_points": n,
            "uncovered": [{"profile_idx": i, "radius": 0.0} for i in range(n)],
            "coverage_ratio": 0.0,
            "pass": False,
        }

    # 工件廓形 → 刀具系（φ_t=0）
    sigma = math.radians(plan.sigma_deg)
    M = workpiece_to_tool_chain(0.0, 0.0, plan.a, sigma)
    P = np.array([(x, y, 0.0, 1.0) for (x, y) in profile_pts], dtype=np.float64).T
    prof_T = apply_transform_batch(M, P).T  # (n, 3)
    prof_r = np.hypot(prof_T[:, 0], prof_T[:, 1])
    edge_r = np.hypot(edge_pts[:, 0], edge_pts[:, 1])

    uncovered: list[dict] = []
    for i in range(n):
        nearest = float(np.abs(edge_r - prof_r[i]).min())
        if nearest > dr:
            uncovered.append({"profile_idx": i, "radius": float(prof_r[i])})
    coverage_ratio = 1.0 - len(uncovered) / n
    return {
        "total_points": n,
        "uncovered": uncovered,
        "coverage_ratio": coverage_ratio,
        "pass": len(uncovered) == 0,
    }


def forward_envelope_ffa(
    edge_pts: np.ndarray,
    profile_pts: list[tuple[float, float]],
    plan: ProcessPlan,
) -> float:
    """K-2.13 双向包络复算 ffα（简化自证闭环，φ_t=0 静态正向变换）.

    刃形点（内边界 = 工件廓形在刀具系 φ_t=0 的映射）经完整正向链
    `tool_to_workpiece_chain(0, 0, a, Σ)` 变换回工件系，与目标工件廓形逐点
    径向距离取最大 → ffα [μm]。只证「闭环自洽」（正向=反向逆），非「绝对正确」
    （见模块 docstring ⚠️）；完整「扫掠 + 内包络」属模块④ K-4.1 正向包络
    （[21] 步骤(5)），届时复用 `tool_to_workpiece_chain`。

    Args:
        edge_pts: (M, 2) 刃形点（刀具系投影）
        profile_pts: 目标工件廓形点 [(x,y), ...]
        plan: ProcessPlan

    Returns:
        ffα [μm]
    """
    if edge_pts.shape[0] == 0 or len(profile_pts) == 0:
        return float("inf")
    n_edge = edge_pts.shape[0]
    P = np.hstack([edge_pts, np.zeros((n_edge, 1)), np.ones((n_edge, 1))]).T  # (4, M)
    sigma = math.radians(plan.sigma_deg)
    M_fwd = tool_to_workpiece_chain(0.0, 0.0, plan.a, sigma)  # φ_t=0, φ_w=0
    Q = apply_transform_batch(M_fwd, P).T  # (M, 3)
    edge_r = np.hypot(Q[:, 0], Q[:, 1])
    prof_r = np.array([math.hypot(x, y) for (x, y) in profile_pts], dtype=np.float64)
    # 每个工件廓形点找最近刃形点径向距离，取最大
    max_diff = 0.0
    for pr in prof_r:
        d = float(np.abs(edge_r - pr).min())
        if d > max_diff:
            max_diff = d
    return max_diff * 1000.0  # mm → μm


def extract_edge(
    cloud: np.ndarray,
    profile_pts: list[tuple[float, float]],
    plan: ProcessPlan,
    *,
    NR: int = 200,
) -> EdgeResult:
    """K-2.10~2.13 完整刃形提取管线.

    Args:
        cloud: (m, n, 3) 扫掠点云点云（generate_envelope_cloud 输出）
        profile_pts: 工件廓形点
        plan: ProcessPlan
        NR: 径向圆环数

    Returns:
        EdgeResult（segments 左右各一段 + coverage_report + ffα）
    """
    # K-2.10 投影
    cloud2d = project_to_xy(cloud).reshape(-1, 2)  # (m*n, 2)
    # K-2.11 内边界
    upper, lower = extract_inner_boundary(cloud2d, NR)
    # 半径匹配阈值 = NR 环间距
    r_all = np.hypot(cloud2d[:, 0], cloud2d[:, 1])
    dr = (float(r_all.max()) - float(r_all.min())) / (NR - 1) if NR > 1 else 0.0
    # 刃形点合并（上下两侧）
    all_edge = np.array(upper + lower, dtype=np.float64).reshape(-1, 2)
    # K-2.12 覆盖
    coverage = compute_coverage(profile_pts, all_edge, plan, dr)
    # K-2.13 ffα
    ffa_um = forward_envelope_ffa(all_edge, profile_pts, plan)

    # 组装 segments：上/下各一段（z≈0），各段内连续；
    # 段间不连续（齿顶/齿根断开）由「多段结构」本身体现，不在单段标记。
    segments: list[EdgeSegment] = []
    if upper:
        segments.append(EdgeSegment(pts=[[x, y, 0.0] for (x, y) in upper], continuity="continuous"))
    if lower:
        segments.append(EdgeSegment(pts=[[x, y, 0.0] for (x, y) in lower], continuity="continuous"))

    return EdgeResult(segments=segments, coverage_report=coverage, ffa_um=ffa_um)

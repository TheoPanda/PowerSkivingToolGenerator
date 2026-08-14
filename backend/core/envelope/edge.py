"""模块②b 刃形 — 前刀面交线刃形（K-2.8 离散路线）+ 覆盖判据 + ffα 闭环（纯数学）.

刃形 = 前刀面 ∩ 生成面（共轭面）。生成面（K-2.6/2.7）为二期，本模块用 K-2.8
[25] 式(8) 的离散实现：对工件廓形每点，沿其运动轨迹（K-0.5 退化链扫掠的 m 个
采样）找与前刀面 F=0 的交点（线性插值），得**落在前刀面上（z≠0）的 3D 刃形**。

与子 PRD-2 的「z=0 投影内边界」占位不同——本刃形是真实前刀面交线，平滑、含 z
分量；解析路线（analytic.compute_analytic_edge 二分精化）与离散路线（本模块采样）
双路线互检。不依赖 OCCT。

⚠️ 覆盖判据/ffα 只证「闭环自洽」（正向=反向逆）非「绝对正确」——绝对正确性由
双路线互检 + 算例1 输入自洽 + 目检（刃形平滑、只相切）兜底（ADR-019）。
"""

import math
from dataclasses import dataclass

import numpy as np

from core.common.transforms import apply_transform_batch, tool_to_workpiece_chain
from core.envelope.process_plan import ProcessPlan
from core.envelope.rake import RakeSurface
from core.envelope.swept_cloud import generate_envelope_cloud


@dataclass
class EdgeSegment:
    """一段刃形（有序 3D 点列，落在前刀面上）."""

    pts: list[list[float]]  # [[x,y,z], ...] 有序
    continuity: str  # 'continuous' | 'discontinuous'


@dataclass
class EdgeResult:
    """刃形提取结果."""

    segments: list[EdgeSegment]
    coverage_report: dict
    ffa_um: float


def compute_discrete_edge(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    m: int = 181,
    theta_range_deg: float = 20.0,
) -> tuple[list[list[float]], list[float], list[bool]]:
    """K-2.8 离散路线刃形：扫掠采样 + 线性插值求前刀面交点.

    对每个廓形点 j，扫其 m 个运动采样点（扫掠点云 cloud[:, j, :]），找 F 变号区间
    线性插值得前刀面交点。与解析路线（二分精化）是同一数学、不同数值方法，供互检。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]
        plan: ProcessPlan
        rake: RakeSurface（前刀面隐式方程）
        m: 运动离散数（刀具转角采样数）
        theta_range_deg: 刀具转角扫描范围 [°]

    Returns:
        (edge_pts, roots_phi, found)
          - edge_pts[k]: 刃形点 [x, y, z]（落在前刀面上，坐标 T）
          - roots_phi[k]: 对应求交转角 φ_t [rad]
          - found[i]: 廓形点 profile_pts[i] 是否命中（长度 = len(profile_pts)）
    """
    cloud = generate_envelope_cloud(profile_pts, plan, m=m, theta_range_deg=theta_range_deg).cloud
    n = len(profile_pts)
    theta_range = math.radians(theta_range_deg)
    phi_t = np.linspace(-theta_range, theta_range, m)

    edge_pts: list[list[float]] = []
    roots_phi: list[float] = []
    found: list[bool] = []
    for j in range(n):
        col = cloud[:, j, :]  # (m, 3)
        F = rake.A * col[:, 0] + rake.B * col[:, 1] + rake.C * col[:, 2] + rake.const
        hit_pt: np.ndarray | None = None
        hit_rt: float | None = None
        for k in range(m - 1):
            fk, fk1 = F[k], F[k + 1]
            if fk * fk1 <= 0.0:
                denom = fk - fk1
                t = 0.0 if abs(denom) < 1e-15 else fk / denom
                hit_pt = col[k] + t * (col[k + 1] - col[k])
                hit_rt = phi_t[k] + t * (phi_t[k + 1] - phi_t[k])
                break
        if hit_pt is None:
            found.append(False)
        else:
            edge_pts.append([float(hit_pt[0]), float(hit_pt[1]), float(hit_pt[2])])
            roots_phi.append(float(hit_rt))
            found.append(True)
    return edge_pts, roots_phi, found


def split_flank_segments(edge_pts: list[list[float]], closed: bool) -> list[list[list[float]]]:
    """刃形点列 → 左右两段（齿顶/齿根处断开）.

    closed=True（内齿轮闭合齿槽廓形）：在半径极小(齿顶)/极大(齿根)两处断开得两段；
    closed=False（外齿轮开放单齿廓形）：在半径极大(齿顶)处断开得两段。

    Args:
        edge_pts: 刃形点列 [[x, y, z], ...]（按廓形顺序）
        closed: 廓形是否闭合（内齿轮 k_io=−1 为 True）

    Returns:
        [段1, 段2]（各自有序；空输入返回 []）
    """
    n = len(edge_pts)
    if n < 2:
        return [edge_pts] if n else []
    r = [math.hypot(p[0], p[1]) for p in edge_pts]
    imin = min(range(n), key=r.__getitem__)
    imax = max(range(n), key=r.__getitem__)
    if imin == imax:
        return [edge_pts]
    if closed:
        def arc(s: int, e: int) -> list[list[float]]:
            return edge_pts[s:e + 1] if s <= e else edge_pts[s:] + edge_pts[:e + 1]
        return [arc(imin, imax), arc(imax, imin)]
    tip = imax
    return [edge_pts[:tip + 1], edge_pts[tip:]]


def _forward_closure_ffa(
    edge_pts: list[list[float]],
    roots_phi: list[float],
    profile_pts,
    found: list[bool],
    plan: ProcessPlan,
) -> float:
    """ffα 闭环：刃形点经正向链（对应各自 φ_t）反变换，与源廓形点径向偏差取最大 [μm].

    每个刃形点 q 由 q = 工件→刀具链(φ_w=φ_t/ω, φ_t, a, Σ)·p 得到（p 为廓形点），
    故 q 经 tool_to_workpiece_chain(φ_w, φ_t, a, Σ) 应精确回到 p——偏差即变换链
    「正向=反向逆」的数值自洽误差（非刃形绝对正确性，见模块 docstring ⚠️）。
    """
    if not edge_pts:
        # 有限哨兵（μm），避免 Starlette JSONResponse(allow_nan=False) 序列化 inf 崩溃
        return 1e9
    sigma = math.radians(plan.sigma_deg)
    prof_found = [profile_pts[i] for i in range(len(profile_pts)) if found[i]]
    max_d = 0.0
    for pt, root, prof in zip(edge_pts, roots_phi, prof_found):
        phi_w = root / plan.omega_ratio
        M = tool_to_workpiece_chain(phi_w, root, plan.a, sigma)
        q = apply_transform_batch(
            M, np.array([[pt[0]], [pt[1]], [pt[2]], [1.0]], dtype=np.float64)
        )
        d = math.hypot(q[0, 0] - prof[0], q[1, 0] - prof[1])
        if d > max_d:
            max_d = d
    return max_d * 1000.0  # mm → μm


def extract_edge(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    m: int = 181,
    theta_range_deg: float = 20.0,
    k_io: int = 1,
) -> EdgeResult:
    """K-2.8 离散路线完整刃形管线：前刀面交线刃形 + 覆盖 + ffα + 分左右两段.

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]
        plan: ProcessPlan
        rake: RakeSurface（前刀面隐式方程）
        m: 运动离散数
        theta_range_deg: 刀具转角扫描范围 [°]
        k_io: 内/外齿轮系数（决定廓形闭合与否：内齿轮 −1 闭合）

    Returns:
        EdgeResult（segments 左右两段 + coverage_report + ffα）
    """
    edge_pts, roots_phi, found = compute_discrete_edge(
        profile_pts, plan, rake, m=m, theta_range_deg=theta_range_deg
    )
    n = len(profile_pts)
    uncovered = [
        {"profile_idx": i, "radius": math.hypot(profile_pts[i][0], profile_pts[i][1])}
        for i in range(n) if not found[i]
    ]
    coverage = {
        "total_points": n,
        "uncovered": uncovered,
        "coverage_ratio": (n - len(uncovered)) / n if n else 1.0,
        "pass": len(uncovered) == 0,
    }
    ffa_um = _forward_closure_ffa(edge_pts, roots_phi, profile_pts, found, plan)

    segments = [
        EdgeSegment(pts=seg, continuity="continuous")
        for seg in split_flank_segments(edge_pts, closed=(k_io == -1))
    ]
    return EdgeResult(segments=segments, coverage_report=coverage, ffa_um=ffa_um)

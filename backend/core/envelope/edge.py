"""模块②b 刃形 — 产形面（共轭面）∩ 前刀面（Tsai 2023 step 3）+ 覆盖 + ffα（纯数学）.

刃形 = 产形面 ∩ 前刀面（文献 [12] Tsai 2023 图3："tool cutting-edge is intersection
curve of generating surface and rake surface"）。对工件廓形每一离散点 u，联立解：

    g(φ) = v(φ)·n_t(φ) = 0     （啮合方程，接触位；Tsai 式(21)）
    F(P(u, z_w, φ)) = 0         （落在前刀面上）

直齿工件齿面 P(u, z_w, φ) = P0(φ) + z_w·col(φ)（col = ∂P/∂z_w，对 z_w 仿射），
故 g 与 F 均对 z_w 仿射：g = g0 + z_w·gz、F = F0 + z_w·Fz。消去 z_w 得单变量
h(φ) = g0·Fz − F0·gz = 0，求根后闭式回代 z_w* = −F0/Fz、刃形点 = P0(φ*) + z_w*·col(φ*)。

⚠️ 与设计书 K-2.8 的 [25] 式(8)「轨迹穿面法」（z_w=0 钉死、无啮合条件）**不同**——
那是离散包络分支的近似（[25]/[21]，仅复杂齿形二期适用），本模块为共轭法的精确刃形。
正确性由：①刃形点落在产形面上（g=0 且 F=0，构造保证）；②正反闭包 ffα；③双路线互检
（analytic.py 二分精化同一方程）；④算例1 输入自洽 兜底（ADR-019）。
不依赖 OCCT。
"""

import math
from dataclasses import dataclass

import numpy as np

from core.common.transforms import apply_transform_batch, tool_to_workpiece_chain
from core.envelope.meshing import (
    chain_matrices,
    first_sign_change_root,
    profile_normals,
    rotate_normals_batch,
    transform_batch,
    velocity_batch,
)
from core.envelope.process_plan import ProcessPlan
from core.envelope.rake import RakeSurface


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
    theta_range_deg: float = 40.0,
) -> tuple[list[list[float]], list[float], list[bool]]:
    """K-2.8 刃形 = 产形面 ∩ 前刀面：逐点解 g=0 ∧ F=0（消元 → h(φ)=0 求根）.

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]，n 个
        plan: ProcessPlan（Σ/a/同步比）
        rake: RakeSurface（前刀面隐式方程）
        m: 运动离散数（刀具转角采样数）
        theta_range_deg: 刀具转角扫描范围 [°]，±θ_range

    Returns:
        (edge_pts, roots_phi, found)
          - edge_pts[k]: 刃形点 [x, y, z]（落在前刀面上，坐标 T；仅 found 点）
          - roots_phi[k]: 对应接触转角 φ_t [rad]
          - found[i]: 廓形点 profile_pts[i] 是否命中（长度 = len(profile_pts)）
    """
    n = len(profile_pts)
    if n < 2:
        raise ValueError("齿廓点至少 2 个")
    if m < 3:
        raise ValueError("运动离散数 m 至少 3（中心差分 + 线性插值需 ≥3 采样）")

    sigma = math.radians(plan.sigma_deg)
    theta_range = math.radians(theta_range_deg)
    phis = np.linspace(-theta_range, theta_range, m)
    phws = phis / plan.omega_ratio

    xs = np.array([pt[0] for pt in profile_pts], dtype=np.float64)
    ys = np.array([pt[1] for pt in profile_pts], dtype=np.float64)
    norms = profile_normals(profile_pts)
    nxs = np.array([nm[0] for nm in norms], dtype=np.float64)
    nys = np.array([nm[1] for nm in norms], dtype=np.float64)

    Ms = chain_matrices(phis, phws, plan.a, sigma)
    P0 = transform_batch(Ms, xs, ys, np.zeros(n))     # (m, n, 3)
    nt = rotate_normals_batch(Ms, nxs, nys)           # (m, n, 3)
    V0 = velocity_batch(phis, P0)
    g0 = np.sum(V0 * nt, axis=-1)                     # (m, n)

    # gz = col'·n_t，col' = d/dφ(∂P/∂z_w) = (cosφ·sinΣ, −sinφ·sinΣ, 0)
    sinS = math.sin(sigma)
    cosS = math.cos(sigma)
    cosphi = np.cos(phis)[:, None]
    sinphi = np.sin(phis)[:, None]
    gz = cosphi * sinS * nt[..., 0] - sinphi * sinS * nt[..., 1]   # (m, n)

    # F0 = F(P0)；Fz = ∂F/∂z_w = A·sinφ·sinΣ + B·cosφ·sinΣ + C·cosΣ（仅 φ 依赖，(m,1) 列，广播到 (m,n)）
    F0 = rake.A * P0[..., 0] + rake.B * P0[..., 1] + rake.C * P0[..., 2] + rake.const  # (m, n)
    Fz = rake.A * sinphi * sinS + rake.B * cosphi * sinS + rake.C * cosS               # (m, 1)

    # 前刀面与齿面母线近平行（Fz 全程 ≈0）→ 几何退化，h≈0 无变号，显式报错而非静默空刃形
    if float(np.max(np.abs(Fz))) < 1e-6:
        raise ValueError("前刀面与齿面母线近平行（Fz≈0），无唯一刃形，请调整 γ₀/β_t")

    h = g0 * Fz - F0 * gz                             # (m, n)
    phi_root, found, kk, tt = first_sign_change_root(phis, h)

    cols = np.arange(n)
    P0r = P0[kk, cols] + tt[:, None] * (P0[kk + 1, cols] - P0[kk, cols])      # (n, 3)
    F0r = rake.A * P0r[:, 0] + rake.B * P0r[:, 1] + rake.C * P0r[:, 2] + rake.const  # (n,)
    Fzr = rake.A * np.sin(phi_root) * sinS + rake.B * np.cos(phi_root) * sinS + rake.C * cosS  # (n,)

    # 逐点退化（该点 Fz≈0）与无根列一并剔除，再回代（先掩码，避免无根列除零/nan 泄漏）
    degenerate = np.abs(Fzr) < 1e-12
    found = found & ~degenerate
    zw = np.zeros(n)
    zw[found] = -F0r[found] / Fzr[found]

    col = np.stack(
        [np.sin(phi_root) * sinS, np.cos(phi_root) * sinS, np.full(n, cosS)], axis=-1
    )  # (n, 3)
    edge = P0r + zw[:, None] * col                    # (n, 3)

    edge_pts: list[list[float]] = []
    roots_phi: list[float] = []
    found_list: list[bool] = []
    for i in range(n):
        found_list.append(bool(found[i]))
        if found[i]:
            edge_pts.append([float(edge[i, 0]), float(edge[i, 1]), float(edge[i, 2])])
            roots_phi.append(float(phi_root[i]))
    return edge_pts, roots_phi, found_list


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
    """ffα 闭环：刃形点经正向链（对应各自 φ_t）反变换，与源廓形点横向偏差取最大 [μm].

    每个刃形点 q 由 q = 工件→刀具链(φ_w=φ_t/ω, φ_t, a, Σ)·(p; z_w*) 得到（p 为廓形点
    横向分量，z_w* 为接触点轴向层），故 q 经 tool_to_workpiece_chain(φ_w, φ_t, a, Σ)
    应精确回到 (p_x, p_y, z_w*)——横向偏差即变换链「正向=反向逆」的数值自洽误差
    （非刃形绝对正确性，见模块 docstring ⚠️）。绝对正确性由刃形落在产形面（g=0 且
    F=0，构造保证）+ 双路线互检 + 算例1 输入自洽兜底（ADR-019）。
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
    theta_range_deg: float = 40.0,
    k_io: int = 1,
) -> EdgeResult:
    """K-2.8 完整刃形管线：产形面∩前刀面刃形 + 覆盖 + ffα + 分左右两段.

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]
        plan: ProcessPlan
        rake: RakeSurface（前刀面隐式方程）
        m: 运动离散数
        theta_range_deg: 刀具转角扫描范围 [°]
        k_io: 内/外齿轮系数（决定廓形闭合与否：内齿轮 −1 闭合）

    Returns:
        EdgeResult（segments 左右两段 + coverage_report + ffα）

    Raises:
        ValueError: 外齿轮（k_io=+1）未支持——运动链旋向/前刀面符号 T14 未销项
    """
    if k_io != -1:
        raise ValueError(
            "外齿轮（k_io=+1）刃形未支持：运动链旋向/前刀面符号 T14 未销项，请使用内齿轮（k_io=−1）"
        )
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

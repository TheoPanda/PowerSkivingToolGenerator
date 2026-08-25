"""模块②b 解析路线 — K-2.8 刃形（产形面 ∩ 前刀面）+ 双路线互检（纯数学）.

与离散路线（edge.compute_discrete_edge 向量化扫掠 + 线性插值）是**同一共轭数学**
（刃形 = 产形面 ∩ 前刀面，消元方程 h(φ) = g0·Fz − F0·gz = 0，见 edge 推导），
不同数值方法：本模块逐点**二分精化** h(φ)（中心差分速度 + 单列向量变换），与离散
路线互检数值收敛（cross_check）。二者均非 [25] 式(8) 轨迹穿面近似。

K-2.6 产形面（共轭面，conjugate.py）与 K-2.7 啮合方程（n·v=0，meshing.contact_roots）
均已落地。不依赖 OCCT。
"""

import math

import numpy as np

from core.common.transforms import workpiece_to_tool_chain
from core.envelope.edge import inner_contour
from core.envelope.meshing import profile_normals
from core.envelope.process_plan import ProcessPlan
from core.envelope.rake import RakeSurface


def _h(phi_t: float, plan: ProcessPlan, pt, rake: RakeSurface, nrm) -> float:
    """h(φ) = g0·Fz − F0·gz（刃形消元方程，见 edge.compute_discrete_edge 推导）.

    pt = 廓形点 (x, y)（z_w=0 端面）；nrm = 该点 2D 单位法矢。
    """
    sigma = math.radians(plan.sigma_deg)
    phi_w = phi_t / plan.omega_ratio
    M = workpiece_to_tool_chain(phi_w, phi_t, plan.a, sigma)
    p = np.array([pt[0], pt[1], 0.0, 1.0], dtype=np.float64)
    P0 = (M @ p)[:3]
    # 法矢 n_t（3×3 旋转块，NZ=0）
    nt = np.array([
        M[0, 0] * nrm[0] + M[0, 1] * nrm[1],
        M[1, 0] * nrm[0] + M[1, 1] * nrm[1],
        M[2, 0] * nrm[0] + M[2, 1] * nrm[1],
    ])
    # 速度 v0 = dP0/dφ（中心差分）
    eps = 1e-6
    M_plus = workpiece_to_tool_chain((phi_t + eps) / plan.omega_ratio, phi_t + eps, plan.a, sigma)
    M_minus = workpiece_to_tool_chain((phi_t - eps) / plan.omega_ratio, phi_t - eps, plan.a, sigma)
    P_plus = (M_plus @ p)[:3]
    P_minus = (M_minus @ p)[:3]
    V0 = (P_plus - P_minus) / (2 * eps)
    g0 = float(V0 @ nt)
    # gz = col'·n_t，col' = (cosφ·sinΣ, −sinφ·sinΣ, 0)
    sinS = math.sin(sigma)
    cosS = math.cos(sigma)
    gz = math.cos(phi_t) * sinS * nt[0] - math.sin(phi_t) * sinS * nt[1]
    # F0、Fz
    F0 = rake.A * P0[0] + rake.B * P0[1] + rake.C * P0[2] + rake.const
    Fz = rake.A * math.sin(phi_t) * sinS + rake.B * math.cos(phi_t) * sinS + rake.C * cosS
    return g0 * Fz - F0 * gz


def _edge_point(phi_t: float, plan: ProcessPlan, pt, rake: RakeSurface) -> list[float]:
    """由接触转角 φ_t 闭式回代刃形点（z_w* = −F0/Fz，见 edge 推导）."""
    sigma = math.radians(plan.sigma_deg)
    phi_w = phi_t / plan.omega_ratio
    M = workpiece_to_tool_chain(phi_w, phi_t, plan.a, sigma)
    p = np.array([pt[0], pt[1], 0.0, 1.0], dtype=np.float64)
    P0 = (M @ p)[:3]
    sinS = math.sin(sigma)
    cosS = math.cos(sigma)
    F0 = rake.A * P0[0] + rake.B * P0[1] + rake.C * P0[2] + rake.const
    Fz = rake.A * math.sin(phi_t) * sinS + rake.B * math.cos(phi_t) * sinS + rake.C * cosS
    zw = -F0 / Fz
    col = np.array([math.sin(phi_t) * sinS, math.cos(phi_t) * sinS, cosS])
    q = P0 + zw * col
    return [float(q[0]), float(q[1]), float(q[2])]


def _find_roots(
    plan: ProcessPlan,
    pt,
    rake: RakeSurface,
    nrm,
    theta_range: float,
    n_samples: int = 64,
) -> list[float]:
    """在 [−θ_range, +θ_range] 内找 h(φ) **全部**变号根（逐区间二分精化）.

    与离散路线（edge.all_sign_change_roots）同语义：段交界（渐开线↔圆弧尖角）
    附近存在多分支根，必须全收后经 inner_contour 取内侧包络——盲取首根会在
    分支间抖动（刃形折返自交），且会使双路线互检分支不一致。
    零点恰落采样点时相邻区间重复触发 → 按 φ 值去重（差 <1e-12 合并）。
    """
    thetas = np.linspace(-theta_range, theta_range, n_samples)
    hs = np.array([_h(t, plan, pt, rake, nrm) for t in thetas])
    roots: list[float] = []
    for k in range(n_samples - 1):
        if hs[k] * hs[k + 1] > 0.0:
            continue
        lo, hi = thetas[k], thetas[k + 1]
        hlo, hhi = hs[k], hs[k + 1]
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            hm = _h(mid, plan, pt, rake, nrm)
            if hlo * hm <= 0.0:
                hi, hhi = mid, hm
            else:
                lo, hlo = mid, hm
        root = 0.5 * (lo + hi)
        if roots and abs(root - roots[-1]) < 1e-12:
            continue
        roots.append(root)
    return roots


def compute_analytic_edge(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    theta_range_deg: float = 40.0,
    normals=None,
) -> list[list[float]]:
    """K-2.8 解析刃形：逐点二分 h(φ)=0（产形面 ∩ 前刀面消元）→ 前刀面内侧包络环.

    与离散路线（edge.compute_discrete_edge）同构：全根收集（多分支）+
    inner_contour 内侧包络（刀齿材料须在产形面各叶内侧，交叉分支取内侧者），
    仅数值方法不同（逐区间二分 vs 扫掠+线性插值），保证双路线互检分支一致。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]
        plan: ProcessPlan
        rake: RakeSurface（前刀面隐式方程）
        theta_range_deg: 刀具转角扫描范围 [°]

    Returns:
        解析刃形点列 [[x, y, z], ...]（内侧包络环序，落在前刀面上，坐标 T）
    """
    if abs(plan.beta_w_deg) > 1e-12:
        raise ValueError(
            "斜齿工件刃形未支持（K-2.8 消元法依赖齿面对 z_w 仿射，仅直齿成立），请先查看产形面"
        )
    theta_range = math.radians(theta_range_deg)
    norms = normals if normals is not None else profile_normals(profile_pts)
    cand: list[list[float]] = []
    for pt, nrm in zip(profile_pts, norms):
        for root in _find_roots(plan, pt, rake, nrm, theta_range):
            cand.append(_edge_point(root, plan, pt, rake))
    if not cand:
        return []
    keep = inner_contour(np.array(cand, dtype=np.float64), rake)
    return [cand[j] for j in keep]


def cross_check(
    analytic_pts,
    discrete_pts,
    eps_cross_um: float = 1.0,
) -> dict:
    """第5章 §5.5 双路线互检（简化）：解析（二分）vs 离散（扫掠+插值）最近点距离 max|Δ|.

    两法现为**同一共轭刃形**的两种数值实现（非旧版穿面法互检），互检数值收敛性。
    ε_cross=1μm 为推导设定（T1，算例1 实测校准后固化）。两法同为刀具系 T，直接比。
    """
    if not analytic_pts or not discrete_pts:
        # 有限哨兵（μm），避免 Starlette JSONResponse(allow_nan=False) 序列化 inf 崩溃
        return {"max_delta_um": 1e9, "pass": False}
    A = np.array(analytic_pts, dtype=np.float64)
    D = np.array(discrete_pts, dtype=np.float64)
    max_delta = 0.0
    for a in A:
        d = float(np.min(np.linalg.norm(D - a, axis=1)))
        max_delta = max(max_delta, d)
    max_um = max_delta * 1000.0
    return {"max_delta_um": max_um, "pass": max_um < eps_cross_um}

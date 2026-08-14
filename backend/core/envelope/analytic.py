"""模块②b 解析路线 — K-2.8 刃形求交（生成面 ∩ 前刀面）+ 双路线互检（纯数学）.

解析路线：对工件廓形每一离散点，求其运动轨迹（螺旋线族）与前刀面的交点
（K-2.8，[25] 式(8)），得解析刃形（二分精化）——与离散刃形（edge.compute_discrete_edge
扫掠采样 + 线性插值）是同一数学、两种数值方法，双路线互检。k_io 无关
（研究 docs/research/外齿轮解析路线.md）。

K-2.6 生成面（共轭面）+ K-2.7 啮合方程（n·v¹²=0）本子 PRD 先 skeleton 占位
（二期补全，缺口纪律）。不依赖 OCCT。
"""

import math

import numpy as np

from core.common.transforms import workpiece_to_tool_chain
from core.envelope.process_plan import ProcessPlan
from core.envelope.rake import RakeSurface


def _trajectory(phi_t: float, plan: ProcessPlan, pt: tuple[float, float]) -> np.ndarray:
    """廓形点在刀具转角 φ_t 时的刀具系坐标（螺旋线族轨迹，K-0.5 退化链）."""
    phi_w = phi_t / plan.omega_ratio  # φ_w = φ_t·z_t/z_w
    M = workpiece_to_tool_chain(phi_w, phi_t, plan.a, math.radians(plan.sigma_deg))
    p = np.array([pt[0], pt[1], 0.0, 1.0], dtype=np.float64)
    return M @ p


def _g(phi_t: float, plan: ProcessPlan, pt: tuple[float, float], rake: RakeSurface) -> float:
    """g(θ) = F(轨迹(θ))：轨迹点代入前刀面方程 A·x+B·y+C·z+const."""
    q = _trajectory(phi_t, plan, pt)
    return rake.A * q[0] + rake.B * q[1] + rake.C * q[2] + rake.const


def _find_root(
    plan: ProcessPlan,
    pt: tuple[float, float],
    rake: RakeSurface,
    theta_range: float,
    n_samples: int = 64,
) -> float | None:
    """在 [−θ_range, +θ_range] 内找 g(θ) 变号根（二分精化，等价 Newton 二分回退）."""
    thetas = np.linspace(-theta_range, theta_range, n_samples)
    gs = np.array([_g(t, plan, pt, rake) for t in thetas])
    for k in range(n_samples - 1):
        if gs[k] * gs[k + 1] <= 0.0:
            lo, hi = thetas[k], thetas[k + 1]
            glo, ghi = gs[k], gs[k + 1]
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                gm = _g(mid, plan, pt, rake)
                if glo * gm <= 0.0:
                    hi, ghi = mid, gm
                else:
                    lo, glo = mid, gm
            return 0.5 * (lo + hi)
    return None


def compute_analytic_edge(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    theta_range_deg: float = 20.0,
) -> list[list[float]]:
    """K-2.8 解析刃形：逐点求轨迹 ∩ 前刀面交点.

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]
        plan: ProcessPlan
        rake: RakeSurface（前刀面隐式方程）
        theta_range_deg: 刀具转角扫描范围 [°]

    Returns:
        解析刃形点列 [[x, y, z], ...]（落在前刀面上，坐标 T）
    """
    theta_range = math.radians(theta_range_deg)
    edge_pts: list[list[float]] = []
    for (x, y) in profile_pts:
        root = _find_root(plan, (x, y), rake, theta_range)
        if root is not None:
            q = _trajectory(root, plan, (x, y))
            edge_pts.append([float(q[0]), float(q[1]), float(q[2])])
    return edge_pts


def cross_check(
    analytic_pts,
    discrete_pts,
    eps_cross_um: float = 1.0,
) -> dict:
    """第5章 §5.5 双路线互检（简化）：解析 vs 离散刃形最近点距离 max|Δ|.

    ⚠️ 简化版：以「解析点集到离散点集的最小欧氏距离」近似「对应弧长位置法向距离」，
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


def generate_conjugate_surface(*args, **kwargs):
    """K-2.6 生成面（共轭面 = 产形面）— ⚠️ 二期骨架占位（缺口纪律，W10/W11/W12 回读后补）."""
    raise NotImplementedError("K-2.6 生成面（共轭面）二期实现，本子 PRD 骨架占位")


def meshing_equation(*args, **kwargs):
    """K-2.7 啮合方程 n·v¹²=0 — ⚠️ 二期骨架占位（缺口纪律）."""
    raise NotImplementedError("K-2.7 啮合方程二期实现，本子 PRD 骨架占位")

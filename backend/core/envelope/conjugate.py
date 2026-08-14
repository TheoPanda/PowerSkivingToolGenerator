"""模块②b 产形面（共轭面）— 设计书 K-2.6 离散数值啮合路线（纯数学）.

产形面 = 工件齿面经反向包络在刀具侧生成的共轭曲面（坐标 T），即 [12] 图3
蓝色面、设计书 §3.4「共轭面（产形面）」契约输出。与扫掠点云（中间媒介、桶形
失真）不同——产形面是严格意义的刀具理论齿面。

解法（A 数值啮合方程路线，2026-08-14 落地）：对工件齿面每一点 P（含法矢 n），
沿刀具转角 φ_t 扫掠得轨迹 P(φ_t)，啮合方程（[12] 式21 等价形式）

    g(φ_t) = v(φ_t) · n_t(φ_t) = 0

（v = dP/dφ_t 轨迹速度，n_t = 旋转后法矢）的第一个根 φ_t* 即接触位，
P(φ_t*) 为产形面点。法矢取反不改根（方程对 n 齐次），故廓形法矢朝向无碍。

实现为全向量化逐元素展开（避开 numpy 2.5.0 + Python 3.14 的方阵乘法崩溃，
与 transforms.apply_transform_batch 同一手动展开策略）。不依赖 OCCT。
"""

import math
from dataclasses import dataclass

import numpy as np

from core.common.transforms import workpiece_to_tool_chain
from core.envelope.process_plan import ProcessPlan
from core.envelope.swept_cloud import _compute_vertex_normals


@dataclass
class ConjugateSurface:
    """产形面（坐标 T）."""

    mesh_positions: list[float]  # 三角网扁平顶点 [x0,y0,z0, ...]
    mesh_indices: list[int]      # 三角网索引
    mesh_normals: list[float]    # 顶点法向（面积加权面法向平均，与 positions 等长）
    coverage: dict               # {total_points, found, uncovered, coverage_ratio, pass}


def _profile_normals(profile_pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """2D 廓形法矢（切向中心差分旋转 +90°），返回单位法矢 [(nx, ny), ...].

    啮合方程对法矢齐次（取反不改根），故朝向仅作几何一致性约定，不影响接触位。
    """
    n = len(profile_pts)
    out: list[tuple[float, float]] = []
    for i in range(n):
        p0 = profile_pts[(i - 1) % n]
        p1 = profile_pts[(i + 1) % n]
        tx = p1[0] - p0[0]
        ty = p1[1] - p0[1]
        L = math.hypot(tx, ty)
        if L < 1e-12:
            out.append((0.0, 0.0))
        else:
            out.append((-ty / L, tx / L))
    return out


def compute_conjugate_surface(
    profile_pts: list[tuple[float, float]],
    plan: ProcessPlan,
    *,
    b_w: float,
    k_io: int,
    n_z: int = 21,
    m: int = 181,
    theta_range_deg: float = 40.0,
) -> ConjugateSurface:
    """K-2.6 离散数值啮合产形面：齿面网格 × 啮合方程求根 → 三角网.

    齿面网格 = n 个廓形点 × n_z 个轴向层（z ∈ [−b_w/2, b_w/2]）；每点沿 φ_t
    扫掠求啮合根，得 (n_z × n) 产形面点网格，三角网连片（内齿轮闭合廓形沿
    廓形向回绕）。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]，n 个
        plan: ProcessPlan（Σ/a/同步比）
        b_w: 工件齿宽 [mm]（产形面轴向展布）
        k_io: 内/外齿轮系数（−1 内齿轮闭合廓形 → 三角网回绕）
        n_z: 轴向层数
        m: 刀具转角采样数
        theta_range_deg: 刀具转角扫描范围 [°]，±θ_range

    Returns:
        ConjugateSurface（坐标 T）

    Raises:
        ValueError: 廓形点 < 2 / m < 2 / n_z < 2 / b_w ≤ 0
    """
    n = len(profile_pts)
    if n < 2:
        raise ValueError("齿廓点至少 2 个")
    if m < 2:
        raise ValueError("运动离散数 m 至少 2")
    if n_z < 2:
        raise ValueError("轴向层数 n_z 至少 2")
    if b_w <= 0:
        raise ValueError(f"齿宽 b_w={b_w} 必须 > 0")

    norms = _profile_normals(profile_pts)

    # 齿面网格：行主序 index = iz·n + iu（n_z 行 × n 列）
    xs = np.array([pt[0] for pt in profile_pts], dtype=np.float64)
    ys = np.array([pt[1] for pt in profile_pts], dtype=np.float64)
    nxs = np.array([nm[0] for nm in norms], dtype=np.float64)
    nys = np.array([nm[1] for nm in norms], dtype=np.float64)
    zs = np.linspace(-b_w / 2.0, b_w / 2.0, n_z)
    X = np.tile(xs, n_z)
    Y = np.tile(ys, n_z)
    Z = np.repeat(zs, n)
    NX = np.tile(nxs, n_z)
    NY = np.tile(nys, n_z)
    N = n * n_z

    # 预计算 m 个 K-0.5 链矩阵（φ_w = φ_t / omega_ratio，同步 K-1.7）
    theta_range = math.radians(theta_range_deg)
    phis = np.linspace(-theta_range, theta_range, m)
    phws = phis / plan.omega_ratio
    sigma = math.radians(plan.sigma_deg)
    Ms = np.stack([
        workpiece_to_tool_chain(phws[j], phis[j], plan.a, sigma) for j in range(m)
    ])  # (m, 4, 4)

    # 逐元素展开变换 P(φ_t)（避开方阵乘法崩溃）
    Px = Ms[:, 0, 0][:, None] * X[None, :] + Ms[:, 0, 1][:, None] * Y[None, :] + Ms[:, 0, 2][:, None] * Z[None, :] + Ms[:, 0, 3][:, None]
    Py = Ms[:, 1, 0][:, None] * X[None, :] + Ms[:, 1, 1][:, None] * Y[None, :] + Ms[:, 1, 2][:, None] * Z[None, :] + Ms[:, 1, 3][:, None]
    Pz = Ms[:, 2, 0][:, None] * X[None, :] + Ms[:, 2, 1][:, None] * Y[None, :] + Ms[:, 2, 2][:, None] * Z[None, :] + Ms[:, 2, 3][:, None]

    # 轨迹速度 v = dP/dφ_t（中心差分，端点单侧）
    dphi = phis[1] - phis[0]
    Vx = np.empty_like(Px)
    Vy = np.empty_like(Py)
    Vz = np.empty_like(Pz)
    Vx[1:-1] = (Px[2:] - Px[:-2]) / (2 * dphi)
    Vy[1:-1] = (Py[2:] - Py[:-2]) / (2 * dphi)
    Vz[1:-1] = (Pz[2:] - Pz[:-2]) / (2 * dphi)
    Vx[0] = (Px[1] - Px[0]) / dphi
    Vy[0] = (Py[1] - Py[0]) / dphi
    Vz[0] = (Pz[1] - Pz[0]) / dphi
    Vx[-1] = (Px[-1] - Px[-2]) / dphi
    Vy[-1] = (Py[-1] - Py[-2]) / dphi
    Vz[-1] = (Pz[-1] - Pz[-2]) / dphi

    # 旋转法矢 n_t（NZ=0，逐元素）
    Ntx = Ms[:, 0, 0][:, None] * NX[None, :] + Ms[:, 0, 1][:, None] * NY[None, :]
    Nty = Ms[:, 1, 0][:, None] * NX[None, :] + Ms[:, 1, 1][:, None] * NY[None, :]
    Ntz = Ms[:, 2, 0][:, None] * NX[None, :] + Ms[:, 2, 1][:, None] * NY[None, :]

    # 啮合方程 g(φ_t) = v·n_t，找首个变号 → 线性插值根
    g = Vx * Ntx + Vy * Nty + Vz * Ntz  # (m, N)
    sc = g[:-1] * g[1:] <= 0.0          # (m-1, N)
    found = sc.any(axis=0)              # (N,)
    kk = sc.argmax(axis=0)              # (N,) 首个变号行
    cols = np.arange(N)
    gk = g[kk, cols]
    gk1 = g[kk + 1, cols]
    denom = gk - gk1
    tt = np.where(np.abs(denom) < 1e-15, 0.0, gk / denom)

    pts_x = Px[kk, cols] + tt * (Px[kk + 1, cols] - Px[kk, cols])
    pts_y = Py[kk, cols] + tt * (Py[kk + 1, cols] - Py[kk, cols])
    pts_z = Pz[kk, cols] + tt * (Pz[kk + 1, cols] - Pz[kk, cols])

    n_found = int(found.sum())
    coverage = {
        "total_points": N,
        "found": n_found,
        "uncovered": N - n_found,
        "coverage_ratio": n_found / N if N else 1.0,
        "pass": n_found == N,
    }

    # 三角网连片（仅四角全命中的单元；内齿轮闭合廓形沿廓形向回绕）
    closed = (k_io == -1)
    positions: list[float] = []
    for v in range(N):
        positions += [pts_x[v], pts_y[v], pts_z[v]]
    indices: list[int] = []
    iu_count = n if closed else n - 1
    for iz in range(n_z - 1):
        for iu in range(iu_count):
            iu2 = (iu + 1) % n
            a = iz * n + iu
            b = iz * n + iu2
            c = a + n
            d = iz * n + iu2 + n
            if found[a] and found[b] and found[c] and found[d]:
                indices += [a, c, b, b, c, d]

    normals = _compute_vertex_normals(positions, indices)
    return ConjugateSurface(
        mesh_positions=positions,
        mesh_indices=indices,
        mesh_normals=normals,
        coverage=coverage,
    )

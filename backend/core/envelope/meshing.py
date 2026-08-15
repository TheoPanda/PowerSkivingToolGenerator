"""模块② 共轭啮合数值核心 — 共享向量化工具（纯数学，无 OCCT）.

集中 K-0.5 运动链批量变换、法矢旋转、轨迹速度、啮合方程求根，供
conjugate.py（产形面，K-2.6 数值）与 edge.py（刃形 = 产形面 ∩ 前刀面，K-2.8）
复用，消除逐元素展开的重复实现。

遵循 numpy 2.5.0 + Python 3.14 方阵乘法崩溃规避纪律（见 core.common.transforms）：
4×4 链矩阵用 workpiece_to_tool_chain（内部 _mat4_compose 纯 Python 连乘），
批量点应用用本模块逐元素展开，禁用 4×4 @ 4×4 / 4×4 @ (4,N) 的 numpy matmul。
"""

import math

import numpy as np

from core.common.transforms import workpiece_to_tool_chain


def profile_normals(profile_pts: list) -> list:
    """2D 廓形法矢（切向中心差分旋转 +90°），返回单位法矢 [(nx, ny), ...].

    啮合方程对法矢齐次（取反不改根），故朝向仅作几何一致性约定，不影响接触位。
    """
    n = len(profile_pts)
    out: list = []
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


def chain_matrices(phis: np.ndarray, phws: np.ndarray, a: float, sigma: float) -> np.ndarray:
    """预计算 m 个 K-0.5 链矩阵 → (m, 4, 4).

    φ_w 已按 K-1.7 同步（调用方传入 phws = phis / omega_ratio）。
    """
    return np.stack([
        workpiece_to_tool_chain(phws[j], phis[j], a, sigma) for j in range(len(phis))
    ])


def transform_batch(Ms: np.ndarray, X: np.ndarray, Y: np.ndarray, Z: np.ndarray) -> np.ndarray:
    """(m,4,4) 链矩阵批量应用到点集 (X,Y,Z)(N,) → (m,N,3)，逐元素展开."""
    Px = (Ms[:, 0, 0][:, None] * X[None, :] + Ms[:, 0, 1][:, None] * Y[None, :]
          + Ms[:, 0, 2][:, None] * Z[None, :] + Ms[:, 0, 3][:, None])
    Py = (Ms[:, 1, 0][:, None] * X[None, :] + Ms[:, 1, 1][:, None] * Y[None, :]
          + Ms[:, 1, 2][:, None] * Z[None, :] + Ms[:, 1, 3][:, None])
    Pz = (Ms[:, 2, 0][:, None] * X[None, :] + Ms[:, 2, 1][:, None] * Y[None, :]
          + Ms[:, 2, 2][:, None] * Z[None, :] + Ms[:, 2, 3][:, None])
    return np.stack([Px, Py, Pz], axis=-1)


def rotate_normals_batch(Ms: np.ndarray, NX: np.ndarray, NY: np.ndarray) -> np.ndarray:
    """旋转 2D 廓形法矢（NZ=0）→ (m,N,3)，只用链 3×3 旋转块（K-0.7）."""
    Ntx = Ms[:, 0, 0][:, None] * NX[None, :] + Ms[:, 0, 1][:, None] * NY[None, :]
    Nty = Ms[:, 1, 0][:, None] * NX[None, :] + Ms[:, 1, 1][:, None] * NY[None, :]
    Ntz = Ms[:, 2, 0][:, None] * NX[None, :] + Ms[:, 2, 1][:, None] * NY[None, :]
    return np.stack([Ntx, Nty, Ntz], axis=-1)


def velocity_batch(phis: np.ndarray, P: np.ndarray) -> np.ndarray:
    """轨迹速度 v = dP/dφ_t（中心差分，端点单侧）→ (m,N,3)."""
    dphi = phis[1] - phis[0]
    V = np.empty_like(P)
    V[1:-1] = (P[2:] - P[:-2]) / (2 * dphi)
    V[0] = (P[1] - P[0]) / dphi
    V[-1] = (P[-1] - P[-2]) / dphi
    return V


def first_sign_change_root(phis: np.ndarray, g: np.ndarray):
    """对 (m,N) 标量场 g 逐列求**首个变号根**（线性插值）.

    Returns:
        phi_root (N,), found (N,bool), kk (N,int), tt (N,float)
        其中 root = phis[kk] + tt·(phis[kk+1]−phis[kk])。
    """
    sc = g[:-1] * g[1:] <= 0.0
    found = sc.any(axis=0)
    kk = sc.argmax(axis=0)
    cols = np.arange(g.shape[1])
    gk = g[kk, cols]
    gk1 = g[kk + 1, cols]
    denom = gk - gk1
    tt = np.where(np.abs(denom) < 1e-15, 0.0, gk / denom)
    phi_root = phis[kk] + tt * (phis[kk + 1] - phis[kk])
    return phi_root, found, kk, tt


def contact_roots(phis: np.ndarray, P: np.ndarray, nt: np.ndarray):
    """啮合方程 g = v·n_t = 0 的首个变号根（Tsai 2023 式(21) 等价形式）.

    法矢取反不改根（方程对 n 齐次），故廓形法矢朝向无碍。
    """
    V = velocity_batch(phis, P)
    g = np.sum(V * nt, axis=-1)
    phi_root, found, kk, tt = first_sign_change_root(phis, g)
    return phi_root, found, kk, tt

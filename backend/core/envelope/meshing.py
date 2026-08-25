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


def rotate_normals_batch_3d(Ms: np.ndarray, NX: np.ndarray, NY: np.ndarray, NZ: np.ndarray) -> np.ndarray:
    """旋转 3D 法矢（含 NZ）→ (m,N,3)，用链矩阵完整 3×3 旋转块（K-0.7）.

    斜齿轮齿面法矢含 z 分量，须用 3×3 块全部 9 个元素（链矩阵旋转部分正交，
    无缩放，直接线性变换即为正确法矢）。
    """
    Ntx = (Ms[:, 0, 0][:, None] * NX[None, :] + Ms[:, 0, 1][:, None] * NY[None, :]
           + Ms[:, 0, 2][:, None] * NZ[None, :])
    Nty = (Ms[:, 1, 0][:, None] * NX[None, :] + Ms[:, 1, 1][:, None] * NY[None, :]
           + Ms[:, 1, 2][:, None] * NZ[None, :])
    Ntz = (Ms[:, 2, 0][:, None] * NX[None, :] + Ms[:, 2, 1][:, None] * NY[None, :]
           + Ms[:, 2, 2][:, None] * NZ[None, :])
    return np.stack([Ntx, Nty, Ntz], axis=-1)


def helical_tooth_grid(
    profile_pts: list,
    normals: list,
    zs: np.ndarray,
    j_w: int,
    beta_w: float,
    r_pw: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """K-0.6 斜齿轮齿面网格 + 3D 单位法矢（β_w=0 退化为直齿拉伸）.

    端面齿槽廓形点 (x,y) 与端面单位法矢 (n_x,n_y) 沿 z 层绕 z 轴扭转
    θ(z) = j_w·z·tan(β_w)/r_pw（K-0.6 逆解：z = j_w·θ·r_pw/tanβ_w），得螺旋面网格
    （n_z·n 点，行主序 index = iz·n + iu）与 3D 单位法矢（含螺旋 z 分量
    nz = −j_w·(x·n_y − y·n_x)·tanβ_w/r_pw，其中 x·n_y − y·n_x = r·t̂ 为旋转不变量）。

    法矢方向取反不改啮合方程根（g = v·n 对 n 齐次）；nz 与 (nx,ny) 由同一 t̂ 耦合，
    遍历方向反转时整体翻号，不产生伪根。

    Args:
        profile_pts: 端面齿廓点 [(x, y), ...]，n 个
        normals: 端面单位法矢 [(n_x, n_y), ...]，n 个（extract_gap_points / profile_normals）
        zs: 轴向层坐标 (n_z,)
        j_w: 工件旋向系数 (+1 右旋 / −1 左旋，U7)
        beta_w: 工件螺旋角 [rad]
        r_pw: 工件节圆半径 [mm]

    Returns:
        (X, Y, Z, NX, NY, NZ) 各为 (n_z·n,) 数组
    """
    n = len(profile_pts)
    n_z = len(zs)
    xs = np.array([pt[0] for pt in profile_pts], dtype=np.float64)
    ys = np.array([pt[1] for pt in profile_pts], dtype=np.float64)
    nxs = np.array([nm[0] for nm in normals], dtype=np.float64)
    nys = np.array([nm[1] for nm in normals], dtype=np.float64)

    Z = np.repeat(np.asarray(zs, dtype=np.float64), n)

    if abs(beta_w) < 1e-15:
        # 直齿退化：θ=0，NZ=0（零回归，与旧「tile/repeat 拉伸」等价）
        X = np.tile(xs, n_z)
        Y = np.tile(ys, n_z)
        NX = np.tile(nxs, n_z)
        NY = np.tile(nys, n_z)
        NZ = np.zeros_like(X)
        return X, Y, Z, NX, NY, NZ

    # 螺旋 z 分量（与 z 层无关，每廓形点一个）
    tan_bw = math.tan(beta_w)
    nz_pt = -j_w * (xs * nys - ys * nxs) * tan_bw / r_pw  # (n,)

    # 每层扭转角 θ(iz)（(n_z,)）
    thetas = j_w * np.asarray(zs, dtype=np.float64) * tan_bw / r_pw
    ct = np.cos(thetas)
    st = np.sin(thetas)

    # 齿面点：X = x·cosθ − y·sinθ，Y = x·sinθ + y·cosθ（外积 (n_z,n) → ravel）
    X = (ct[:, None] * xs[None, :] - st[:, None] * ys[None, :]).ravel()
    Y = (st[:, None] * xs[None, :] + ct[:, None] * ys[None, :]).ravel()

    # 法矢 xy 分量同向扭转，z 分量逐廓形点复制到各层
    NX_rot = (ct[:, None] * nxs[None, :] - st[:, None] * nys[None, :]).ravel()
    NY_rot = (st[:, None] * nxs[None, :] + ct[:, None] * nys[None, :]).ravel()
    NZ_rot = np.tile(nz_pt, n_z)

    # 单位化：|(NX_rot, NY_rot)| = |(n_x, n_y)| = 1，故 norm = sqrt(1 + NZ²)
    norm = np.sqrt(1.0 + NZ_rot * NZ_rot)
    return X, Y, Z, NX_rot / norm, NY_rot / norm, NZ_rot / norm


def velocity_batch(phis: np.ndarray, P: np.ndarray) -> np.ndarray:
    """轨迹速度 v = dP/dφ_t（中心差分，端点单侧）→ (m,N,3)."""
    dphi = phis[1] - phis[0]
    V = np.empty_like(P)
    V[1:-1] = (P[2:] - P[:-2]) / (2 * dphi)
    V[0] = (P[1] - P[0]) / dphi
    V[-1] = (P[-1] - P[-2]) / dphi
    return V


def first_sign_change_root(phis: np.ndarray, g: np.ndarray, direction: int = -1):
    """对 (m,N) 标量场 g 逐列求**首个变号根**（线性插值），按穿越方向筛选.

    斜齿啮合方程 g=v·n 每点有**两个**变号根：物理接触根（接触点落产形齿径向带，
    r_T≈r_pt±齿高）+ 伪 flare 叶根（r_T≈r_pt+12~21mm、|z_T| 大多在齿宽外）。盲取
    首个变号根会在一侧齿面选中伪叶（2026-08-24 用户目检：右产形面偏离齿面、两产
    形面过远）。物理根恒为 **g 由正变负的下降穿越**（β_w=0/5/19° 全用例标定）。

    direction 语义依赖廓形法矢朝向约定（profile_normals 切向 +90°）；法矢朝向若
    翻转需重新标定——回归护栏：test_conjugate 半径带断言（越带即红）。

    Args:
        phis: (m,) 扫掠角采样
        g: (m,N) 啮合方程标量场
        direction: −1（默认）下降穿越 +→−（物理根）；+1 上升穿越 −→+；0 任意首个（旧行为）

    Returns:
        phi_root (N,), found (N,bool), kk (N,int), tt (N,float)
        其中 root = phis[kk] + tt·(phis[kk+1]−phis[kk])。
    """
    diff = g[1:] - g[:-1]
    if direction == 0:
        sc = g[:-1] * g[1:] <= 0.0
    elif direction < 0:
        sc = (g[:-1] >= 0.0) & (g[1:] <= 0.0) & (diff < 0.0)
    else:
        sc = (g[:-1] <= 0.0) & (g[1:] >= 0.0) & (diff > 0.0)
    found = sc.any(axis=0)
    kk = sc.argmax(axis=0)
    cols = np.arange(g.shape[1])
    gk = g[kk, cols]
    gk1 = g[kk + 1, cols]
    denom = gk - gk1
    # tt 钳制 [0,1]：命中列天然在内（变号区间端点异号）；未命中列 kk=0、g 同号，
    # 不钳制会线性外推出野坐标（曾致 z=−89/r=136 垃圾位置混入 positions 数组）
    tt = np.clip(np.where(np.abs(denom) < 1e-15, 0.0, gk / denom), 0.0, 1.0)
    phi_root = phis[kk] + tt * (phis[kk + 1] - phis[kk])
    return phi_root, found, kk, tt


def all_sign_change_roots(phis: np.ndarray, g: np.ndarray) -> list[list[tuple[int, float]]]:
    """对 (m,N) 标量场 g 逐列求**全部变号根**（线性插值，升序去重）.

    用于刃形根连续追踪（edge.track_edge_roots）：段交界（渐开线↔圆弧尖角）附近
    存在多分支根，盲取首根会在分支间抖动 → 刃形折返自交。

    零点恰落采样点时相邻两区间均触发 → 按 φ 值去重（差 <1e-12 合并）。

    Returns:
        每列 [(k, t), ...]：k = 变号区间左端采样索引，t∈[0,1] 插值比，
        root = phis[k] + t·(phis[k+1]−phis[k])；空列表 = 该列无根。
    """
    sc = g[:-1] * g[1:] <= 0.0
    out: list[list[tuple[int, float]]] = []
    for j in range(g.shape[1]):
        roots: list[tuple[int, float]] = []
        prev_phi = -np.inf
        for k in np.where(sc[:, j])[0]:
            gk, gk1 = g[k, j], g[k + 1, j]
            denom = gk - gk1
            t = 0.0 if abs(denom) < 1e-15 else gk / denom
            phi = phis[k] + t * (phis[k + 1] - phis[k])
            if abs(phi - prev_phi) < 1e-12:
                continue  # 零点触界重复计根
            roots.append((int(k), float(t)))
            prev_phi = phi
        out.append(roots)
    return out


def contact_roots(phis: np.ndarray, P: np.ndarray, nt: np.ndarray, direction: int = -1):
    """啮合方程 g = v·n_t = 0 的首个变号根（Tsai 2023 式(21) 等价形式）.

    direction=−1（默认）只取 g 由正变负的下降穿越 = 物理接触根（斜齿双根结构下
    盲取首根会选中伪 flare 叶）；法矢取反不改根的位置（方程对 n 齐次），但会翻转
    穿越 direction 语义——见 first_sign_change_root 的朝向约定说明。
    """
    V = velocity_batch(phis, P)
    g = np.sum(V * nt, axis=-1)
    phi_root, found, kk, tt = first_sign_change_root(phis, g, direction)
    return phi_root, found, kk, tt

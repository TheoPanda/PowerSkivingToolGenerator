"""K-0.x 基础变换库 — 设计书 §2.4 纯函数实现.

约定 (U1–U12):
  - U1: 右手笛卡尔系, 4×4 齐次矩阵, 列向量 [x,y,z,1]ᵀ
  - U2: M_AB = "从 B 系到 A 系", 左乘、从右向左施加
  - U6: 右手定则旋转正方向
  - U7: β≥0, 旋向由 j=±1 携带
  - U12: 内部 rad, 接口 °
"""

import math
import numpy as np
from numpy.typing import NDArray

# 4×4 齐次矩阵类型
Mat4 = NDArray[np.float64]


def rot_x(theta: float) -> Mat4:
    """K-0.1 Rot_x(θ) — 绕 X 轴旋转 (右手定则).

    Args:
        theta: 旋转角 [rad]

    Returns:
        4×4 齐次旋转矩阵
    """
    c = math.cos(theta)
    s = math.sin(theta)
    return np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, c,   -s,   0.0],
        [0.0, s,   c,    0.0],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=np.float64)


def rot_y(theta: float) -> Mat4:
    """K-0.1 Rot_y(θ) — 绕 Y 轴旋转 (右手定则).

    Args:
        theta: 旋转角 [rad]

    Returns:
        4×4 齐次旋转矩阵
    """
    c = math.cos(theta)
    s = math.sin(theta)
    return np.array([
        [c,   0.0, s,   0.0],
        [0.0, 1.0, 0.0, 0.0],
        [-s,  0.0, c,   0.0],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=np.float64)


def rot_z(theta: float) -> Mat4:
    """K-0.1 Rot_z(θ) — 绕 Z 轴旋转 (右手定则).

    Args:
        theta: 旋转角 [rad]

    Returns:
        4×4 齐次旋转矩阵
    """
    c = math.cos(theta)
    s = math.sin(theta)
    return np.array([
        [c,   -s,   0.0, 0.0],
        [s,   c,    0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=np.float64)


def tran_x(d: float) -> Mat4:
    """K-0.2 Tran(x, d) — 沿 X 轴平移.

    Args:
        d: 平移距离 [mm]

    Returns:
        4×4 齐次平移矩阵
    """
    return np.array([
        [1.0, 0.0, 0.0, d],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=np.float64)


def tran_y(d: float) -> Mat4:
    """K-0.2 Tran(y, d) — 沿 Y 轴平移.

    Args:
        d: 平移距离 [mm]

    Returns:
        4×4 齐次平移矩阵
    """
    return np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, d],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=np.float64)


def tran_z(d: float) -> Mat4:
    """K-0.2 Tran(z, d) — 沿 Z 轴平移.

    Args:
        d: 平移距离 [mm]

    Returns:
        4×4 齐次平移矩阵
    """
    return np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, d],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=np.float64)


def helical_surface(
    x0_fn: callable,
    y0_fn: callable,
    j_w: int,
    r_pw: float,
    beta_w: float,
    u: float,
    theta: float,
) -> tuple[float, float, float]:
    """K-0.6 S_w(u, θ) — 工件螺旋面参数化 ([25] 式(5)).

    S_w(u,θ) = [x0(u)cosθ − y0(u)sinθ,
                 x0(u)sinθ + y0(u)cosθ,
                 j_w·θ·r_pw/tan(β_w)]

    β_w=0 时 z 分量恒为 0，退化为平面廓形。

    Args:
        x0_fn: 廓形 X 分量函数 x0(u)
        y0_fn: 廓形 Y 分量函数 y0(u)
        j_w: 旋向系数 (+1 右旋, −1 左旋, U7)
        r_pw: 工件节圆半径 [mm]
        beta_w: 工件螺旋角 [rad], β≥0 (U7)
        u: 廓形参数
        theta: 绕轴转角 [rad]

    Returns:
        (x, y, z) 螺旋面上点的坐标 [mm]
    """
    x0 = x0_fn(u)
    y0 = y0_fn(u)
    ct = math.cos(theta)
    st = math.sin(theta)

    x = x0 * ct - y0 * st
    y = x0 * st + y0 * ct

    if abs(beta_w) < 1e-15:
        z = 0.0
    else:
        z = j_w * theta * r_pw / math.tan(beta_w)

    return (x, y, z)


def extract_rotation_3x3(M: Mat4) -> NDArray[np.float64]:
    """K-0.7 提取 4×4 齐次矩阵左上 3×3 旋转子阵.

    用于法矢/切矢等自由向量变换 ([15] [Lij], [22] 式(13)).

    Args:
        M: 4×4 齐次变换矩阵

    Returns:
        3×3 旋转矩阵
    """
    return M[:3, :3].copy()


# ── K-0.3 / K-0.5 包络运动链（模块②，2026-08-13）─────────────────────
# 注意：numpy 2.5.0 + Python 3.14 的 4×4 @ 4×4（及 4×4 @ (4,N)）矩阵乘法
# 间歇崩溃（见 test_transforms.py 的 skip 注释）；4×4 @ 4×1 单列向量正常。
# 故 K-0.3/K-0.5 的矩阵**连乘**用纯 Python `_mat4_compose`，点应用仍用 4×4 @ 4×1。


def _mat4_compose(*mats: Mat4) -> Mat4:
    """纯 Python 4×4 矩阵连乘（从左到右），避开 numpy 方阵乘法崩溃.

    Args:
        *mats: 至少一个 4×4 矩阵（np.array 或可转 np.array）

    Returns:
        连乘结果 4×4 np.array
    """
    if not mats:
        raise ValueError("_mat4_compose 至少需要 1 个矩阵")
    result = np.asarray(mats[0], dtype=np.float64).tolist()
    for m in mats[1:]:
        mm = np.asarray(m, dtype=np.float64).tolist()
        result = [
            [
                result[i][0] * mm[0][j] + result[i][1] * mm[1][j]
                + result[i][2] * mm[2][j] + result[i][3] * mm[3][j]
                for j in range(4)
            ]
            for i in range(4)
        ]
    return np.array(result, dtype=np.float64)


def install_transform(a: float, sigma: float, delta: float = 0.0) -> Mat4:
    """K-0.3 安装变换 M_{F_w,F_t} = Tran(x,a)·Rot_x(Σ)·Rot_y(δ).

    Args:
        a: 中心距 [mm], 恒正 (U9)
        sigma: 轴交角 [rad], 有符号 (U8)
        delta: 刀具轴倾斜角 [rad], 默认 0 (U11)

    Returns:
        4×4 齐次变换矩阵（从刀具侧固定系 F_t 到工件侧固定系 F_w）
    """
    return _mat4_compose(tran_x(a), rot_x(sigma), rot_y(delta))


def install_transform_inverse(a: float, sigma: float, delta: float = 0.0) -> Mat4:
    """K-0.3 逆变换 M_{F_t,F_w} = Rot_y(−δ)·Rot_x(−Σ)·Tran(x,−a)."""
    return _mat4_compose(rot_y(-delta), rot_x(-sigma), tran_x(-a))


def workpiece_to_tool_chain(
    phi_w: float,
    phi_t: float,
    a: float,
    sigma: float,
    *,
    delta_phi_t: float = 0.0,
    s_t: float = 0.0,
    s_w: float = 0.0,
    delta: float = 0.0,
) -> Mat4:
    """K-0.5 统一工件→刀具链变换矩阵（返回矩阵，供调用方批量应用）.

    r^(T) = Rot_z(−φ_t−Δφ_t)·Tran(z,−s_t)·M_{F_t,F_w}·Tran(z,s_w)·Rot_z(φ_w)·r^(W)

    退化核对（δ=0、Δφ_t=0、s_t=s_w=0）与 [21] 式(7)
    (r₂ = M⁻¹_{s2-2}·M⁻¹_{s1-s2}·M_{s1-1}·r₁) 同构。

    Args:
        phi_w: 工件动系转角 [rad], 有符号 (U6)
        phi_t: 刀具动系转角 [rad], 有符号 (U6)
        a: 中心距 [mm]
        sigma: 轴交角 [rad], 有符号 (U8)
        delta_phi_t: 进给差动附加转动 [rad], 默认 0 (K-1.7, β_w=0 时为零)
        s_t: 刀具沿自身 z 轴位移 [mm], 默认 0
        s_w: 工件沿自身 z 轴位移 [mm], 默认 0
        delta: 刀具轴倾斜角 [rad], 默认 0 (U11)

    Returns:
        4×4 齐次变换矩阵（从工件动系 W 到刀具动系 T）
    """
    m_ft_fw = install_transform_inverse(a, sigma, delta)
    return _mat4_compose(
        rot_z(-phi_t - delta_phi_t),
        tran_z(-s_t),
        m_ft_fw,
        tran_z(s_w),
        rot_z(phi_w),
    )


def tool_to_workpiece_chain(
    phi_w: float,
    phi_t: float,
    a: float,
    sigma: float,
    *,
    delta_phi_t: float = 0.0,
    s_t: float = 0.0,
    s_w: float = 0.0,
    delta: float = 0.0,
) -> Mat4:
    """K-0.5 逆（正向：刀具→工件）变换矩阵，供正向包络（K-2.13 / K-4.1）.

    r^(W) = Rot_z(−φ_w)·Tran(z,−s_w)·M_{F_w,F_t}·Tran(z,s_t)·Rot_z(φ_t+Δφ_t)·r^(T)

    是 :func:`workpiece_to_tool_chain` 的逆（退化下与 [21] 正向包络同构）。

    Args:
        phi_w: 工件动系转角 [rad]
        phi_t: 刀具动系转角 [rad]
        a: 中心距 [mm]
        sigma: 轴交角 [rad]
        delta_phi_t: 进给差动附加转动 [rad], 默认 0
        s_t: 刀具沿自身 z 轴位移 [mm], 默认 0
        s_w: 工件沿自身 z 轴位移 [mm], 默认 0
        delta: 刀具轴倾斜角 [rad], 默认 0

    Returns:
        4×4 齐次变换矩阵（从刀具动系 T 到工件动系 W）
    """
    m_fw_ft = install_transform(a, sigma, delta)
    return _mat4_compose(
        rot_z(-phi_w),
        tran_z(-s_w),
        m_fw_ft,
        tran_z(s_t),
        rot_z(phi_t + delta_phi_t),
    )


def apply_transform_batch(M: Mat4, points: NDArray[np.float64]) -> NDArray[np.float64]:
    """4×4 矩阵批量应用到 (4,N) 齐次点集，手动展开避开 numpy 方阵乘法崩溃.

    Args:
        M: 4×4 变换矩阵
        points: (4, N) 齐次点集（第 4 行通常全 1）

    Returns:
        (3, N) 变换后点集（去齐次）
    """
    x, y, z, w = points[0], points[1], points[2], points[3]
    out = np.empty((3, points.shape[1]), dtype=np.float64)
    out[0] = M[0, 0] * x + M[0, 1] * y + M[0, 2] * z + M[0, 3] * w
    out[1] = M[1, 0] * x + M[1, 1] * y + M[1, 2] * z + M[1, 3] * w
    out[2] = M[2, 0] * x + M[2, 1] * y + M[2, 2] * z + M[2, 3] * w
    return out

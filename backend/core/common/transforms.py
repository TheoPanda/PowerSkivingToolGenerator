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

"""模块②a 前刀面定义 — 设计书 K-2.1 平面前刀面（产形轮法）.

由设计前角 γ₀ + 刀具螺旋角 β_t + 刀具节圆半径 r_pt 装配平面前刀面隐式方程
F(x,y,z) = (x−r₁)sinγ + y·cosγ·sinβ₁ + z·cosγ·cosβ₁ = 0（[23] 式3.4），
在产形轮固连系 S₁ ≡ 刀具动系 T 中（[23] 下标 1=刀具，勿与 [14] 1=工件 混用）。
输出系数 (A,B,C,const) + 单位法矢 n_rake + 可视化平面片/法矢箭头几何。
不依赖 OCCT。

符号：γ=γ₀ 设计前角、β₁=β_t 产形轮螺旋角=刀具螺旋角、r₁=r_pt 产形轮分度圆半径。
"""

import math
from dataclasses import dataclass

from core.common.gltf_export import GeometrySpec

# 可视化默认尺寸（模块③ 有真实齿面宽后对齐）
_RADIAL_HALF_RATIO = 1.2   # 平面片径向半宽 = 1.2·r_pt
_AXIAL_HALF_MM = 10.0      # 平面片轴向半宽（占位）
_ARROW_LENGTH_RATIO = 0.2  # 法矢箭头长度 = 0.2·r_pt


@dataclass(frozen=True)
class RakeSurface:
    """前刀面（坐标 T）：隐式方程 A·x + B·y + C·z + const = 0."""

    A: float
    B: float
    C: float
    const: float
    p_ref: tuple[float, float, float]  # 过点 (r_pt, 0, 0)

    @property
    def n_rake(self) -> tuple[float, float, float]:
        """单位法矢 = (A,B,C)（sin²γ + cos²γ = 1 构造保证，不翻号）. """
        return (self.A, self.B, self.C)


def build_plane_rake(gamma_deg: float, beta_t_deg: float, r_pt: float) -> RakeSurface:
    """K-2.1 平面前刀面系数装配（产形轮法）.

    F = (x−r₁)sinγ + y·cosγ·sinβ₁ + z·cosγ·cosβ₁ = 0
      → A = sinγ、B = cosγ·sinβ₁、C = cosγ·cosβ₁、const = −A·r₁

    Args:
        gamma_deg: 设计前角 γ₀ [°]
        beta_t_deg: 刀具螺旋角 β_t [°]（β₁ = β_t）
        r_pt: 刀具节圆半径 [mm]（产形轮分度圆半径 r₁）

    Returns:
        RakeSurface（系数 + 过点 P_ref=(r_pt, 0, 0)）

    Raises:
        ValueError: r_pt ≤ 0
    """
    if r_pt <= 0:
        raise ValueError(f"刀具节圆半径 r_pt={r_pt} 必须 > 0")
    gamma = math.radians(gamma_deg)
    beta = math.radians(beta_t_deg)
    a = math.sin(gamma)
    b = math.cos(gamma) * math.sin(beta)
    c = math.cos(gamma) * math.cos(beta)
    const = -a * r_pt
    return RakeSurface(A=a, B=b, C=c, const=const, p_ref=(r_pt, 0.0, 0.0))


def _tangent_basis(n: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """平面内两个正交单位切向 u/v（u = normalize(n×ẑ)、v = n×u，右手系）. """
    a, b, _ = n
    l = math.hypot(a, b)
    if l < 1e-12:
        u = (1.0, 0.0, 0.0)  # n ∥ ẑ 退化
    else:
        u = (b / l, -a / l, 0.0)
    v = (
        n[1] * u[2] - n[2] * u[1],
        n[2] * u[0] - n[0] * u[2],
        n[0] * u[1] - n[1] * u[0],
    )
    return u, v


def plane_patch(surf: RakeSurface, radial_half: float | None = None, axial_half: float = _AXIAL_HALF_MM) -> GeometrySpec:
    """前刀面平面片（以 P_ref 为中心、u 向径向、v 向轴向的矩形，doubleSide）. """
    if radial_half is None:
        radial_half = _RADIAL_HALF_RATIO * surf.p_ref[0]
    u, v = _tangent_basis(surf.n_rake)
    cx, cy, cz = surf.p_ref

    def corner(su: float, sv: float) -> list[float]:
        return [
            cx + su * radial_half * u[0] + sv * axial_half * v[0],
            cy + su * radial_half * u[1] + sv * axial_half * v[1],
            cz + su * radial_half * u[2] + sv * axial_half * v[2],
        ]

    positions = corner(1, 1) + corner(-1, 1) + corner(-1, -1) + corner(1, -1)
    normals = list(surf.n_rake) * 4
    return GeometrySpec(
        kind="mesh",
        positions=positions,
        indices=[0, 1, 2, 0, 2, 3],
        normals=normals,
        layer_id="rake",
    )


def normal_arrow(surf: RakeSurface, length: float | None = None) -> GeometrySpec:
    """法矢箭头：从 P_ref 沿 n_rake 的线段（LINE_STRIP）. """
    if length is None:
        length = _ARROW_LENGTH_RATIO * surf.p_ref[0]
    sx, sy, sz = surf.p_ref
    ex = sx + length * surf.n_rake[0]
    ey = sy + length * surf.n_rake[1]
    ez = sz + length * surf.n_rake[2]
    return GeometrySpec(
        kind="line",
        positions=[sx, sy, sz, ex, ey, ez],
        layer_id="rake.normal",
    )

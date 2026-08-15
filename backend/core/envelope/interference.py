"""模块②b 干涉热力图 — 等效产形齿轮 vs 工件齿轮的符号距离着色（纯数学，直齿）.

符号距离 d = 产形面点（经静态安装变换到 W 系）到工件端面齿槽廓形的最近欧氏距离，
符号由 2D 射线法 point-in-polygon 判定：点在齿槽廓形内（孔侧/空气，刀具切削区）
= 间隙（正），点在齿槽廓形外（材料侧，越过齿面进入环带）= 干涉（负）。
发散色阶：红（干涉）→ 白（相切）→ 蓝（间隙）。

⚠️ 语义（重要）：静态快照（φ=0）下产形面是「整个啮合过程的桶形包络」，桶形鼓出
部分会静态「侵入」齿槽——正确设计也会出现部分红色，这是产形面的桶形形态（与
「产形面只相切于 φ_t*=0 接触线、其余桶形鼓出」一致），**不代表设计错误**。热力图
的价值是「看清产形面相对齿面的空间分布/偏差」，不是「判定刀具真实干涉」。

为何不逐点 OCCT：BRepClass3d_SolidClassifier + BRepExtrema_DistShapeShape 每点
~0.5s，2625 顶点要 ~20 分钟；直齿工件齿面 = 端面齿廓直纹面，符号距离退化为 2D
点-多边形距离，纯 Python/numpy 瞬时（法向投影会混淆「静态旋转错开」与「真实穿透」，
已弃用；point-in-polygon 直接判材料侧/孔侧，语义干净）。
"""

import math
from dataclasses import dataclass

import numpy as np

from core.common.transforms import apply_transform_batch, install_transform
from core.envelope.conjugate import compute_conjugate_surface
from core.envelope.process_plan import ProcessPlan
from core.envelope.swept_cloud import _compute_vertex_normals


@dataclass
class InterferenceResult:
    """干涉热力图（坐标 T，顶点色编码符号距离）."""

    mesh_positions: list[float]
    mesh_indices: list[int]
    mesh_normals: list[float]
    mesh_colors: list[float]  # 逐顶点 RGB（与 positions 等长）
    coverage: dict


def _point_in_polygon(poly: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """2D 射线法 point-in-polygon（向量化），返回 bool 数组（pts 是否在 poly 内）."""
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), dtype=bool)
    n = len(poly)
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[(i + 1) % n]
        cross = (yi > y) != (yj > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (xj - xi) * (y - yi) / (yj - yi) + xi
        inside ^= cross & (x < xint)
    return inside


def _nearest_distance(pts: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """点到多边形各顶点的最近欧氏距离（2D，numpy 广播）."""
    d = np.full(len(pts), np.inf)
    for j in range(len(poly)):
        dd = (pts[:, 0] - poly[j, 0]) ** 2 + (pts[:, 1] - poly[j, 1]) ** 2
        d = np.minimum(d, dd)
    return np.sqrt(d)


def _diverging_color(d: np.ndarray, clamp: float) -> np.ndarray:
    """符号距离 → 发散色阶 RGB（红=干涉/负，白=0，蓝=间隙/正），返回 (N,3) ∈ [0,1]."""
    t = np.clip(d / clamp, -1.0, 1.0)
    r = np.where(t < 0.0, 1.0, 1.0 - t)
    g = 1.0 - np.abs(t)
    b = np.where(t > 0.0, 1.0, 1.0 + t)
    return np.stack([r, g, b], axis=1)


def compute_interference(
    profile_pts,
    plan: ProcessPlan,
    *,
    b_w: float,
    k_io: int,
    z_t: int,
    n_z: int = 21,
    m: int = 181,
    theta_range_deg: float = 40.0,
    normals=None,
    clamp_mm: float = 0.5,
) -> InterferenceResult:
    """K-2.6 干涉热力图：单齿槽产形面符号距离着色 → 阵列 z_t 份（坐标 T）.

    Args:
        profile_pts: 工件齿槽廓形点 [(x, y), ...]（同时是产形面啮合输入 + 符号距离
            的「齿槽多边形」）
        plan: ProcessPlan（Σ/a/同步比）
        b_w: 工件齿宽 [mm]
        k_io: 内/外齿轮系数（仅内齿轮 −1 产形面已支持）
        z_t: 刀具齿数（阵列份数）
        n_z: 轴向层数
        m: 刀具转角采样数
        theta_range_deg: 刀具转角扫描范围 [°]
        clamp_mm: 色阶饱和距离 [mm]（|d|≥clamp 即饱和红/蓝）

    Returns:
        InterferenceResult（坐标 T；coverage 沿用单齿槽报告）

    Raises:
        ValueError: z_t < 1 / clamp_mm ≤ 0
    """
    if z_t < 1:
        raise ValueError("刀具齿数 z_t 必须 ≥ 1")
    if clamp_mm <= 0:
        raise ValueError(f"色阶饱和距离 clamp_mm={clamp_mm} 必须 > 0")

    surf = compute_conjugate_surface(
        profile_pts, plan, b_w=b_w, k_io=k_io, n_z=n_z, m=m,
        theta_range_deg=theta_range_deg, normals=normals,
    )
    single_pos = surf.mesh_positions
    single_idx = surf.mesh_indices
    n_vert = len(single_pos) // 3
    if n_vert == 0:
        return InterferenceResult(
            surf.mesh_positions, surf.mesh_indices, surf.mesh_normals, [], surf.coverage
        )

    # 产形面顶点（T）→ 静态安装变换 → W 系（2D 用于符号距离，直齿轮 z 无关）
    sigma = math.radians(plan.sigma_deg)
    M = install_transform(plan.a, sigma)
    qws = np.empty((n_vert, 2), dtype=np.float64)
    for i in range(n_vert):
        x, y, z = single_pos[3 * i], single_pos[3 * i + 1], single_pos[3 * i + 2]
        qw = apply_transform_batch(M, np.array([[x], [y], [z], [1.0]])).ravel()
        qws[i, 0] = qw[0]
        qws[i, 1] = qw[1]

    # 工件齿槽廓形（= profile_pts，闭合多边形）
    poly = np.array([(pt[0], pt[1]) for pt in profile_pts], dtype=np.float64)

    d_abs = _nearest_distance(qws, poly)
    inside = _point_in_polygon(poly, qws)
    d = np.where(inside, d_abs, -d_abs)  # 内=间隙(正)，外=干涉(负)

    col = _diverging_color(d, clamp_mm)
    single_col: list[float] = []
    for c in col:
        single_col += [float(c[0]), float(c[1]), float(c[2])]

    # 阵列 z_t 份：positions 绕 z 旋转 + colors 逐份复制（对称）+ normals 重算
    delta = 2.0 * math.pi / z_t
    all_pos: list[float] = []
    all_col: list[float] = []
    all_idx: list[int] = []
    for k in range(z_t):
        c, s = math.cos(k * delta), math.sin(k * delta)
        for i in range(0, len(single_pos), 3):
            x, y, z = single_pos[i], single_pos[i + 1], single_pos[i + 2]
            all_pos += [x * c - y * s, x * s + y * c, z]
        all_col += single_col
        all_idx += [idx + k * n_vert for idx in single_idx]

    all_normals = _compute_vertex_normals(all_pos, all_idx)
    return InterferenceResult(
        mesh_positions=all_pos,
        mesh_indices=all_idx,
        mesh_normals=all_normals,
        mesh_colors=all_col,
        coverage=surf.coverage,
    )

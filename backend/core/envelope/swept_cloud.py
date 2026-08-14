"""模块②b 离散包络点云 + 扫掠点云 — 设计书 K-2.9 纯数学.

由工件齿廓点云经 K-0.5 运动链扫掠得 m×n 点云（扫掠点云，坐标 T），
并按规则网格三角化为 mesh（供 GLB 导出）。不依赖 OCCT。

K-2.10 投影 z=0 属刃形提取（edge.py），不在此模块——扫掠点云 mesh 为
原始扫掠点云（含 z 分量）直接三角化（spec「mesh ≠ 投影内边界结果」）。
"""

import math
from dataclasses import dataclass

import numpy as np

from core.common.transforms import apply_transform_batch, workpiece_to_tool_chain
from core.envelope.process_plan import ProcessPlan
from core.workpiece.profile import Arc, Polyline, Segment

# 线框中性深灰 #1f2937（扫掠点云「网+点」档的连通性线，不抢光谱，ADR 见 spec）
WIREFRAME_COLOR: tuple[float, float, float] = (0x1F / 255.0, 0x29 / 255.0, 0x37 / 255.0)


def jet(t: float) -> tuple[float, float, float]:
    """jet 光谱色（蓝→青→绿→黄→红），t ∈ [0,1] 归一化（超出截断）.

    t=0 → (0, 0, 0.5) 蓝（≈#00007F，光谱蓝端，与起止齿廓蓝线一致）；
    t=1 → (1, 0, 0) 红。纯 Python 分段线性，无新依赖。
    """
    t = min(1.0, max(0.0, t))
    if t < 0.125:
        return (0.0, 0.0, 0.5 + 0.5 * (t / 0.125))
    if t < 0.375:
        return (0.0, (t - 0.125) / 0.25, 1.0)
    if t < 0.625:
        return ((t - 0.375) / 0.25, 1.0, 1.0 - (t - 0.375) / 0.25)
    if t < 0.875:
        return (1.0, 1.0 - (t - 0.625) / 0.25, 0.0)
    return (1.0, 0.0, 0.0)


@dataclass
class SweptCloud:
    """扫掠点云扫掠点云（坐标 T）."""

    cloud: np.ndarray          # (m, n, 3) 点云
    phi_t: np.ndarray          # (m,) 刀具转角采样 [rad]
    mesh_positions: list[float]  # 三角网扁平顶点 [x0,y0,z0, x1,y1,z1, ...]
    mesh_indices: list[int]      # 三角网索引
    mesh_normals: list[float]    # 顶点法向（面积加权面法向平均，与 positions 等长）
    mesh_colors: list[float]     # 逐顶点光谱 jet 色（扁平 [r,g,b,...]，与 positions 等长，按 φ_t 行着色）
    wireframe_indices: list[int]  # 三角网线框段（LINES 模式，三角片边序，每条 2 索引，含重复共享边）


def _sample_segments(segs: list[Segment], n_points: int) -> list[tuple[float, float]]:
    """段列表（Arc/Polyline）→ 按累计弧长均匀采样 n_points 个点（闭合去重）."""
    dense: list[tuple[float, float]] = []
    for seg in segs:
        if isinstance(seg, Arc):
            cx, cy = seg.center
            for k in range(48):
                t = k / 48
                a = seg.a0 + (seg.a1 - seg.a0) * t
                dense.append((cx + seg.radius * math.cos(a), cy + seg.radius * math.sin(a)))
        else:
            dense.extend(seg.points)
    if len(dense) < 2:
        return dense
    # 去重相邻重复点
    dedup = [dense[0]]
    for p in dense[1:]:
        if math.hypot(p[0] - dedup[-1][0], p[1] - dedup[-1][1]) > 1e-9:
            dedup.append(p)
    # 累计弧长
    cum = [0.0]
    for i in range(1, len(dedup)):
        cum.append(cum[-1] + math.hypot(dedup[i][0] - dedup[i - 1][0], dedup[i][1] - dedup[i - 1][1]))
    total = cum[-1]
    if total < 1e-12:
        return dedup
    pts: list[tuple[float, float]] = []
    for k in range(n_points):
        s = total * k / n_points
        lo, hi = 0, len(dedup) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if cum[mid] <= s:
                lo = mid
            else:
                hi = mid
        seg_len = cum[hi] - cum[lo]
        t = 0.0 if seg_len < 1e-15 else (s - cum[lo]) / seg_len
        x = dedup[lo][0] + (dedup[hi][0] - dedup[lo][0]) * t
        y = dedup[lo][1] + (dedup[hi][1] - dedup[lo][1]) * t
        pts.append((x, y))
    return pts


def extract_gap_points(p, n_points: int = 200) -> list[tuple[float, float]]:
    """从 GearParams 提取单齿廓形点（离散包络输入）.

    内齿轮 k_io=−1 用 tooth_gap_segments（齿槽 = 刀具齿的反包络源，ADR-017）；
    外齿轮 k_io=+1 用 _tooth_open_segments（开放单齿轮廓：左齿根→左齿面→齿顶→
    右齿面→右齿根，不闭合）。⚠️ 不能用 single_tooth_segments——它的 350° 根弧
    是 3D 实体建模（ThruSections 需闭合截面）的闭合产物，扫进包络会污染扫掠点云。
    """
    from core.workpiece.profile import _tooth_open_segments, tooth_gap_segments

    if p.k_io == -1:
        segs = tooth_gap_segments(p, 0)
    else:
        segs, *_ = _tooth_open_segments(p, 0, 40)
    return _sample_segments(segs, n_points)


def generate_envelope_cloud(
    profile_pts: list[tuple[float, float]],
    plan: ProcessPlan,
    *,
    m: int = 181,
    theta_range_deg: float = 20.0,
) -> SweptCloud:
    """K-2.9 运动包络点云 + 三角网连片.

    采样语义：φ_t = linspace(−θ_range, +θ_range, m)（含两端点与 φ_t=0），
    φ_w = φ_t / omega_ratio（同步关系 K-1.7）。cloud[i][j] = (φ_t[i], profile[j])。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]，n 个
        plan: ProcessPlan（Σ/a/同步比）
        m: 运动离散数（刀具转角采样数）
        theta_range_deg: 刀具转角扫描范围 [°]，±θ_range

    Returns:
        SweptCloud（cloud 含 z 分量；mesh 为原始点云直接三角化）

    Raises:
        ValueError: 齿廓点 < 2 或 m < 2
    """
    n = len(profile_pts)
    if n < 2:
        raise ValueError("齿廓点至少 2 个")
    if m < 2:
        raise ValueError("运动离散数 m 至少 2")

    # 廓形点 → (4, n) 齐次（z=0 端面廓形）
    P = np.array([(x, y, 0.0, 1.0) for (x, y) in profile_pts], dtype=np.float64).T  # (4, n)

    theta_range = math.radians(theta_range_deg)
    phi_t = np.linspace(-theta_range, theta_range, m)  # (m,)
    phi_w = phi_t / plan.omega_ratio  # φ_w = φ_t·z_t/z_w = φ_t / (z_w/z_t)

    sigma = math.radians(plan.sigma_deg)
    cloud = np.empty((m, n, 3), dtype=np.float64)
    for j in range(m):
        M = workpiece_to_tool_chain(phi_w[j], phi_t[j], plan.a, sigma)
        cloud[j] = apply_transform_batch(M, P).T  # (n, 3)

    # 三角网连片：每格两个三角 (a,c,b) + (b,c,d)
    indices: list[int] = []
    for i in range(m - 1):
        for j in range(n - 1):
            a = i * n + j
            b = a + 1
            c = a + n
            d = c + 1
            indices += [a, c, b, b, c, d]

    flat = [v for p in cloud.reshape(-1, 3).tolist() for v in p]
    normals = _compute_vertex_normals(flat, indices)

    # 逐顶点光谱色：顶点 v 的行 i = v // n，色 = jet(i/(m−1))（蓝=起点行 0，红=终点行 m−1）
    colors: list[float] = []
    for v in range(m * n):
        r, g, b = jet((v // n) / (m - 1))
        colors += [r, g, b]

    # 三角网线框段（三角片边序，含重复共享边；与 mesh_indices 同序 → 可按行 drawRange 揭示）
    wire: list[int] = []
    for t in range(len(indices) // 3):
        v0, v1, v2 = indices[3 * t], indices[3 * t + 1], indices[3 * t + 2]
        wire += [v0, v1, v1, v2, v2, v0]

    return SweptCloud(
        cloud=cloud,
        phi_t=phi_t,
        mesh_positions=flat,
        mesh_indices=indices,
        mesh_normals=normals,
        mesh_colors=colors,
        wireframe_indices=wire,
    )


def _compute_vertex_normals(positions_flat: list[float], indices: list[int]) -> list[float]:
    """三角网顶点法向（面积加权面法向平均），返回与 positions 等长的扁平法向.

    向量化计算（np.cross 批量叉积 + np.add.at 累加），不触发方阵乘法崩溃。
    """
    n_vertices = len(positions_flat) // 3
    pts = np.array(positions_flat, dtype=np.float64).reshape(-1, 3)
    idx = np.array(indices, dtype=np.int64).reshape(-1, 3)  # (T, 3)
    v0 = pts[idx[:, 0]]
    v1 = pts[idx[:, 1]]
    v2 = pts[idx[:, 2]]
    face_normals = np.cross(v1 - v0, v2 - v0)  # (T, 3) 面法向（模 ∝ 2×面积）
    normals = np.zeros((n_vertices, 3), dtype=np.float64)
    np.add.at(normals, idx[:, 0], face_normals)
    np.add.at(normals, idx[:, 1], face_normals)
    np.add.at(normals, idx[:, 2], face_normals)
    lens = np.linalg.norm(normals, axis=1, keepdims=True)
    lens[lens < 1e-12] = 1.0
    normals = normals / lens
    return normals.reshape(-1).tolist()

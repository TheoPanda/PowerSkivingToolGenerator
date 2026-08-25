"""模块②b 产形面（共轭面）— 设计书 K-2.6 离散数值啮合路线（纯数学）.

产形面 = 工件齿面经反向包络在刀具侧生成的共轭曲面（坐标 T），即 [12] Tsai 2023
图3 蓝色面、设计书 §3.4「共轭面（产形面）」契约输出。与扫掠点云（中间媒介、桶形
失真）不同——产形面是严格意义的刀具理论齿面（文献原文 "the generating surface …
is barrel-shaped"）。

解法（A 数值啮合方程路线）：对工件齿面每一点 P（含法矢 n），沿刀具转角 φ_t 扫掠
得轨迹 P(φ_t)，啮合方程（[12] 式21 等价形式）g(φ_t)=v(φ_t)·n_t(φ_t)=0 的根 φ_t*
即接触位，P(φ_t*) 为产形面点。斜齿下每点有双根（物理接触根 + 伪 flare 叶根），
取 **g 由正变负的下降穿越**（meshing.first_sign_change_root direction=−1，
2026-08-24 标定；盲取首根曾使一侧齿面整侧落伪叶——右产形面偏离齿面、两产形面
过远）。法矢取反不改根的位置（方程对 n 齐次），但会翻转穿越方向语义。数值核心
集中在 meshing.py（全向量化逐元素展开，避开 numpy 2.5.0 + Python 3.14 的方阵
乘法崩溃）。不依赖 OCCT。
"""

import math
from dataclasses import dataclass, field

import numpy as np

from core.common.mesh import compute_vertex_normals
from core.envelope.meshing import (
    chain_matrices,
    contact_roots,
    helical_tooth_grid,
    profile_normals,
    rotate_normals_batch_3d,
    transform_batch,
)
from core.envelope.process_plan import ProcessPlan


@dataclass
class AnimFrameData:
    """单个动画帧：刀具转角 φ_t 下工件齿面在 T 系中的位置."""

    phi_t_deg: float          # 刀具转角 [deg]
    positions: list[float]    # 扁平顶点 [x0,y0,z0, ...]（仅 mesh 使用的顶点）


@dataclass
class ConjugateSurface:
    """产形面（坐标 T）."""

    mesh_positions: list[float]  # 三角网扁平顶点 [x0,y0,z0, ...]
    mesh_indices: list[int]      # 三角网索引
    mesh_normals: list[float]    # 顶点法向（面积加权面法向平均，与 positions 等长）
    coverage: dict               # {total_points, found, uncovered, coverage_ratio, pass}
    interference_stats: dict = field(default_factory=dict)  # 干涉着色统计（conjugate_gear 填充；红/绿/蓝/灰计数 + 最深侵入）
    mesh_colors: list[float] = field(default_factory=list)  # 可选逐顶点 RGB（与 positions 等长）
    mesh_contact_phi: list[float] = field(default_factory=list)  # 逐顶点接触角 φ_t [rad]（与 positions 等长；未命中填 0）
    # 动画帧数据（include_anim=True 时填充）
    anim_frames: list[AnimFrameData] = field(default_factory=list)
    anim_indices: list[int] = field(default_factory=list)  # mesh 顶点在原始 N 点中的索引
    anim_mesh_indices: list[int] = field(default_factory=list)  # 重映射后的三角网索引
    # 参与求解的工件齿面网格（include_tooth_grid=True 时填充，坐标 W，行主序 iz·n + iu）：
    # 逐点位置/单位法矢 + 最终参与掩码（含边界修剪/半径兜底/折叠行剔除后的 found），
    # 不变式 sum(tooth_participating) == coverage["found"]
    tooth_positions: list[float] = field(default_factory=list)
    tooth_normals: list[float] = field(default_factory=list)
    tooth_participating: list[bool] = field(default_factory=list)


def compute_conjugate_surface(
    profile_pts: list[tuple[float, float]],
    plan: ProcessPlan,
    *,
    b_w: float,
    k_io: int,
    n_z: int = 21,
    m: int = 181,
    theta_range_deg: float = 40.0,
    normals=None,
    trim_fold: bool = False,
    include_anim: bool = False,
    m_anim: int = 72,
    anim_theta_range_deg: float = 360.0,
    include_tooth_grid: bool = False,
) -> ConjugateSurface:
    """K-2.6 离散数值啮合产形面：齿面网格 × 啮合方程求根 → 三角网.

    齿面网格 = n 个廓形点 × n_z 个轴向层（z_w ∈ [−b_w/2, b_w/2]）；每点沿 φ_t
    扫掠求啮合根，得 (n_z × n) 产形面点网格，三角网连片（内齿轮闭合廓形沿
    廓形向回绕）。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]，n 个
        plan: ProcessPlan（Σ/a/同步比）
        b_w: 工件齿宽 [mm]（产形面轴向展布；桶形面扩展时可传 5×b_w）
        k_io: 内/外齿轮系数（−1 内齿轮闭合廓形 → 三角网回绕）
        n_z: 轴向层数
        m: 刀具转角采样数
        theta_range_deg: 刀具转角扫描范围 [°]（斜齿下限 120°：β_w≠0 时自动抬高）
        trim_fold: 折叠行修剪（桶形面扩展 z 范围时启用）：包络在齿宽外会 flare
            出第二叶（该行半径双峰），逐 z 行检测排序半径最大间隙超阈值即整行
            剔除，仅保留单叶桶面（双层伪影修复）
        include_anim: 是否返回逐帧动画数据（用于运动仿真可视化）
        m_anim: 动画帧数（include_anim=True 时有效）
        anim_theta_range_deg: 动画角度范围 [°]（默认 ±360°，独立于产形面的 theta_range_deg）
        include_tooth_grid: 是否返回参与求解的工件齿面网格（W 系逐点位置/法矢 +
            最终参与掩码，供「内齿轮齿面」图层渲染离散点+法向箭头）

    Returns:
        ConjugateSurface（坐标 T）

    Raises:
        ValueError: 廓形点 < 2 / m < 2 / n_z < 2 / b_w ≤ 0
    """
    n = len(profile_pts)
    if n < 2:
        raise ValueError("齿廓点至少 2 个")
    if m < 3:
        raise ValueError("运动离散数 m 至少 3（中心差分 + 线性插值需 ≥3 采样）")
    if n_z < 2:
        raise ValueError("轴向层数 n_z 至少 2")
    if b_w <= 0:
        raise ValueError(f"齿宽 b_w={b_w} 必须 > 0")

    norms = normals if normals is not None else profile_normals(profile_pts)

    # 齿面网格（K-0.6 螺旋面）：行主序 index = iz·n + iu（n_z 行 × n 列）。
    # 斜齿 β_w≠0 时每层廓形绕 z 扭转 θ(z)=j_w·z·tanβ_w/r_pw（螺旋面）；
    # 直齿 β_w=0 退化为沿 z 拉伸（零回归）。
    xs = np.array([pt[0] for pt in profile_pts], dtype=np.float64)
    ys = np.array([pt[1] for pt in profile_pts], dtype=np.float64)
    zs = np.linspace(-b_w / 2.0, b_w / 2.0, n_z)
    beta_w = math.radians(plan.beta_w_deg)
    X, Y, Z, NX, NY, NZ = helical_tooth_grid(
        profile_pts, norms, zs, plan.j_w, beta_w, plan.r_pw
    )
    N = n * n_z

    # 预计算 m 个 K-0.5 链矩阵（φ_w = φ_t / omega_ratio，同步 K-1.7）
    # 斜齿接触位更广（交错轴啮合接触位远离 φ_t=0，±40° 不足），120° 为物理下限：
    # β_w≠0 时调用方传小值自动抬高，避免「忘了 120°」的调用方错误（router 曾两处散落此知识）。
    if abs(plan.beta_w_deg) > 1e-12:
        theta_range_deg = max(theta_range_deg, 120.0)
    theta_range = math.radians(theta_range_deg)
    phis = np.linspace(-theta_range, theta_range, m)
    phws = phis / plan.omega_ratio
    sigma = math.radians(plan.sigma_deg)

    Ms = chain_matrices(phis, phws, plan.a, sigma)
    P = transform_batch(Ms, X, Y, Z)               # (m, N, 3)
    nt = rotate_normals_batch_3d(Ms, NX, NY, NZ)   # (m, N, 3)（斜齿法矢含 z 分量）
    phi_root, found, kk, tt = contact_roots(phis, P, nt)

    # 排除齿顶/齿根圆弧段 + 渐开线端点：这些点接触为极限/径向（与齿面接触不连续），
    # 计入三角网会产生撕裂（尖角处中心差分法向被污染 → 伪根 → 接触点跳 1–10mm）。
    # 用半径判据：轮廓最小/最大半径（r_a/r_f）附近 ε 带内的点不计入（保留齿面内部）。
    # r_prof 用**端面廓形半径**（未扭转、与 z 层无关），勿用扭转后的 X/Y。
    r_prof = np.hypot(np.tile(xs, n_z), np.tile(ys, n_z))
    r_lo, r_hi = float(r_prof.min()), float(r_prof.max())
    # 斜齿（β_w≠0）螺旋面使齿顶/齿根圆弧段尖角处啮合方程出现双根（伪根范围更大），
    # 渐开线端点（距 r_hi/r_lo ~2.4% 齿高）接触位跳变 → 三角网折叠（波浪折纹）。
    # 故斜齿加大修剪带到 3% 齿高，直齿保持 1%（算例1 ≈ 0.045mm，零回归）。
    trim_ratio = 0.03 if abs(plan.beta_w_deg) > 1e-12 else 0.01
    trim = trim_ratio * (r_hi - r_lo)
    boundary = (r_prof <= r_lo + trim) | (r_prof >= r_hi - trim)

    # 段界尖角邻点法向跳变剔除（斜齿飞点根因，2026-08-21 用户报「产形面不对」）：
    # 渐开线↔圆弧段界 ±1 邻点的中心差分法向被污染（dn ~200× 中位数），斜齿啮合方程
    # 双根范围更大 → 伪根使整列飞点（r→60~1000mm，前端视图被拉爆）；直齿同处跳变
    # 仅 1-10mm，曾被 trim 掩盖。按法向跳变剔除，平滑齿面 dn 远低于阈值（零回归）。
    n2 = np.array([(float(nx), float(ny)) for nx, ny in norms], dtype=np.float64)
    dn = np.hypot(n2[2:, 0] - n2[:-2, 0], n2[2:, 1] - n2[:-2, 1])  # dn[i] ↔ 廓形点 i+1
    jump_n = np.zeros(n, dtype=bool)
    jump_n[1:-1] = dn > max(0.3, 20.0 * float(np.median(dn)))
    boundary |= np.tile(jump_n, n_z)  # 行主序 index = iz*n + iu，与 r_prof 同 tile

    found = found & ~boundary

    cols = np.arange(N)
    pts = P[kk, cols] + tt[:, None] * (P[kk + 1, cols] - P[kk, cols])  # (N, 3)

    # 半径单侧宽松兜底：斜齿产形面半径合法带可宽（工件齿根弧共轭区 r 可达
    # 中位数 +20mm 量级），不用对称带（会误杀真点）；仅防数值伪根千毫米级飞点
    # 拉爆前端视图。
    r_all = np.hypot(pts[:, 0], pts[:, 1])
    if found.sum() > 16:
        med = float(np.median(r_all[found]))
        found &= r_all < med + max(20.0, 2.0 * (r_hi - r_lo))

    # 折叠行修剪（trim_fold，桶形面扩展 z 范围时）：包络在齿宽外 flare 出第二叶，
    # 该 z 行半径呈双峰（根带+外抛顶带、中间齿面缺失，maxgap≈0.5~0.6 齿高）；单叶
    # 行 maxgap≈0.26 齿高。逐行检测排序半径最大间隙，超 0.4 齿高整行剔除。
    if trim_fold:
        r_pts = np.hypot(pts[:, 0], pts[:, 1])
        for iz in range(n_z):
            s = slice(iz * n, (iz + 1) * n)
            hit = found[s]
            if hit.sum() < 2:
                continue
            rr = np.sort(r_pts[s][hit])
            span = rr[-1] - rr[0]
            # 单叶行 gap/span≈0.26；折叠行（双叶）≈0.43~0.6 → 阈值 0.35
            if span > 1e-9 and np.diff(rr).max() > 0.35 * span:
                found[s] = False

    # 覆盖率只统计齿面内部点（圆弧段/渐开线端点已被边界修剪排除，不计入分母）
    n_total = int((~boundary).sum())
    n_found = int(found.sum())
    coverage = {
        "total_points": n_total,
        "found": n_found,
        "uncovered": max(0, n_total - n_found),
        "coverage_ratio": n_found / n_total if n_total else 1.0,
        "pass": n_found == n_total,
    }

    # 三角网连片（仅四角全命中的单元；内齿轮闭合廓形沿廓形向回绕）
    closed = (k_io == -1)
    positions: list[float] = []
    for v in range(N):
        positions += [float(pts[v, 0]), float(pts[v, 1]), float(pts[v, 2])]
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
                indices += [a, b, c, b, d, c]

    normals = compute_vertex_normals(positions, indices)

    # ── 动画帧提取（独立 θ 范围，默认 ±360°） ──────────────────────
    # 当 include_anim=True 时，用 anim_theta_range_deg 做独立扫掠（不复用产形面 P），
    # 每帧返回齿面网格在 T 系中的 positions（仅 mesh 使用的顶点）。
    anim_data_frames: list[AnimFrameData] = []
    anim_data_indices: list[int] = []
    anim_data_mesh_indices: list[int] = []
    if include_anim and len(indices) > 0:
        mesh_verts = sorted(set(indices))
        vert_remap = {old_i: new_i for new_i, old_i in enumerate(mesh_verts)}
        anim_data_indices = [int(v) for v in mesh_verts]
        anim_data_mesh_indices = [vert_remap[int(idx)] for idx in indices]

        # 独立扫掠：anim_theta_range_deg 范围，m_anim 个采样点
        anim_theta_range = math.radians(anim_theta_range_deg)
        anim_phis = np.linspace(-anim_theta_range, anim_theta_range, m_anim)
        anim_phws = anim_phis / plan.omega_ratio
        anim_Ms = chain_matrices(anim_phis, anim_phws, plan.a, sigma)
        anim_P = transform_batch(anim_Ms, X, Y, Z)  # (m_anim, N, 3)

        for fi in range(m_anim):
            frame_pts = anim_P[fi, mesh_verts, :]
            anim_data_frames.append(AnimFrameData(
                phi_t_deg=round(float(np.degrees(anim_phis[fi])), 4),
                positions=[round(float(v), 6) for v in frame_pts.ravel()],
            ))

    # 齿面网格导出（include_tooth_grid=True）：W 系逐点位置/法矢 + 最终参与掩码
    # （与 coverage 同源 found，含边界修剪/半径兜底/折叠行剔除全部效果）
    tooth_pos: list[float] = []
    tooth_nrm: list[float] = []
    tooth_mask: list[bool] = []
    if include_tooth_grid:
        tooth_pos = [float(v) for v in np.stack([X, Y, Z], axis=1).ravel()]
        tooth_nrm = [float(v) for v in np.stack([NX, NY, NZ], axis=1).ravel()]
        tooth_mask = [bool(v) for v in found]

    return ConjugateSurface(
        mesh_positions=positions,
        mesh_indices=indices,
        mesh_normals=normals,
        coverage=coverage,
        mesh_contact_phi=[float(v) for v in phi_root],
        anim_frames=anim_data_frames,
        anim_indices=anim_data_indices,
        anim_mesh_indices=anim_data_mesh_indices,
        tooth_positions=tooth_pos,
        tooth_normals=tooth_nrm,
        tooth_participating=tooth_mask,
    )

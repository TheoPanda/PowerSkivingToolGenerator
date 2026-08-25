"""模块②b 刃形 — 产形面（共轭面）∩ 前刀面（Tsai 2023 step 3）+ 覆盖 + ffα（纯数学）.

刃形 = 产形面 ∩ 前刀面（文献 [12] Tsai 2023 图3："tool cutting-edge is intersection
curve of generating surface and rake surface"）。对工件廓形每一离散点 u，联立解：

    g(φ) = v(φ)·n_t(φ) = 0     （啮合方程，接触位；Tsai 式(21)）
    F(P(u, z_w, φ)) = 0         （落在前刀面上）

直齿工件齿面 P(u, z_w, φ) = P0(φ) + z_w·col(φ)（col = ∂P/∂z_w，对 z_w 仿射），
故 g 与 F 均对 z_w 仿射：g = g0 + z_w·gz、F = F0 + z_w·Fz。消去 z_w 得单变量
h(φ) = g0·Fz − F0·gz = 0，求根后闭式回代 z_w* = −F0/Fz、刃形点 = P0(φ*) + z_w*·col(φ*)。

⚠️ 与设计书 K-2.8 的 [25] 式(8)「轨迹穿面法」（z_w=0 钉死、无啮合条件）**不同**——
那是离散包络分支的近似（[25]/[21]，仅复杂齿形二期适用），本模块为共轭法的精确刃形。
正确性由：①刃形点落在产形面上（g=0 且 F=0，构造保证）；②正反闭包 ffα；③双路线互检
（analytic.py 二分精化同一方程）；④算例1 输入自洽 兜底（ADR-019）。

斜齿（β_w≠0，2026-08-24）：消元法失效（齿面非 z_w 仿射）→ compute_helical_edge
数值求交路线（K-2.8b）——在产形面 (u,z) 网格上逐列沿 z 解 F=0，链跟踪选物理叶，
双残差（贴前刀面 + 贴产形面独立重算）<5μm 作验收，ffα 闭环不适用（None）。
不依赖 OCCT。
"""

import math
from dataclasses import dataclass

import numpy as np

from core.common.transforms import apply_transform_batch, tool_to_workpiece_chain
from core.envelope.meshing import (
    all_sign_change_roots,
    chain_matrices,
    contact_roots,
    helical_tooth_grid,
    profile_normals,
    rotate_normals_batch,
    rotate_normals_batch_3d,
    transform_batch,
    velocity_batch,
)
from core.envelope.process_plan import ProcessPlan
from core.envelope.rake import RakeSurface


@dataclass
class EdgeSegment:
    """一段刃形（有序 3D 点列，落在前刀面上）."""

    pts: list[list[float]]  # [[x,y,z], ...] 有序
    continuity: str  # 'continuous' | 'discontinuous'


@dataclass
class EdgeResult:
    """刃形提取结果."""

    segments: list[EdgeSegment]
    coverage_report: dict
    ffa_um: float | None           # 斜齿无 ffα 闭环（第二批范围外）→ None
    residual_stats: dict | None = None  # 斜齿双残差 {max_plane_um, max_surface_um, pass}


def inner_contour(pts: np.ndarray, rake: RakeSurface, eps_mm: float = 0.15) -> list[int]:
    """前刀面平面**内侧包络轮廓**（多根刃形候选点 → 无自交环，保输入分辨率）.

    物理依据（2026-08-20，顶刃↔侧刃交界折叠修复）：段交界尖角处产形面分裂为
    多叶，各叶与前刀面的交线（多分支刃形）在平面上**真实交叉**；刀齿材料必须
    同时位于所有叶的内侧 → 真实刃形环 = 各分支曲线的内侧包络（交叉处切到更近
    分支；远分支点不在材料边界上，自然剔除——它们正是折返自交与实体缝合不良
    体的来源）。

    实现：候选点投到前刀面平面、以形心为原点取极角/半径 → **邻域下包络滤波**：
    若某点的极角邻域（±1.5×中位角距）内存在半径显著更小（> eps_mm）的点，则该
    点属远分支，剔除。近分支连续覆盖处其自身点互为邻域最小 → 全保留（分辨率
    = 输入密度，无重采样损失）。幸存点按极角升序输出环。
    假设环关于形心星形（前刀面片扇形剖分同此假设）。

    Args:
        pts: (K,3) 全部候选刃形点（坐标 T，多根全保留，每列可 >1 点）
        rake: RakeSurface（提供平面 2D 基）
        eps_mm: 远分支剔除的半径差阈值 [mm]（小于此差的近点视作同分支毛刺保留）

    Returns:
        环序点下标列表（range(K) 的子集，按极角升序）
    """
    if len(pts) < 3:
        return list(range(len(pts)))
    nv = np.array(rake.n_rake, dtype=np.float64)
    nv = nv / np.linalg.norm(nv)
    e1 = np.cross(nv, [0.0, 0.0, 1.0])
    ne1 = float(np.linalg.norm(e1))
    e1 = e1 / ne1 if ne1 > 1e-12 else np.array([1.0, 0.0, 0.0])
    e2 = np.cross(nv, e1)
    # 逐元素展开（numpy 2.5 + Py3.14 matmul 崩溃规避纪律，勿用 pts @ e1）
    qx = pts[:, 0] * e1[0] + pts[:, 1] * e1[1] + pts[:, 2] * e1[2]
    qy = pts[:, 0] * e2[0] + pts[:, 1] * e2[1] + pts[:, 2] * e2[2]
    q = np.stack([qx, qy], axis=1)                # (K, 2)
    c = q.mean(axis=0)
    d = q - c
    ang = np.arctan2(d[:, 1], d[:, 0])
    r = np.hypot(d[:, 0], d[:, 1])

    order = np.argsort(ang)
    a_s = ang[order]
    r_s = r[order]
    k = len(order)
    # 环形中位角距（采样密度的稳健估计）
    gaps = np.diff(np.concatenate([a_s, [a_s[0] + 2.0 * np.pi]]))
    delta = 1.5 * float(np.median(gaps))
    keep = np.ones(k, dtype=bool)
    for i in range(k):
        d_ang = (a_s - a_s[i] + np.pi) % (2.0 * np.pi) - np.pi  # 有向角差 (−π, π]
        near = np.abs(d_ang) <= delta
        if np.any(r_s[near] < r_s[i] - eps_mm):
            keep[i] = False  # 邻域内有显著更近的分支点 → 远分支，剔除
    return [int(order[i]) for i in range(k) if keep[i]]


def solve_edge_chain(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    m: int = 181,
    theta_range_deg: float = 40.0,
    normals=None,
    b_w: float = 0.0,
    n_z: int = 21,
) -> tuple[list[list[float]], list[float], list[int], list[bool]]:
    """K-2.8 刃形按**廓形列序**的单根链（模块③ B 方案 v2 输入）.

    与 compute_discrete_edge（内侧包络角序环）不同：本函数保留廓形参数顺序——
    廓形列序 = 刀齿工作面的物理顺序（右齿面→齿根弧→左齿面→齿顶弧折返），供
    开放轮廓（1/2齿根-齿侧-齿顶-齿侧-1/2齿根）按段组装。多根列取**就近连续**
    根（与上一链点 3D 距离最近；首列取第一个根）。

    斜齿（β_w≠0，2026-08-24）分派 compute_helical_edge：列序上链 = 左齿侧→
    顶刃（含 r_f−a 椭圆弧顶缝桥点）→右齿侧，桥点在 bridge_mask 标 True。

    Returns:
        (chain_pts, chain_phis, chain_cols, bridge_mask)
          - chain_pts[k]: 刃形点 [x, y, z]（坐标 T，共面 F=0，按列序）
          - chain_phis[k]: 接触转角 φ_t [rad]
          - chain_cols[k]: 母线廓形列号
          - bridge_mask[k]: 顶缝构造桥点标记（直齿恒 False）
    """
    if abs(plan.beta_w_deg) > 1e-12:
        if b_w <= 0:
            raise ValueError(f"斜齿刃形链需要 b_w>0（工件齿宽），当前 {b_w}")
        pts_c, phis_c, _, _, cols_c, _, _, br_c = compute_helical_edge(
            profile_pts, plan, rake, b_w=b_w, n_z=n_z,
            m=m, theta_range_deg=theta_range_deg, normals=normals,
        )
        return pts_c, phis_c, cols_c, br_c
    sigma = math.radians(plan.sigma_deg)
    theta_range = math.radians(theta_range_deg)
    phis = np.linspace(-theta_range, theta_range, m)
    phws = phis / plan.omega_ratio

    xs = np.array([pt[0] for pt in profile_pts], dtype=np.float64)
    ys = np.array([pt[1] for pt in profile_pts], dtype=np.float64)
    norms = normals if normals is not None else profile_normals(profile_pts)
    nxs = np.array([nm[0] for nm in norms], dtype=np.float64)
    nys = np.array([nm[1] for nm in norms], dtype=np.float64)

    Ms = chain_matrices(phis, phws, plan.a, sigma)
    P0 = transform_batch(Ms, xs, ys, np.zeros(len(profile_pts)))
    nt = rotate_normals_batch(Ms, nxs, nys)
    V0 = velocity_batch(phis, P0)
    g0 = np.sum(V0 * nt, axis=-1)
    sinS, cosS = math.sin(sigma), math.cos(sigma)
    cosphi = np.cos(phis)[:, None]
    sinphi = np.sin(phis)[:, None]
    gz = cosphi * sinS * nt[..., 0] - sinphi * sinS * nt[..., 1]
    F0 = rake.A * P0[..., 0] + rake.B * P0[..., 1] + rake.C * P0[..., 2] + rake.const
    Fz = (rake.A * sinphi * sinS + rake.B * cosphi * sinS + rake.C * cosS) * np.ones_like(g0)
    h = g0 * Fz - F0 * gz

    roots_per_col = all_sign_change_roots(phis, h)
    chain_pts: list[list[float]] = []
    chain_phis: list[float] = []
    chain_cols: list[int] = []
    prev = None
    for j, rs in enumerate(roots_per_col):
        if not rs:
            continue
        cands: list[list[float]] = []
        cand_phis: list[float] = []
        for k, t in rs:
            phi = float(phis[k] + t * (phis[k + 1] - phis[k]))
            Pr = P0[k, j] + t * (P0[k + 1, j] - P0[k, j])
            F0r = rake.A * Pr[0] + rake.B * Pr[1] + rake.C * Pr[2] + rake.const
            Fzr = rake.A * math.sin(phi) * sinS + rake.B * math.cos(phi) * sinS + rake.C * cosS
            if abs(Fzr) < 1e-12:
                continue
            zw = -F0r / Fzr
            col_vec = np.array([math.sin(phi) * sinS, math.cos(phi) * sinS, cosS])
            q = Pr + zw * col_vec
            cands.append([float(q[0]), float(q[1]), float(q[2])])
            cand_phis.append(phi)
        if not cands:
            continue
        if prev is None:
            pick = 0
        else:
            pick = min(
                range(len(cands)),
                key=lambda i: (cands[i][0] - prev[0]) ** 2
                + (cands[i][1] - prev[1]) ** 2
                + (cands[i][2] - prev[2]) ** 2,
            )
        chain_pts.append(cands[pick])
        chain_phis.append(cand_phis[pick])
        chain_cols.append(j)
        prev = cands[pick]
    return chain_pts, chain_phis, chain_cols, [False] * len(chain_pts)


def compute_discrete_edge(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    m: int = 181,
    theta_range_deg: float = 40.0,
    normals=None,
) -> tuple[list[list[float]], list[float], list[bool]]:
    """K-2.8 刃形 = 产形面 ∩ 前刀面：逐点解 g=0 ∧ F=0（消元 → h(φ)=0 求根）.

    根选择用就近连续追踪（track_edge_roots）：段交界尖角处分支不混合、不连桥线，
    消除顶刃↔侧刃交界折返自交（前刀面剖分/实体缝合的不良体根源）。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]，n 个
        plan: ProcessPlan（Σ/a/同步比）
        rake: RakeSurface（前刀面隐式方程）
        m: 运动离散数（刀具转角采样数）
        theta_range_deg: 刀具转角扫描范围 [°]，±θ_range

    Returns:
        (edge_pts, roots_phi, found, breaks_edge, edge_cols)
          - edge_pts[k]: 刃形点 [x, y, z]（前刀面平面内侧包络环序，坐标 T）
          - roots_phi[k]: 对应接触转角 φ_t [rad]
          - found[i]: 廓形点 profile_pts[i] 是否有非退化根（长度 = len(profile_pts)）
          - breaks_edge: 断段位置集合（内侧轮廓为无自交单环，恒空；留接口）
          - edge_cols[k]: 该刃形点的母线廓形列号（ffα 反变换对应用）
    """
    n = len(profile_pts)
    if n < 2:
        raise ValueError("齿廓点至少 2 个")
    if m < 3:
        raise ValueError("运动离散数 m 至少 3（中心差分 + 线性插值需 ≥3 采样）")
    if abs(plan.beta_w_deg) > 1e-12:
        raise ValueError(
            "斜齿工件刃形未支持（K-2.8 消元法依赖齿面对 z_w 仿射，仅直齿成立），请先查看产形面"
        )

    sigma = math.radians(plan.sigma_deg)
    theta_range = math.radians(theta_range_deg)
    phis = np.linspace(-theta_range, theta_range, m)
    phws = phis / plan.omega_ratio

    xs = np.array([pt[0] for pt in profile_pts], dtype=np.float64)
    ys = np.array([pt[1] for pt in profile_pts], dtype=np.float64)
    norms = normals if normals is not None else profile_normals(profile_pts)
    nxs = np.array([nm[0] for nm in norms], dtype=np.float64)
    nys = np.array([nm[1] for nm in norms], dtype=np.float64)

    Ms = chain_matrices(phis, phws, plan.a, sigma)
    P0 = transform_batch(Ms, xs, ys, np.zeros(n))     # (m, n, 3)
    nt = rotate_normals_batch(Ms, nxs, nys)           # (m, n, 3)
    V0 = velocity_batch(phis, P0)
    g0 = np.sum(V0 * nt, axis=-1)                     # (m, n)

    # gz = col'·n_t，col' = d/dφ(∂P/∂z_w) = (cosφ·sinΣ, −sinφ·sinΣ, 0)
    sinS = math.sin(sigma)
    cosS = math.cos(sigma)
    cosphi = np.cos(phis)[:, None]
    sinphi = np.sin(phis)[:, None]
    gz = cosphi * sinS * nt[..., 0] - sinphi * sinS * nt[..., 1]   # (m, n)

    # F0 = F(P0)；Fz = ∂F/∂z_w = A·sinφ·sinΣ + B·cosφ·sinΣ + C·cosΣ（仅 φ 依赖，(m,1) 列，广播到 (m,n)）
    F0 = rake.A * P0[..., 0] + rake.B * P0[..., 1] + rake.C * P0[..., 2] + rake.const  # (m, n)
    Fz = rake.A * sinphi * sinS + rake.B * cosphi * sinS + rake.C * cosS               # (m, 1)

    # 前刀面与齿面母线近平行（Fz 全程 ≈0）→ 几何退化，h≈0 无变号，显式报错而非静默空刃形
    if float(np.max(np.abs(Fz))) < 1e-6:
        raise ValueError("前刀面与齿面母线近平行（Fz≈0），无唯一刃形，请调整 γ₀/β_t")

    h = g0 * Fz - F0 * gz                             # (m, n)
    # 全根收集（段交界尖角处多分支）→ 多根回代 → 前刀面平面内侧包络轮廓
    # （刀齿材料须同时在产形面各叶内侧：交叉分支取内侧者，远分支点剔除——
    #   这是顶刃↔侧刃交界折返自交 / 实体缝合不良体的物理根除点）
    roots_per_col = all_sign_change_roots(phis, h)
    cols_f: list[int] = []
    ks_f: list[int] = []
    ts_f: list[float] = []
    phis_f: list[float] = []
    for j, rs in enumerate(roots_per_col):
        for k, t in rs:
            cols_f.append(j)
            ks_f.append(k)
            ts_f.append(t)
            phis_f.append(float(phis[k] + t * (phis[k + 1] - phis[k])))
    breaks_edge: set[int] = set()  # 内侧轮廓为无自交单环，无断点
    if not cols_f:
        return [], [], [False] * n, breaks_edge, []

    colv = np.array(cols_f)
    kkv = np.array(ks_f)
    ttv = np.array(ts_f)
    phiv = np.array(phis_f)

    # 多根回代（逐元素展开，遵循 transforms.py 崩溃规避纪律）
    P0r = P0[kkv, colv] + ttv[:, None] * (P0[kkv + 1, colv] - P0[kkv, colv])  # (K, 3)
    F0r = rake.A * P0r[:, 0] + rake.B * P0r[:, 1] + rake.C * P0r[:, 2] + rake.const  # (K,)
    Fzr = rake.A * np.sin(phiv) * sinS + rake.B * np.cos(phiv) * sinS + rake.C * cosS  # (K,)

    # 逐点退化（Fz≈0）剔除后回代 z_w*
    ok = np.abs(Fzr) >= 1e-12
    zw = np.where(ok, -F0r / np.where(ok, Fzr, 1.0), 0.0)
    col_vec = np.stack(
        [np.sin(phiv) * sinS, np.cos(phiv) * sinS, np.full(len(phiv), cosS)], axis=-1
    )  # (K, 3)
    edge_all = P0r + zw[:, None] * col_vec           # (K, 3)

    keep = inner_contour(edge_all, rake)             # 内侧包络环序下标
    edge_pts = [[float(v) for v in edge_all[j]] for j in keep]
    roots_phi = [float(phiv[j]) for j in keep]
    edge_cols = [int(colv[j]) for j in keep]

    # 覆盖语义：列有非退化根即命中（内侧轮廓丢点属分支交叉剔除，不算未覆盖）
    col_has = np.zeros(n, dtype=bool)
    col_has[colv[ok]] = True
    found_list = [bool(v) for v in col_has]
    return edge_pts, roots_phi, found_list, breaks_edge, edge_cols


def compute_helical_edge(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    b_w: float,
    n_z: int = 21,
    m: int = 181,
    theta_range_deg: float = 40.0,
    normals=None,
) -> tuple[list[list[float]], list[float], list[bool], set[int], list[int], list[bool], dict]:
    """斜齿刃形 = 产形面网格 ∩ 前刀面（数值求交路线，2026-08-24，K-2.8b）.

    直齿消元法依赖齿面对 z_w 仿射，斜齿螺旋面破坏之 → 改在（根修复后的）产形面
    (u,z) 网格上，对每个内部廓形列 u 沿 z 层求前刀面方程 F=A·x+B·y+C·z+const 的
    变号根（线性插值），得刃形点列。多次穿零（产形面回折）用链跟踪选物理叶：
    种子列 = 源半径最近 r_pw（该处刃形必过 rake.p_ref 邻域），根取离 p_ref 最近的
    穿越点；向两侧列推进取离上一根 z 最近的穿越，层跳变/无根处断段。

    残差（验收判据，<5μm）：
      - max_plane_um：刃形点 |F|×1000（F 已归一，n_rake 单位矢）
      - max_surface_um：抽样列在 z* 用解析扭转 θ(z*) 重算源点 + φ* 邻层插值链矩阵
        映射的独立点，与 z 向插值刃形点的距离 ×1000（z 插值收敛误差的独立估计）

    Returns:
        (edge_pts, roots_phi, found, breaks_edge, edge_cols, interior_mask, residual_stats)
          - found[i]：内部列 i 是否有刃形点（边界列恒 False，不入覆盖分母）
          - interior_mask[i]：列是否为齿面内部（r_prof 带 + 法向跳变，照抄 conjugate.py）
          - residual_stats：{max_plane_um, max_surface_um, n_check, pass(均<5μm)}
    """
    n = len(profile_pts)
    if n < 2:
        raise ValueError("齿廓点至少 2 个")
    if n_z < 2:
        raise ValueError("轴向层数 n_z 至少 2")
    if b_w <= 0:
        raise ValueError(f"斜齿刃形需要 b_w>0（齿宽），当前 {b_w}")

    # 斜齿接触根下限（照抄 conjugate.py：物理接触位远离 φ=0，±40° 扫不到）；
    # 实际 θ 窗口由扩程梯子逐档决定（见下）
    sigma = math.radians(plan.sigma_deg)

    xs = np.array([pt[0] for pt in profile_pts], dtype=np.float64)
    ys = np.array([pt[1] for pt in profile_pts], dtype=np.float64)
    norms = normals if normals is not None else profile_normals(profile_pts)

    # ── 内部列判据（2026-08-25 修订：全列开放，链尾由极角折返切割把关）──
    # 旧版 r_lo+3% 带想剔槽底弧（底刃构造域），但**直齿折返点本身落在弧前圆角
    # 带**（n=200 实测 col≈144，r≈r_lo+0.1）——3% 带=0.135mm 恰把折返点提前
    # ~3 列切掉：折返区 dθ/du 极陡（β5° 丢 2.56° 展布、链底抬高 1.6mm）→ 刀齿
    # 角宽缩窄 45% + 构造腿长坡（用户报侧刃变形/齿根坡状）。槽底弧列物理根与
    # F 穿越均存在（±360° 探针验证，接触位 φ*≈∓5° 在梯子窗口内），链跟踪可穿
    # 过折返进入弧段，随后按极角折返切割（见 _fold_cut）取上链——与直齿
    # build_tooth_loop 的 i_fold 切分同语义。r_hi 即工件齿根圆 r_f（gap 外边界）。
    r_prof = np.hypot(xs, ys)
    r_lo, r_hi = float(r_prof.min()), float(r_prof.max())
    interior_mask = [True] * n
    r_top = r_hi - plan.a  # 顶刃极限半径（工件齿根圆柱共轭极限，顶刃共轭贴此圆）
    n2 = np.array([(nm[0], nm[1]) for nm in norms], dtype=np.float64)

    # ── 产形面 (u,z) 网格 + z 向扩程梯子（**全方向变号根**）──
    # 刃形源点可越出 ±b_w/2（接触点轴向漂移，conjugate_gear _bw_scale=2 同
    # rationale）；大 β_w 更远（25° 实测 z*≈2.5×b_w）。梯子 (z_half, θ 窗口) 逐档
    # 扩（粗扫 ~0.05s/档），直到全部内部列出现 F 夹区间；θ 同步放宽（接触 φ 随 z 漂移）
    beta_w = math.radians(plan.beta_w_deg)
    tan_bw = math.tan(beta_w)

    # 根方向（2026-08-25 修订）：旧 contact_roots direction=−1（下降穿越）只覆盖
    # 齿侧共轭叶；**工件齿顶圆柱（廓形弧列）的共轭是上升穿越**——直齿路径用
    # all_sign_change_roots（双向）因此链完整（199/200 列），斜齿旧实现只取下降
    # 根，把整段齿根共轭轨迹（r≈r_w−a 恒定、θ 跨全齿宽 ~5.8°）丢掉：折返点提前
    # ~1.6mm、角宽随 β 递进缩窄（β5° 5.49°→3.16°、β10°→0.4°），齿根被构造长坡
    # 腿替代（用户报侧刃变形/齿根坡状）。伪 flare 远叶（r≈r_pt+12~21）与方向无
    # 关，由半径护栏拦截。实现：g、F 在 (φ, z, u) 网格上全量计算，所有变号根点
    # 按列组织，相邻 z 层按 φ 就近配对成根曲线，沿曲线找 F 变号 = 刃形候选。
    r_guard = plan.r_pt + 3.0 * (r_hi - r_lo)

    def _ladder_crossings(z_half: float, th_deg: float) -> dict[int, list[tuple[list[float], float, int]]]:
        """逐列全方向根曲线的 F 穿越点.

        Returns: {iu: [(pt3, φ, k)]}——pt3 为 F 线性插值后的 3D 刃形候选点，k 为
        粗层下标（细化夹区间用）。半径护栏内（杀远叶）；层间 φ 配对容差 = 2×φ 步长。
        """
        tr = math.radians(th_deg)
        ph = np.linspace(-tr, tr, m)
        Ms_l = chain_matrices(ph, ph / plan.omega_ratio, plan.a, sigma)
        zs_l = np.linspace(-z_half, z_half, n_z)
        Xl, Yl, Zl, NXl, NYl, NZl = helical_tooth_grid(
            profile_pts, norms, zs_l, plan.j_w, beta_w, plan.r_pw)
        Pl = transform_batch(Ms_l, Xl, Yl, Zl)                    # (m, n·n_z, 3)
        ntl = rotate_normals_batch_3d(Ms_l, NXl, NYl, NZl)
        G = np.sum(velocity_batch(ph, Pl) * ntl, axis=-1)         # (m, n·n_z)
        Fl = rake.A * Pl[..., 0] + rake.B * Pl[..., 1] + rake.C * Pl[..., 2] + rake.const
        sc = (G[:-1] * G[1:] <= 0) & (G[:-1] != G[1:])
        ii, jj = np.where(sc)
        if len(ii) == 0:
            return {}
        tt = G[:-1][ii, jj] / (G[:-1][ii, jj] - G[1:][ii, jj])
        phi_r = ph[ii] + tt * (ph[ii + 1] - ph[ii])
        pt_r = Pl[ii, jj] + tt[:, None] * (Pl[ii + 1, jj] - Pl[ii, jj])
        F_r = Fl[ii, jj] + tt * (Fl[ii + 1, jj] - Fl[ii, jj])
        rr = np.hypot(pt_r[:, 0], pt_r[:, 1])
        desc = G[1:][ii, jj] < G[:-1][ii, jj]      # 下降穿越 = 齿侧共轭叶
        # 上升根仅收弧列（r_prof 贴工件齿顶圆——齿根共轭轨迹所在）；齿侧列上的
        # 上升根是 flare 远叶的护栏内残余（19° 实测混入致 2D 极角回卷、链自交）
        cols_r = jj % n
        near_arc = r_prof[cols_r] < r_lo + 0.05 * (r_hi - r_lo)
        keep = (rr <= r_guard) & (desc | near_arc)
        phi_r, pt_r, F_r, jj = phi_r[keep], pt_r[keep], F_r[keep], jj[keep]
        per_col: dict[int, dict[int, list[tuple[float, float, list[float]]]]] = {}
        for a_ in range(len(jj)):
            iu_ = int(jj[a_]) % n
            k_ = int(jj[a_]) // n
            per_col.setdefault(iu_, {}).setdefault(k_, []).append(
                (float(phi_r[a_]), float(F_r[a_]), [float(v) for v in pt_r[a_]])
            )
        dphi_tol = 20.0 * math.pi / 180.0  # 层间 φ 配对容差：护栏内每层常单根（最近 φ
        # 不会错配）；根曲线随 z 漂移可达 ~3.3°/层（β10 实测）——紧容差会整列丢
        # 穿越。窗口回卷（真根越出 ±θ 窗口、层根跳到另一支，Δφ≈±139°）仍被拒。
        out: dict[int, list[tuple[list[float], float, int]]] = {}
        for iu_, layers in per_col.items():
            crs: list[tuple[list[float], float, int]] = []
            for k_, lst in layers.items():
                for f1, F1, p1 in lst:
                    nxt = layers.get(k_ + 1)
                    if not nxt:
                        continue
                    f2, F2, p2 = min(nxt, key=lambda r_: abs(r_[0] - f1))
                    if abs(f2 - f1) > dphi_tol or F1 * F2 > 0 or F1 == F2:
                        continue
                    t2 = F1 / (F1 - F2)
                    pt = [p1[j2] + t2 * (p2[j2] - p1[j2]) for j2 in range(3)]
                    crs.append((pt, f1 + t2 * (f2 - f1), k_))
            if crs:
                out[iu_] = crs
        return out

    # 梯子逐档求解但**保留最优档**：以「有根列数」为择优目标，无增益即停
    # （更早档 Δz/Δφ 更细，精度更高）
    best: tuple[int, dict, float, float] | None = None
    for z_half, th_deg in ((b_w, max(theta_range_deg, 120.0)), (1.5 * b_w, 150.0), (2.0 * b_w, 180.0), (3.0 * b_w, 240.0)):
        crossings = _ladder_crossings(z_half, th_deg)
        cnt = len(crossings)
        if best is None or cnt > best[0]:
            best = (cnt, crossings, th_deg, z_half)
        elif best[0] > 0:
            break  # 已有收获且无增益 → 更高档只会更粗，停（全 0 档继续爬——β25° 前两档空、第 3 档才有根）
    assert best is not None
    _, crossings, active_th_deg, active_z_half = best
    zs = np.linspace(-active_z_half, active_z_half, n_z)

    # ── 链跟踪选叶：种子=p_ref 最近；推进=上一根 z 最近；层跳>3 / 无根断段；
    #    每条链终结后从未选列中重新播种（左右两条齿面各成一段）──
    p_ref = np.array(rake.p_ref, dtype=np.float64)
    if not crossings:
        return [], [], [False] * n, set(), [], interior_mask, {
            "max_plane_um": 0.0, "max_surface_um": 0.0, "n_check": 0, "n_bridge": 0, "pass": False,
        }, []

    def _seed_cross(iu: int) -> tuple[list[float], float, int] | None:
        best_s, bd = None, None
        for pt, f, k in crossings[iu]:
            d = float(np.linalg.norm(np.array(pt) - p_ref))
            if bd is None or d < bd:
                best_s, bd = (pt, f, k), d
        return best_s

    def _nearest_cross(iu: int, ref_z: float, f_prev: float) -> tuple[list[float], float, int] | None:
        # 几何连续性代价：Δφ 的切向位移 r_pt·Δφ 与 Δz 合成（φ 是接触相位——刃形
        # 点随 φ 演进沿切向移动 r·Δφ）。分支混跳（Δφ 数十度 ≈ 数 mm）代价巨大，
        # 合法漂移（≤0.5°/列）微小——纯 z 就近在 19° 曾跟混支（2D 极角回卷 3 次）。
        best_n, bd = None, None
        for pt, f, k in crossings[iu]:
            df = f - f_prev
            while df > math.pi:
                df -= 2.0 * math.pi
            while df < -math.pi:
                df += 2.0 * math.pi
            d = math.hypot(plan.r_pt * df, pt[2] - ref_z)
            if bd is None or d < bd:
                best_n, bd = (pt, f, k), d
        return best_n

    chosen: dict[int, tuple[list[float], float, int]] = {}
    remaining = set(crossings.keys())
    while remaining:
        seed_col = min(remaining, key=lambda iu: abs(r_prof[iu] - plan.r_pw))
        pick = _seed_cross(seed_col)
        if pick is None:
            remaining.discard(seed_col)
            continue
        chosen[seed_col] = pick
        remaining.discard(seed_col)
        for direction in (1, -1):  # 从种子向两侧推进
            iu = seed_col
            ref_z = pick[0][2]
            ref_f = pick[1]
            j = iu + direction
            while 0 <= j < n:
                if j not in remaining:
                    break  # 已选/无根/边界列 → 本条链终结
                pick_j = _nearest_cross(j, ref_z, ref_f)
                if pick_j is None:
                    break
                chosen[j] = pick_j
                remaining.discard(j)
                ref_z = pick_j[0][2]
                ref_f = pick_j[1]
                iu = j
                j += direction
    order = sorted(chosen.keys())

    def _refine_cross(iu: int, k: int, pt0: list[float], f0: float) -> tuple[list[float], float, float]:
        """夹区间 [zs[k], zs[k+1]] 8 细分单列重解 → 细化 (刃形点, φ*, z*).

        粗层 Δz 可达 2~4mm，线性插值残差 μm~十 μm 级；单列细化成本可忽略
        （m×9 个点），精度由细分步长决定 → 亚 μm。根分支跟粗根 φ（全方向变号，
        就近续接——弧列的上升根同样可细化）。细化失败退粗根（残差护栏兜底）。
        """
        z0, z1 = float(zs[k]), float(zs[k + 1])
        zs_sub = np.linspace(z0, z1, 9)
        thetas = plan.j_w * zs_sub * tan_bw / plan.r_pw
        ct, st = np.cos(thetas), np.sin(thetas)
        pxs = xs[iu] * ct - ys[iu] * st
        pys = xs[iu] * st + ys[iu] * ct
        nrm_x, nrm_y = float(n2[iu][0]), float(n2[iu][1])
        nz_pt = -plan.j_w * (xs[iu] * nrm_y - ys[iu] * nrm_x) * tan_bw / plan.r_pw
        nn = math.sqrt(1.0 + nz_pt * nz_pt)
        NXs = (nrm_x * ct - nrm_y * st) / nn
        NYs = (nrm_x * st + nrm_y * ct) / nn
        NZs = np.full(9, nz_pt / nn)
        tr = math.radians(active_th_deg)
        ph = np.linspace(-tr, tr, m)
        Ms_l = chain_matrices(ph, ph / plan.omega_ratio, plan.a, sigma)
        Pl = transform_batch(Ms_l, pxs, pys, zs_sub)          # (m, 9, 3)
        ntl = rotate_normals_batch_3d(Ms_l, NXs, NYs, NZs)     # (m, 9, 3)
        G = np.sum(velocity_batch(ph, Pl) * ntl, axis=-1)      # (m, 9)
        F_s = rake.A * Pl[..., 0] + rake.B * Pl[..., 1] + rake.C * Pl[..., 2] + rake.const  # (m, 9)
        # 每子层取 φ 就近 f0 的变号根（跟随粗根分支），层间找 F 变号
        roots: list[tuple[float, float, list[float]]] = []
        for j in range(9):
            g_col = G[:, j]
            f_col = F_s[:, j]
            best_r = None
            for i2 in range(m - 1):
                g0, g1 = g_col[i2], g_col[i2 + 1]
                if g0 * g1 > 0 or g0 == g1:
                    continue
                t3 = g0 / (g0 - g1)
                f_r = ph[i2] + t3 * (ph[i2 + 1] - ph[i2])
                if best_r is None or abs(f_r - f0) < abs(best_r[0] - f0):
                    pt_r2 = Pl[i2, j] + t3 * (Pl[i2 + 1, j] - Pl[i2, j])
                    best_r = (float(f_r), float(f_col[i2] + t3 * (f_col[i2 + 1] - f_col[i2])), [float(v) for v in pt_r2])
            if best_r is not None:
                roots.append(best_r)
        best_k2, best_t2 = None, None
        for j in range(len(roots) - 1):
            fa_, Fa_, pa_ = roots[j]
            fb_, Fb_, pb_ = roots[j + 1]
            if abs(fa_ - fb_) > 0.2 or Fa_ * Fb_ > 0 or Fa_ == Fb_:
                continue
            t2 = Fa_ / (Fa_ - Fb_)
            if best_k2 is None:
                best_k2, best_t2 = j, t2
        if best_k2 is None:
            return [float(v) for v in pt0], float(f0), float(0.5 * (z0 + z1))
        fa_, Fa_, pa_ = roots[best_k2]
        fb_, Fb_, pb_ = roots[best_k2 + 1]
        t2 = best_t2
        pt = [pa_[j3] + t2 * (pb_[j3] - pa_[j3]) for j3 in range(3)]
        phi = float(fa_ + t2 * (fb_ - fa_))
        z_star = float(z0 + (best_k2 + t2) / 8.0 * (z1 - z0))
        return pt, phi, z_star

    edge_pts: list[list[float]] = []
    roots_phi: list[float] = []
    edge_cols: list[int] = []
    bridge_mask: list[bool] = []
    refined: dict[int, tuple[list[float], float, float]] = {}
    for iu in order:
        pt0, f0, k0 = chosen[iu]
        pt, phi, z_star = _refine_cross(iu, k0, pt0, f0)
        refined[iu] = (pt, phi, z_star)
        edge_pts.append(pt)
        roots_phi.append(phi)
        edge_cols.append(iu)
        bridge_mask.append(False)

    # ── 顶缝桥接：双段链（左上/右上）缺口两端均在顶区（齿上半段）且缺口 ≤8 列
    #    → 前刀面内 **椭圆基底 + 端部 Hermite 混合桥**成单条上链。中缝是渐开线↔
    #    圆角弧退化区（直齿同区折返，构造器同款处理）。端部切向匹配是必须的：
    #    常数半径椭圆弧（旧实现）与共轭端点方向不匹配——共轭侧刃到达端点时径向
    #    仍在爬升（真顶刃共轭可越 r_f−a 极限 0.3~1.0mm，Σ 离面接触），椭圆弧把
    #    径向行程挤进首末段 → 桥两端 ~60° 折角；但全切向 Hermite 又把中段顶成
    #    鼓包 → 混合窗两端取 Hermite（C1）、中段严格贴椭圆（平直带保形）。
    def _seam_bridge() -> tuple[int, int] | None:
        if len(order) < 8 or abs(rake.C) < 1e-9:
            return None
        runs: list[tuple[int, int]] = []
        s: int | None = None
        for iu in range(n):
            if iu in chosen and s is None:
                s = iu
            elif iu not in chosen and s is not None:
                runs.append((s, iu - 1))
                s = None
        if s is not None:
            runs.append((s, n - 1))
        if len(runs) != 2:
            return None
        (_, hi_a), (lo_b, _) = runs  # 左段尾 = 左顶点；右段首 = 右顶点
        if lo_b - hi_a - 1 > max(8, n // 4):
            return None  # 缺口过宽（非顶缝，疑链断裂；列数上限随采样密度缩放）
        j_l = edge_cols.index(hi_a)
        j_r = edge_cols.index(lo_b)
        # 切向估计需端点邻域共轭点（前向差分）：左端用 j_l−1（左段倒数第二点），
        # 右端用 j_r+1（右段第二点）；任一侧缺失则退化为弦方向
        if j_l < 1 or j_r + 1 >= len(edge_pts):
            return None
        pt_l, pt_r = edge_pts[j_l], edge_pts[j_r]
        r_l, r_r = math.hypot(pt_l[0], pt_l[1]), math.hypot(pt_r[0], pt_r[1])
        if r_l < plan.r_pt + 0.5 * (r_top - plan.r_pt) or r_r < plan.r_pt + 0.5 * (r_top - plan.r_pt):
            return None  # 缺口端点不在齿上半段（非顶缝）
        # 前刀面 2D 基（与 _trim_end_fold 同构）
        nv = [rake.A, rake.B, rake.C]
        nrm = math.sqrt(sum(c * c for c in nv))
        nv = [c / nrm for c in nv]
        be1 = [nv[1], -nv[0], 0.0]
        l1 = math.hypot(be1[0], be1[1])
        be1 = [c / l1 for c in be1] if l1 > 1e-12 else [1.0, 0.0, 0.0]
        be2 = [nv[1] * be1[2] - nv[2] * be1[1], nv[2] * be1[0] - nv[0] * be1[2], nv[0] * be1[1] - nv[1] * be1[0]]

        def _q2(pt):
            return (pt[0] * be1[0] + pt[1] * be1[1] + pt[2] * be1[2],
                    pt[0] * be2[0] + pt[1] * be2[1] + pt[2] * be2[2])

        q_l, q_r = _q2(pt_l), _q2(pt_r)
        q_lm, q_rm = _q2(edge_pts[j_l - 1]), _q2(edge_pts[j_r + 1])  # 邻域共轭点
        chord = math.hypot(q_r[0] - q_l[0], q_r[1] - q_l[1])
        if chord < 1e-9:
            return None
        # 桥 = 椭圆基底 + 端部混合窗 × Hermite 修正（bridge(t) = E + (H−E)·w(t)）：
        #   - 端部（w=1）：方向 = 共轭切向的 Hermite——消旧椭圆弧的 62° 折角
        #     （用户 2026-08-25 上午报实体侧刃↔顶刃交界尖角，根因是椭圆弧把径向
        #     行程挤进首末桥段、方向全错）；
        #   - 中段 [1/3, 2/3]（w=0）：严格贴常数半径椭圆弧——全切向 Hermite 会把
        #     缝顶成 0.18mm 鼓包（超缝端半径 +0.177mm、占弦长 26%），顶刃平直带
        #     变坡状隆起（用户 2026-08-25 下午报）；
        #   - 余弦坡 w′|窗端 = 0：全程 C1；端点处 H=E=q端 → 修正式导数 = H′。
        #   - 逐点钳制（违规回退纯椭圆弧）：偏离椭圆基底 ≤ 0.25×弦长、半径 ∈
        #     [min(r端)−0.1, max(r端)+0.3]——「掉头型」缝（19°，缝内含极角峰）
        #     共轭切向强拧时的护栏。
        t_l = [q_l[0] - q_lm[0], q_l[1] - q_lm[1]]
        t_r = [q_rm[0] - q_r[0], q_rm[1] - q_r[1]]
        lt = math.hypot(*t_l) or 1.0
        rt = math.hypot(*t_r) or 1.0
        # 切向幅值 = 0.8×弦长（方向 = 共轭方向不变 → 端部折角不受影响；幅值
        # 打八折压到达路径的端部越顶：满额弦长会把右端顶到缝端+0.10 以上）
        m_l = [t_l[0] / lt * chord * 0.8, t_l[1] / lt * chord * 0.8]
        m_r = [t_r[0] / rt * chord * 0.8, t_r[1] / rt * chord * 0.8]
        n_br = 17
        phi_l, phi_r = roots_phi[j_l], roots_phi[j_r]
        # 3D 重建原点：pt_l 对应 q_l → origin = pt_l − a·e1 − b·e2（桥点严格在前刀面上）
        ox = pt_l[0] - q_l[0] * be1[0] - q_l[1] * be2[0]
        oy = pt_l[1] - q_l[0] * be1[1] - q_l[1] * be2[1]
        oz = pt_l[2] - q_l[0] * be1[2] - q_l[1] * be2[2]
        # 椭圆基底参数（与回退弧同式：常数半径 = 缝两端均值，极角均匀插值）
        th_l = math.atan2(pt_l[1], pt_l[0])
        th_r = math.atan2(pt_r[1], pt_r[0])
        dth = ((th_r - th_l + math.pi) % (2.0 * math.pi)) - math.pi
        r_br = 0.5 * (r_l + r_r)

        def _ellipse_q2(th: float) -> tuple[float, float]:
            return _q2([r_br * math.cos(th), r_br * math.sin(th),
                        -(rake.A * r_br * math.cos(th) + rake.B * r_br * math.sin(th) + rake.const) / rake.C])

        def _wblend(tt: float) -> float:
            """端部混合窗：两端 plateau=1（纯 Hermite，端点方向精确续接）、
            [1/6,1/3] smoothstep 坡（w′|坡端=0 全程 C1）、中段 [1/3,2/3] 0（纯椭圆）.

            平台必须存在：坡状窗在末端 w<1，混合点够不到 Hermite 位置 → 端部
            方向只接了一半、剩余转折挤进最后一个桥段（56° 回退）。
            """

            def _ss(u: float) -> float:
                return u * u * (3.0 - 2.0 * u)

            if tt <= 1.0 / 6.0:
                return 1.0
            if tt <= 1.0 / 3.0:
                return _ss((1.0 / 3.0 - tt) * 6.0)
            if tt < 2.0 / 3.0:
                return 0.0
            if tt <= 5.0 / 6.0:
                return _ss((tt - 2.0 / 3.0) * 6.0)
            return 1.0

        r_ok_lo, r_ok_hi = min(r_l, r_r) - 0.1, max(r_l, r_r) + 0.3
        samples: list[tuple[float, float]] = []
        ok = True
        for j in range(1, n_br):
            tt = j / n_br
            t2 = tt * tt
            t3 = t2 * tt
            h00 = 2 * t3 - 3 * t2 + 1
            h10 = t3 - 2 * t2 + tt
            h01 = -2 * t3 + 3 * t2
            h11 = t3 - t2
            a2h = h00 * q_l[0] + h10 * m_l[0] + h01 * q_r[0] + h11 * m_r[0]
            b2h = h00 * q_l[1] + h10 * m_l[1] + h01 * q_r[1] + h11 * m_r[1]
            a2e, b2e = _ellipse_q2(th_l + tt * dth)
            ww = _wblend(tt)
            a2 = a2e + (a2h - a2e) * ww
            b2 = b2e + (b2h - b2e) * ww
            dev = math.hypot(a2 - a2e, b2 - b2e)
            rj = math.hypot(a2 * be1[0] + b2 * be2[0] + ox, a2 * be1[1] + b2 * be2[1] + oy)
            if dev > 0.25 * chord or not (r_ok_lo <= rj <= r_ok_hi):
                ok = False
                break
            samples.append((a2, b2))
        if not ok:
            # 回退：纯常数半径椭圆弧（旧实现，体积正确、端部拐角可容忍）
            samples = []
            for j in range(1, n_br):
                samples.append(_ellipse_q2(th_l + (j / n_br) * dth))
        for j, (a2, b2) in enumerate(samples, start=1):
            edge_pts.insert(j_l + j, [a2 * be1[0] + b2 * be2[0] + ox,
                                      a2 * be1[1] + b2 * be2[1] + oy,
                                      a2 * be1[2] + b2 * be2[2] + oz])
            roots_phi.insert(j_l + j, phi_l + (j / n_br) * (phi_r - phi_l))
            edge_cols.insert(j_l + j, hi_a)
            bridge_mask.insert(j_l + j, True)
        return (hi_a, lo_b)

    seam = _seam_bridge()

    # ── 极角折返切割（直齿 build_tooth_loop i_fold 同语义）：interior 全列开放
    #    后链会跟踪穿过折返点进入槽底弧（折返后刀具极角回落）——上链应止于极角
    #    极大处，其后为构造底刃域。折返点在弧前圆角带上，是刀齿角宽的主要贡献
    #    区（dθ/du 极陡），截在其前会齿瘦+长坡腿（2026-08-25 用户报侧刃变形）。
    if len(edge_pts) >= 3:
        th0 = math.atan2(edge_pts[0][1], edge_pts[0][0])
        rel = [((math.atan2(q[1], q[0]) - th0 + math.pi) % (2.0 * math.pi)) - math.pi for q in edge_pts]
        i_fold = max(range(len(rel)), key=rel.__getitem__)
        if 0 < i_fold < len(rel) - 1 and rel[i_fold] > rel[0] and rel[i_fold] > rel[-1]:
            n_keep = i_fold + 1
            del edge_pts[n_keep:]
            del roots_phi[n_keep:]
            del edge_cols[n_keep:]
            del bridge_mask[n_keep:]

    # ── 链端部 2D 折叠修剪（共轭底缘退化区的小回折；直齿同区即折返点、由
    #    build_tooth_loop 切分，斜齿链需等效前置处理）：从前刀面 2D 投影上找
    #    端部切向反转的极值点，截到极值——否则延伸腿穿过折叠簇产生自相交 ──
    def _trim_end_fold() -> None:
        nv = [rake.A, rake.B, rake.C]
        nrm = math.sqrt(sum(c * c for c in nv))
        nv = [c / nrm for c in nv]
        e1 = [nv[1], -nv[0], 0.0]
        l1 = math.hypot(e1[0], e1[1])
        e1 = [c / l1 for c in e1] if l1 > 1e-12 else [1.0, 0.0, 0.0]
        e2 = [nv[1] * e1[2] - nv[2] * e1[1], nv[2] * e1[0] - nv[0] * e1[2], nv[0] * e1[1] - nv[1] * e1[0]]

        def _q2(pt):
            return (pt[0] * e1[0] + pt[1] * e1[1] + pt[2] * e1[2],
                    pt[0] * e2[0] + pt[1] * e2[1] + pt[2] * e2[2])

        for _ in range(3):  # 端部可有多重小折，最多修 3 轮
            q = [_q2(p) for p in edge_pts]
            win = min(max(6, n // 12), len(q) // 4)  # 折叠簇窗口随采样密度缩放
            cut_h = cut_t = 0
            for k in range(min(win, len(q) - 3)):
                d1 = (q[k + 1][0] - q[k][0], q[k + 1][1] - q[k][1])
                d2 = (q[k + 2][0] - q[k + 1][0], q[k + 2][1] - q[k + 1][1])
                if d1[0] * d2[0] + d1[1] * d2[1] < 0:
                    cut_h = k + 1  # 极值点：新链首
                    break
            for k in range(min(6, len(q) - 3)):
                i = len(q) - 1 - k
                d1 = (q[i - 1][0] - q[i][0], q[i - 1][1] - q[i][1])
                d2 = (q[i - 2][0] - q[i - 1][0], q[i - 2][1] - q[i - 1][1])
                if d1[0] * d2[0] + d1[1] * d2[1] < 0:
                    cut_t = k + 1  # 极值点：新链尾
                    break
            if cut_h == 0 and cut_t == 0:
                return
            if cut_h:
                del edge_pts[:cut_h]
                del roots_phi[:cut_h]
                del edge_cols[:cut_h]
                del bridge_mask[:cut_h]
            if cut_t:
                n_keep = len(edge_pts) - cut_t
                del edge_pts[n_keep:]
                del roots_phi[n_keep:]
                del edge_cols[n_keep:]
                del bridge_mask[n_keep:]

    _trim_end_fold()

    found = [False] * n
    for iu in order:
        found[iu] = True
    breaks_edge: set[int] = set()
    if seam is not None:
        for iu in range(seam[0] + 1, seam[1]):
            found[iu] = True  # 桥接缝列经桥覆盖
    else:
        prev_iu = None
        for idx, iu in enumerate(edge_cols):
            if prev_iu is not None and iu != prev_iu + 1:
                breaks_edge.add(idx)  # 列序断裂（缺口未桥）→ 分段
            prev_iu = iu

    # ── 双残差（排除桥点：构造点不在产形面上，只保 |F|≈0 的平面性由构造保证）──
    max_plane_um = 0.0
    for pt, is_br in zip(edge_pts, bridge_mask):
        if is_br:
            continue
        f = rake.A * pt[0] + rake.B * pt[1] + rake.C * pt[2] + rake.const
        max_plane_um = max(max_plane_um, abs(f) * 1000.0)

    max_surface_um = 0.0
    n_check = 0
    sample = order[:: max(1, len(order) // 40)]  # 抽样 ≤40 列
    for iu in sample:
        pt, phi, z_star = refined[iu]
        theta = plan.j_w * z_star * tan_bw / plan.r_pw
        ct, st = math.cos(theta), math.sin(theta)
        px = xs[iu] * ct - ys[iu] * st
        py = xs[iu] * st + ys[iu] * ct
        M1 = chain_matrices(np.array([phi]), np.array([phi / plan.omega_ratio]), plan.a, sigma)
        q = (
            M1[0, 0, 0] * px + M1[0, 0, 1] * py + M1[0, 0, 2] * z_star + M1[0, 0, 3],
            M1[0, 1, 0] * px + M1[0, 1, 1] * py + M1[0, 1, 2] * z_star + M1[0, 1, 3],
            M1[0, 2, 0] * px + M1[0, 2, 1] * py + M1[0, 2, 2] * z_star + M1[0, 2, 3],
        )
        d = math.dist(q, pt) * 1000.0
        max_surface_um = max(max_surface_um, d)
        n_check += 1

    residual_stats = {
        "max_plane_um": round(max_plane_um, 4),
        "max_surface_um": round(max_surface_um, 4),
        "n_check": n_check,
        "n_bridge": int(sum(bridge_mask)),
        "pass": max_plane_um < 5.0 and max_surface_um < 5.0,
    }
    return (
        edge_pts, roots_phi, found, breaks_edge, edge_cols,
        interior_mask, residual_stats, bridge_mask,
    )


def split_flank_segments(
    edge_pts: list[list[float]],
    closed: bool,
    breaks: set[int] | list[int] = (),
) -> list[list[list[float]]]:
    """刃形点列 → 多段（半径极值处 + 根追踪断点处断开）.

    closed=True（内齿轮闭合齿槽廓形）：在半径极小(齿顶)/极大(齿根)两处断开，
    再按 breaks（track_edge_roots 的物理尖角断点）细分；
    closed=False（外齿轮开放单齿廓形）：在半径极大(齿顶)处断开，再按 breaks 细分。
    断点处不连桥线——顶刃↔侧刃交界的两分支根各自独立段，消除折返自交。

    Args:
        edge_pts: 刃形点列 [[x, y, z], ...]（按廓形顺序）
        closed: 廓形是否闭合（内齿轮 k_io=−1 为 True）
        breaks: 额外断段位置集合（edge_pts 下标域，在该点与其前一点之间断开）

    Returns:
        段列表（各自有序；空输入返回 []）
    """
    n = len(edge_pts)
    if n < 2:
        return [edge_pts] if n else []
    r = [math.hypot(p[0], p[1]) for p in edge_pts]
    imin = min(range(n), key=r.__getitem__)
    imax = max(range(n), key=r.__getitem__)
    if imin == imax:
        return [edge_pts]

    def cut_linear(seq: list[list[float]], cuts: set[int]) -> list[list[list[float]]]:
        cs = sorted({0, len(seq)} | {c for c in cuts if 0 < c < len(seq)})
        return [seq[cs[i]:cs[i + 1]] for i in range(len(cs) - 1) if cs[i + 1] - cs[i] >= 2]

    if closed:
        def arc(s: int, e: int) -> list[list[float]]:
            return edge_pts[s:e + 1] if s <= e else edge_pts[s:] + edge_pts[:e + 1]
        # 环两半各自再按断点细分（断点先转半环内下标）
        half1, half2 = arc(imin, imax), arc(imax, imin)
        br = set(breaks)
        cuts1 = {(b - imin) % n for b in br} - {0}
        cuts2 = {(b - imax) % n for b in br} - {0}
        return cut_linear(half1, cuts1) + cut_linear(half2, cuts2)
    tip = imax
    cuts = {c for c in breaks if 0 < c < n}
    if tip not in cuts and tip + 1 not in cuts:
        cuts.add(tip + 1)
    return cut_linear(edge_pts, cuts)


def _forward_closure_ffa(
    edge_pts: list[list[float]],
    roots_phi: list[float],
    edge_cols: list[int],
    profile_pts,
    plan: ProcessPlan,
) -> float:
    """ffα 闭环：刃形点经正向链（对应各自 φ_t）反变换，与源廓形点横向偏差取最大 [μm].

    每个刃形点 q 由 q = 工件→刀具链(φ_w=φ_t/ω, φ_t, a, Σ)·(p; z_w*) 得到（p 为廓形点
    横向分量，z_w* 为接触点轴向层），故 q 经 tool_to_workpiece_chain(φ_w, φ_t, a, Σ)
    应精确回到 (p_x, p_y, z_w*)——横向偏差即变换链「正向=反向逆」的数值自洽误差
    （非刃形绝对正确性，见模块 docstring ⚠️）。绝对正确性由刃形落在产形面（g=0 且
    F=0，构造保证）+ 双路线互检 + 算例1 输入自洽兜底（ADR-019）。
    edge_cols[k] 为该刃形点的母线廓形列号（多根内侧轮廓不再与 found 列一一对应）。
    """
    if not edge_pts:
        # 有限哨兵（μm），避免 Starlette JSONResponse(allow_nan=False) 序列化 inf 崩溃
        return 1e9
    sigma = math.radians(plan.sigma_deg)
    max_d = 0.0
    for pt, root, ci in zip(edge_pts, roots_phi, edge_cols):
        phi_w = root / plan.omega_ratio
        M = tool_to_workpiece_chain(phi_w, root, plan.a, sigma)
        q = apply_transform_batch(
            M, np.array([[pt[0]], [pt[1]], [pt[2]], [1.0]], dtype=np.float64)
        )
        prof = profile_pts[ci]
        d = math.hypot(q[0, 0] - prof[0], q[1, 0] - prof[1])
        if d > max_d:
            max_d = d
    return max_d * 1000.0  # mm → μm


def extract_edge(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    m: int = 181,
    theta_range_deg: float = 40.0,
    k_io: int = 1,
    normals=None,
    b_w: float = 0.0,
    n_z: int = 21,
) -> EdgeResult:
    """K-2.8 完整刃形管线：产形面∩前刀面刃形 + 覆盖 + ffα + 分左右两段.

    斜齿（β_w≠0）分派 compute_helical_edge（产形面网格数值求交，K-2.8b）：
    coverage 分母 = 齿面内部列（圆弧列无刃形是物理事实）、ffa_um=None（ffα 闭环
    第二批范围外）、residual_stats 携带双残差。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]
        plan: ProcessPlan
        rake: RakeSurface（前刀面隐式方程）
        m: 运动离散数
        theta_range_deg: 刀具转角扫描范围 [°]
        k_io: 内/外齿轮系数（决定廓形闭合与否：内齿轮 −1 闭合）
        b_w: 工件齿宽 [mm]（斜齿路径必需：产形面网格 z 范围）
        n_z: 轴向层数（斜齿路径用）

    Returns:
        EdgeResult（segments 左右两段 + coverage_report + ffα/残差）

    Raises:
        ValueError: 外齿轮（k_io=+1）未支持——运动链旋向/前刀面符号 T14 未销项
    """
    if k_io != -1:
        raise ValueError(
            "外齿轮（k_io=+1）刃形未支持：运动链旋向/前刀面符号 T14 未销项，请使用内齿轮（k_io=−1）"
        )
    if abs(plan.beta_w_deg) > 1e-12:
        if b_w <= 0:
            raise ValueError(f"斜齿刃形需要 b_w>0（工件齿宽），当前 {b_w}")
        edge_pts, roots_phi, found, breaks_edge, edge_cols, interior_mask, residual, _bridge = (
            compute_helical_edge(
                profile_pts, plan, rake, b_w=b_w, n_z=n_z,
                m=m, theta_range_deg=theta_range_deg, normals=normals,
            )
        )
        interior_idx = [i for i, ok in enumerate(interior_mask) if ok]
        uncovered = [
            {"profile_idx": i, "radius": float(r_prof_i)}
            for i, r_prof_i in zip(interior_idx, (math.hypot(profile_pts[i][0], profile_pts[i][1]) for i in interior_idx))
            if not found[i]
        ]
        n_interior = len(interior_idx)
        coverage = {
            "total_points": n_interior,
            "uncovered": uncovered,
            "coverage_ratio": (n_interior - len(uncovered)) / n_interior if n_interior else 1.0,
            "pass": len(uncovered) == 0,
        }
        segments = [
            EdgeSegment(pts=seg, continuity="continuous")
            for seg in split_flank_segments(edge_pts, closed=False, breaks=breaks_edge)
        ]
        return EdgeResult(
            segments=segments, coverage_report=coverage, ffa_um=None, residual_stats=residual,
        )
    edge_pts, roots_phi, found, breaks_edge, edge_cols = compute_discrete_edge(
        profile_pts, plan, rake, m=m, theta_range_deg=theta_range_deg, normals=normals
    )
    n = len(profile_pts)
    uncovered = [
        {"profile_idx": i, "radius": math.hypot(profile_pts[i][0], profile_pts[i][1])}
        for i in range(n) if not found[i]
    ]
    coverage = {
        "total_points": n,
        "uncovered": uncovered,
        "coverage_ratio": (n - len(uncovered)) / n if n else 1.0,
        "pass": len(uncovered) == 0,
    }
    ffa_um = _forward_closure_ffa(edge_pts, roots_phi, edge_cols, profile_pts, plan)

    segments = [
        EdgeSegment(pts=seg, continuity="continuous")
        for seg in split_flank_segments(edge_pts, closed=(k_io == -1), breaks=breaks_edge)
    ]
    return EdgeResult(segments=segments, coverage_report=coverage, ffa_um=ffa_um)

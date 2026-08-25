"""模块②b 等效产形齿轮 — 单齿槽产形面阵列 z_t 份 + 补齿顶/齿根回转面（纯数学）.

产形面（conjugate.py，K-2.6）是**单个齿槽**的左右两侧刃面（坐标 T，刀具动系），
并在「产形面绘制错误」修复中修剪掉了齿顶/齿根圆弧段（避免 G0 尖角法向污染 → 撕裂）。

本模块把这一片产形面绕刀具 z 轴旋转阵列 z_t 份，拼成**等效产形齿轮**——内齿轮工件
的一个齿槽 ↔ 产形齿轮（外齿轮凸齿）的一个齿，且同步比 ω_t/ω_w = z_w/z_t 保证单齿槽
产形面在刀具系 T 下占据角距 2π/z_t，故阵列 z_t 份正好铺满一整圈、无缝无重叠。

同时补回齿顶/齿根回转面（凸齿顶部 / 齿间底部），使齿轮外形闭合完整（用户选
「补齿顶/齿根圆柱面」）。产形面是桶形（半径随轴向 z 变化），故齿顶/齿根半径
r_top(z)/r_root(z) 随 z 层变化，从产形面**实际边界顶点**（T 系 hypot(x,y) 极值）提取，
而非工件端面 r_hi/r_lo（那是 trim 判据、坐标 W 端面）。

不依赖 OCCT。
"""

import math

import numpy as np

from core.common.mesh import compute_vertex_normals
from core.envelope.conjugate import ConjugateSurface, compute_conjugate_surface
from core.envelope.interference import swept_interference_colors
from core.envelope.process_plan import ProcessPlan


def _referenced_vertices(indices: list[int], n_vert: int) -> list[bool]:
    """从三角网索引反推「被引用」顶点掩码（未被索引引用的顶点不参与齿面渲染）."""
    ref = [False] * n_vert
    for i in indices:
        ref[i] = True
    return ref


def _layer_cap_endpoints(
    positions: list[float],
    referenced: list[bool],
    iz: int,
    n: int,
) -> tuple[int, int, int, int] | None:
    """提取第 iz 层的齿顶/齿根端点，返回 (top_a, top_b, root_a, root_b)（顶点 id）.

    凸齿（单齿槽产形面）每层是「V 形」半径分布（左齿面齿根→齿顶递增、右齿面齿顶
    →齿根递减），齿顶（凸齿顶部）↔ 工件齿槽齿根圆弧（r_hi）、齿根（齿间底部）↔
    齿顶圆弧（r_lo）。故取该层被引用顶点中 T 系半径 hypot(x,y) 最大 2 点为左右齿顶
    端、最小 2 点为左右齿根端。勿用极角最大间隙聚类——齿根空隙为环绕长弧（≈2π−齿
    槽角），会把整环误当成一段。
    """
    lo = iz * n
    hi = (iz + 1) * n
    ids = [v for v in range(lo, hi) if referenced[v]]
    if len(ids) < 4:
        return None
    items: list[tuple[int, float]] = []  # (v, radius)
    for v in ids:
        x = positions[3 * v]
        y = positions[3 * v + 1]
        items.append((v, math.hypot(x, y)))
    items.sort(key=lambda t: t[1], reverse=True)  # 半径降序
    top_a, top_b = items[0][0], items[1][0]        # 齿顶端（半径最大 2 个）
    root_a, root_b = items[-1][0], items[-2][0]    # 齿根端（半径最小 2 个）
    # 按极角升序排列端点对，保证跨层弧方向一致（否则相邻层弧方向翻转 → 三角折叠）
    top_a, top_b = _order_by_angle(positions, top_a, top_b)
    root_a, root_b = _order_by_angle(positions, root_a, root_b)
    return (top_a, top_b, root_a, root_b)


def _order_by_angle(positions: list[float], va: int, vb: int) -> tuple[int, int]:
    """按极角升序排列两个顶点 id（保证跨层齿顶/齿根弧走向一致）."""
    ta = math.atan2(positions[3 * va + 1], positions[3 * va])
    tb = math.atan2(positions[3 * vb + 1], positions[3 * vb])
    return (va, vb) if ta <= tb else (vb, va)


def _cap_arc_points(
    positions: list[float], va: int, vb: int, n_arc: int, contact_phi: list[float] | None = None
) -> tuple[list[list[float]], list[float]]:
    """生成连接顶点 va→vb 的圆弧 n_arc 个点（绕 z 轴短弧；端点精确复制、中间点线性插值半径/角/z）.

    产形面桶形 → 齿顶/齿根半径随层变化，中间点半径 r(t)=r0+t·(r1−r0) 线性过渡，
    保证端点与侧刃面边界顶点坐标精确重合（无缝）。同步返回各点接触角 φ_t
    （contact_phi[va]→[vb] 线性插值，供干涉着色啮合位反变换）。
    """
    x0, y0, z0 = positions[3 * va], positions[3 * va + 1], positions[3 * va + 2]
    x1, y1, z1 = positions[3 * vb], positions[3 * vb + 1], positions[3 * vb + 2]
    r0, r1 = math.hypot(x0, y0), math.hypot(x1, y1)
    th0, th1 = math.atan2(y0, x0), math.atan2(y1, x1)
    dth = ((th1 - th0 + math.pi) % (2.0 * math.pi)) - math.pi  # 短弧角差（|dth| ≤ π）
    ph0 = contact_phi[va] if contact_phi else 0.0
    ph1 = contact_phi[vb] if contact_phi else 0.0
    pts: list[list[float]] = [[x0, y0, z0]]
    phis: list[float] = [ph0]
    for j in range(1, n_arc - 1):
        t = j / (n_arc - 1)
        rj = r0 + t * (r1 - r0)
        th = th0 + t * dth
        z = z0 + t * (z1 - z0)
        pts.append([rj * math.cos(th), rj * math.sin(th), z])
        phis.append(ph0 + t * (ph1 - ph0))
    pts.append([x1, y1, z1])
    phis.append(ph1)
    return pts, phis


def _build_cap_face(
    positions: list[float],
    indices: list[int],
    n: int,
    n_z: int,
    mode: str,
    n_arc: int,
    contact_phi: list[float] | None = None,
) -> tuple[list[float], list[int], list[float]]:
    """生成单齿槽的齿顶(mode='top')或齿根(mode='root')弧面（相邻层弧连片直纹面）.

    返回 (positions_flat, indices, contact_phi_flat)。每层弧 n_arc 个点（端点复制自
    侧刃面边界顶点），相邻层弧连成 n_arc−1 段 × 2 三角的直纹回转面；contact_phi_flat
    为各点接触角（从侧刃面边界顶点插值，供干涉着色啮合位反变换）。
    """
    n_vert = len(positions) // 3
    referenced = _referenced_vertices(indices, n_vert)
    cap_pos: list[float] = []
    cap_idx: list[int] = []
    cap_phi: list[float] = []
    prev_base = -1
    for iz in range(n_z):
        ep = _layer_cap_endpoints(positions, referenced, iz, n)
        if ep is None:
            prev_base = -1
            continue
        top_a, top_b, root_a, root_b = ep
        va, vb = (top_a, top_b) if mode == "top" else (root_a, root_b)
        arc, phis = _cap_arc_points(positions, va, vb, n_arc, contact_phi)
        base = len(cap_pos) // 3
        for p in arc:
            cap_pos += p
        cap_phi += phis
        if prev_base >= 0:
            for j in range(n_arc - 1):
                a0 = prev_base + j
                a1 = prev_base + j + 1
                b0 = base + j
                b1 = base + j + 1
                cap_idx += [a0, a1, b0, a1, b1, b0]
        prev_base = base
    return cap_pos, cap_idx, cap_phi


def compute_conjugate_gear(
    profile_pts,
    plan: ProcessPlan,
    *,
    b_w: float,
    k_io: int,
    z_t: int,
    z_w: int,
    n_z: int = 21,
    m: int = 181,
    theta_range_deg: float = 40.0,
    normals=None,
    n_arc: int = 9,
    clamp_mm: float = 0.5,
) -> ConjugateSurface:
    """K-2.6 等效产形齿轮：单齿槽产形面阵列 z_t 份 + 补齿顶/齿根回转面（坐标 T）.

    返回的 mesh_colors 为扫掠最坏位干涉顶点色（红=干涉/橙黄=临界/绿→蓝=间隙/
    灰=齿宽外参考段），interference_stats 为色阶统计，供前端在「正常单色/干涉
    热力图」两样式间切换（材质切换，非独立图层）。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]（同时是符号距离的齿槽多边形）
        plan: ProcessPlan（Σ/a/同步比）
        b_w: 工件齿宽 [mm]
        k_io: 内/外齿轮系数（仅内齿轮 −1 产形面已支持）
        z_t: 刀具齿数（阵列份数）
        z_w: 工件齿数（全周向干涉折叠判定）
        n_z: 轴向层数
        m: 刀具转角采样数
        theta_range_deg: 刀具转角扫描范围 [°]
        n_arc: 每层齿顶/齿根弧采样点数（≥3）
        clamp_mm: 符号距离色阶饱和距离 [mm]（|d|≥clamp 即饱和红/蓝）

    Returns:
        ConjugateSurface（坐标 T；coverage 沿用单齿槽报告）

    Raises:
        ValueError: z_t < 1 / n_arc < 3 / clamp_mm ≤ 0
    """
    if z_t < 1:
        raise ValueError("刀具齿数 z_t 必须 ≥ 1")
    if n_arc < 3:
        raise ValueError("齿顶/齿根弧采样点 n_arc 至少 3")
    if clamp_mm <= 0:
        raise ValueError(f"色阶饱和距离 clamp_mm={clamp_mm} 必须 > 0")

    # 产形面轴向取 2 倍工件齿宽（桶形面完整段 + 干涉检测余量）。
    # 2026-08-20 校核修正：原 5× 扩展使 T 系轴向长达 ~125mm（工件 b_w=20mm 的 6 倍），
    # 边缘行啮合方程失根（覆盖率跌至 87.6%）、已命中点物理意义可疑（接触位漂移、
    # 半径塌缩）——视觉呈「长条穿刺工件」。2× 实测覆盖率 100%、轴向 ~50mm。
    _bw_scale = 2
    _n_z_conj = n_z * _bw_scale
    surf = compute_conjugate_surface(
        profile_pts, plan, b_w=b_w * _bw_scale, k_io=k_io,
        n_z=_n_z_conj, m=m,
        theta_range_deg=theta_range_deg, normals=normals,
        trim_fold=True,
    )
    single_pos = surf.mesh_positions
    single_idx = surf.mesh_indices
    n_vert = len(single_pos) // 3
    if n_vert == 0:
        return surf  # 空产形面直接返回（退化，覆盖报告已反映）

    n = n_vert // _n_z_conj  # 每层廓形点数（conjugate.py positions 行主序 index = iz·n + iu）

    top_pos, top_idx, top_phi = _build_cap_face(single_pos, single_idx, n, _n_z_conj, "top", n_arc, surf.mesh_contact_phi)
    root_pos, root_idx, root_phi = _build_cap_face(single_pos, single_idx, n, _n_z_conj, "root", n_arc, surf.mesh_contact_phi)

    # 合并单齿槽三件（侧刃面 + 齿顶面 + 齿根面）+ 各面接触角（供干涉着色）
    n_top = len(top_pos) // 3
    base_pos = single_pos + top_pos + root_pos
    base_idx = list(single_idx)
    base_idx += [i + n_vert for i in top_idx]
    base_idx += [i + n_vert + n_top for i in root_idx]
    base_phi = list(surf.mesh_contact_phi) + top_phi + root_phi
    n_base = len(base_pos) // 3

    # 干涉热力图顶点色：扫掠最坏位（每顶点沿自身接触窗 ±60° 取最深侵入）。
    # 旧静态 φ_t=0 快照有两缺陷：① 符号约定反了（齿槽空隙被当材料染红）；
    # ② 桶形面「待切削余量」大片呈现为红，无法与真实碰撞区分。改良后：
    # 全周向判定（z_w 齿槽折叠）+ 只在点进入工件齿宽（W 系 |z|≤b_w/2）的相位
    # 计入，工程色阶红=干涉/绿=贴合/蓝=间隙/灰=齿宽外参考段。
    # 着色只算单齿槽基准几何，阵列份逐点复制色。
    poly = np.array([(pt[0], pt[1]) for pt in profile_pts], dtype=np.float64)
    base_col, _stats = swept_interference_colors(
        base_pos, base_phi, plan, poly, b_w=b_w, z_w=z_w, clamp_mm=clamp_mm,
    )

    # 绕刀具 z 轴阵列 z_t 份（旋转只作用 (x,y)，颜色逐份复制，法向由合并后重算）
    delta = 2.0 * math.pi / z_t
    all_pos: list[float] = []
    all_col: list[float] = []
    all_idx: list[int] = []
    for k in range(z_t):
        c = math.cos(k * delta)
        s = math.sin(k * delta)
        for i in range(0, len(base_pos), 3):
            x, y, z = base_pos[i], base_pos[i + 1], base_pos[i + 2]
            all_pos += [x * c - y * s, x * s + y * c, z]
        all_col += base_col
        all_idx += [idx + k * n_base for idx in base_idx]

    normals = compute_vertex_normals(all_pos, all_idx)
    return ConjugateSurface(
        mesh_positions=all_pos,
        mesh_indices=all_idx,
        mesh_normals=normals,
        coverage=surf.coverage,
        interference_stats={**_stats, "clamp_mm": clamp_mm},
        mesh_colors=all_col,
    )

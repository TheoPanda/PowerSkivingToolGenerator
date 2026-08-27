"""模块③ K-3.1 预览级 — 单齿闭合实体（B 方案 v2，2026-08-21 用户方案）.

「预览级」指三角网伪实体（直接由网格拼装，非 OCCT 实体布尔），几何量本身按
公式施加；K-3.2 刀体结构（内孔/键槽/刃带等，W9 未回读）仍不在本层。

v1（r_hub 椭圆弧薄环带）的齿底呈片体，v2 按用户方案重做：刃形不做封闭环，
而是**开放轮廓** = 上链（1/2齿根-齿侧-齿顶-齿侧-1/2齿根，按廓形列序的共轭链）
+ 齿根延伸 + 径向偏置 + 圆弧闭合：

  - 上链 = 刃形共轭链的「齿侧+齿顶+齿侧」部分（列序 = 物理齿序，solve_edge_chain）；
    齿面共轭在啮合极限处折返（刀具极角反转、半径贴 r_a−a），折返链为共轭退化区。
  - 齿根延伸（「1/2齿根」）= 沿**理论极限圆** r_limit = r_a − a 的椭圆弧（前刀面 ∩
    极限圆柱）从左右折返点延伸到齿距线 θ_c ± π/z_t——每侧 ≈ 半齿谷，即工件齿顶
    圆柱在刀具系的包络面（真实根切/成形面，v1 缺失正是片体根源）。
  - 径向偏置 = 从两齿距线端点沿刀具径向（前刀面内）偏置 1/20 分度圆直径。
  - 圆弧闭合 = 偏置端点间的圆弧（圆心在齿中线，谷底朝轴凸）。
  - 整环阵列 z_t 份为**同相位周向阵列**（设计书 K-3.1 原义，与工件侧 ADR-002 同构）：
    单齿本体已是沿导程螺旋扫掠的条带（自带扭转），z_t 个条带绕 Z 纯旋转即拼成完整
    斜齿轮刀具体。勘误记录：TO-3/#34 曾施加逐齿轴向错位 ΔZ_i=i·π·m_n/sinβ_t·j_t，
    2026-08-27 用户实测证伪——那会把 L≈20mm 宽的单齿串成总跨度近千米的蜗杆状弹簧；
    错位语义属 hob 类单头螺纹排布，不适用于车齿刀，已回退。

后刀面（/flank）与单齿实体共用同一闭合轮廓（用户指定）。坐标标签 T；内部
rad / 接口 °。不依赖 OCCT。
"""

import math
from dataclasses import dataclass, field

from core.common.gltf_export import GeometrySpec
from core.common.mesh import compute_vertex_normals
from core.envelope.edge import solve_edge_chain
from core.envelope.process_plan import ProcessPlan
from core.envelope.rake import RakeSurface

ROOT_OFFSET_RATIO_DEFAULT = 1.0 / 20.0  # 齿根径向偏置 = 1/20 分度圆直径（用户选定）

_SIN_BETA_EPS = 1e-12  # sinβ 低于此值视为直齿（导程发散，纯轴向扫掠）


def helical_lead_mm(m_n: float, z_t: int, beta_t_deg: float) -> float:
    """螺旋导程 L_tp [mm]（K-2.15 螺旋导程法）：L_tp = z_t·π·m_n / sinβ_t.

    全仓单一权威源（原 /flank router 与 build_tooth_solid 各持一份公式，TO-3/#34
    收拢）。β_t→0 时导程发散（纯轴向扫掠），返回 math.inf，调用方自行退化处理
    （router 序列化为 null）。导程是后刀面螺旋扫掠链的真实几何参数；注意它不再
    用于整环阵列错位——K-3.1 阵列为同相位周向阵列（见模块 docstring 勘误记录）。
    """
    sin_b = math.sin(math.radians(beta_t_deg))
    if abs(sin_b) <= _SIN_BETA_EPS:
        return math.inf
    return z_t * m_n * math.pi / sin_b


def helical_sweep(poly, theta: float, dz: float) -> list[list[float]]:
    """折线绕 Z 轴转 theta [rad] + 沿 Z 平移 dz 的刚体螺旋运动（截面形状恒定）."""
    c = math.cos(theta)
    s = math.sin(theta)
    return [[c * x - s * y, s * x + c * y, z + dz] for (x, y, z) in poly]


@dataclass
class ToothLoop:
    """单齿前刀面闭合轮廓（坐标 T，共面于前刀面 F=0）."""

    pts: list[list[float]]  # 环形心极角升序（扇形剖分序）
    r_limit: float          # 理论极限最小刀具半径 r_a − a [mm]
    root_radius: float      # 谷底圆弧半径水平（≈ r_limit − 偏置量）[mm]
    offset_mm: float        # 径向偏置量 = ratio × 分度圆直径 [mm]
    theta_c: float          # 齿中线刀具极角 [rad]
    arch_spread_deg: float  # 上链（折返点间）刀具极角展布 [°]
    pitch_z_mm: float       # 单齿固有量：前刀面斜置下齿距线 ±π/z_t 两端的高差（非整环错位）[mm]
    arc_end_idx: tuple[int, int] = (0, 0)  # 偏置圆弧两端点（θ_c±π/z_t 侧）在 pts 中下标
    # 与 pts 等长：True = 齿底构造段（延伸/偏置/圆弧），False = 共轭上链（/edge 图层
    # 附加构造段线用——完整刃口 = 共轭上链 + 构造段；构造序下两段各自连续）
    constructed: list[bool] = field(default_factory=list)
    # 前刀面 2D 基下耳切三角化索引（CCW，法向 +n̂）：前后帽剖分用（v3 起替代扇形
    # 剖分——深谷轮廓非星形，扇形不适用）
    cap_indices: list[int] = field(default_factory=list)


@dataclass
class ToothSolid:
    """单齿闭合流形实体（坐标 T）."""

    mesh_positions: list[float]
    mesh_indices: list[int]
    mesh_normals: list[float]
    ribbon_indices: list[int]  # 仅侧面（后刀面用，= 全网格去前后帽）
    loop: ToothLoop
    volume_mm3: float   # 散度定理有向体积 [mm³]（> 0 = 绕向一致 outward）
    n_loop: int         # 每截面环点数 N（跨截面一致）
    n_sections: int     # n_L + 1


def limit_radius(r_a: float, a: float) -> float:
    """理论极限最小刀具半径 = r_a − a（工件齿顶圆 − 中心距，精确式）.

    刀具轴穿入工件齿顶圆柱内，最近距在 z=0 啮合平面（偏离后轴间距只增不减，
    Σ 斜角不伤）；齿根延伸面贴此极限圆 = 工件齿顶圆柱在刀具系的包络。

    Raises:
        ValueError: r_a − a ≤ 0
    """
    r_limit = r_a - a
    if r_limit <= 0:
        raise ValueError(f"理论极限半径 r_a−a = {r_limit:.4f} 必须 > 0（齿顶圆半径过小或中心距过大）")
    return r_limit


def _rake_basis_2d(rake: RakeSurface) -> tuple[list[float], list[float]]:
    """前刀面平面 2D 基（与 inner_contour 同构：e1 = n̂×ẑ、e2 = n̂×e1，右手系 e1×e2 = n̂）."""
    nv = [rake.A, rake.B, rake.C]
    nrm = math.sqrt(nv[0] * nv[0] + nv[1] * nv[1] + nv[2] * nv[2])
    nv = [c / nrm for c in nv]
    e1 = [nv[1], -nv[0], 0.0]  # n̂×ẑ
    l1 = math.hypot(e1[0], e1[1])
    if l1 < 1e-12:
        return [1.0, 0.0, 0.0], nv  # n ∥ ẑ 退化（e2 = n̂）
    e1 = [c / l1 for c in e1]
    e2 = [
        nv[1] * e1[2] - nv[2] * e1[1],
        nv[2] * e1[0] - nv[0] * e1[2],
        nv[0] * e1[1] - nv[1] * e1[0],
    ]
    return e1, e2


def _self_intersections_2d(q: list[tuple[float, float]]) -> int:
    """2D 闭环自相交线段对数（非相邻段严格相交）."""

    def cross(o, x, y):
        return (x[0] - o[0]) * (y[1] - o[1]) - (x[1] - o[1]) * (y[0] - o[0])

    def inter(a, b, c, d):
        d1, d2 = cross(c, d, a), cross(c, d, b)
        d3, d4 = cross(a, b, c), cross(a, b, d)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    n = len(q)
    return sum(
        1
        for i in range(n)
        for j in range(i + 2, n)
        if inter(q[i], q[(i + 1) % n], q[j], q[(j + 1) % n])
        and not (i == 0 and j == n - 1)
    )


def build_tooth_loop(
    chain_pts,
    rake: RakeSurface,
    *,
    z_t: int,
    r_pt: float,
    r_limit: float,
    offset_ratio: float = ROOT_OFFSET_RATIO_DEFAULT,
    n_arc: int = 17,
    n_ext: int = 4,
    n_off: int = 4,
    r_f: float | None = None,
    a: float | None = None,
    precut: bool = False,
    upper_constructed: list[bool] | None = None,
) -> ToothLoop:
    """B 方案 v7 单齿前刀面闭合轮廓：上链 + 1/2 齿根直腿 + 谷底圆弧.

    Args:
        chain_pts: 按廓形列序的刃形共轭链（solve_edge_chain 输出，坐标 T；含折返链，
            本函数在折返处切分，仅保留上链 [左折返点→齿侧→齿顶→齿侧→右折返点]）
        rake: RakeSurface（前刀面隐式方程）
        z_t: 刀具齿数（齿距线 = 齿中线 ± π/z_t）
        r_pt: 刀具节圆半径 [mm]（偏置量 = offset_ratio × 2 r_pt）
        r_limit: 理论极限最小刀具半径 r_a − a [mm]（limit_radius 输出）
        offset_ratio: 径向偏置 / 分度圆直径（默认 1/20，用户选定）
        n_arc: 谷底圆弧采样点数（含端点，≥3）
        n_ext: 每侧 1/2 齿根延伸弦直线细分点数（含端点，≥2）
        n_off: 每条径向偏置直线细分点数（含端点，≥2；直线细分仅为扫掠带加密）
        r_f / a: 工件齿根圆半径与中心距 [mm]（齿顶伪点判据 r_f−a 用；缺省跳过该判据）
        precut: 链已是上链（斜齿数值求交路线：compute_helical_edge 链跟踪 + 顶缝
            桥接产出，无底部折返段）——跳过折返检测；且**跳过 r_f−a 伪点判据**
            （斜齿合法顶刃共轭可越极限 0.3~1.0mm，Σ 交错轴离面接触；粗筛护栏
            已在 edge.py 拦 r≈70 伪支），仅保留极角递增贪心清洗
        upper_constructed: 上链逐点构造标记（斜齿顶缝桥点 True，与链等长；
            与链点一一对应，清洗时随点保留/剔除）

    Returns:
        ToothLoop（pts 为物理构造序闭环）

    Raises:
        ValueError: z_t<2 / |C|≈0 / 链过短 / 无折返 / 上链展布 ≥ 齿距 / 轮廓非简单
    """
    if z_t < 2:
        raise ValueError(f"刀具齿数 z_t={z_t} 至少 2（z_t=1 齿距线退化为整圆）")
    if abs(rake.C) < 1e-9:
        raise ValueError("前刀面法向 Z 分量 C=cosγ·cosβ_t≈0（γ₀→90°），椭圆弧退化")
    if offset_ratio <= 0:
        raise ValueError(f"径向偏置比 offset_ratio={offset_ratio} 必须 > 0")
    if n_arc < 3 or n_ext < 2 or n_off < 2:
        raise ValueError("采样点数不足（n_arc≥3 / n_ext≥2 / n_off≥2）")
    if len(chain_pts) < 8:
        raise ValueError(f"刃形链 {len(chain_pts)} 点至少 8（上链需含齿侧+齿顶）")

    # 折返切分：相对链首角的展开角取最大者 = 右折返点（其后为共轭退化折返链）
    th0 = math.atan2(chain_pts[0][1], chain_pts[0][0])
    rel = [((math.atan2(p[1], p[0]) - th0 + math.pi) % (2.0 * math.pi)) - math.pi for p in chain_pts]
    if precut:
        # 斜齿上链：极角「先升后降」是合法形态（螺旋导程使齿角位沿 z 漂移，19°
        # 实测 +0.8° 顶点 → −6.2° 尾），直齿的单调贪心会整侧误杀——跳过两判据
        # 清洗（伪支已由 edge.py 粗筛护栏拦；连续性由链跟踪保证，自交/耳切校验兜底）
        i_fold = len(chain_pts) - 1  # 链即上链（斜齿路线），无折返段
    else:
        i_fold = max(range(len(rel)), key=rel.__getitem__)
        if i_fold >= len(chain_pts) - 2 or i_fold < 2:
            raise ValueError("刃形链无折返点（极角未反转）：检查刃形覆盖或增大 theta_range")
    # 上链坏点清理（两判据互补，2026-08-21 用户反馈齿顶凸角/zigzag）：
    # ① 半径超限（优先，直齿专用）：多根列就近选根在共轭退化区跳到高支——半径超出工件
    #    槽底圆柱的共轭极限 r_f−a（算例1 真支贴极限 −0.6μm，伪支超 +24μm 起，
    #    判据 ε=10μm 分离充分）。伪点若不剔会以孤立凸角留在齿顶（且其 rel 局部
    #    峰会挤压邻点造成极角假回退）。斜齿（precut）跳过：合法顶刃共轭可越极限
    #    0.3~1.0mm（Σ 离面接触），伪支已由 edge.py 粗筛护栏拦截。
    # ② 极角回退（兜底）：跳分支产生的来回折线——上链要求刀具极角相对链首
    #    严格递增，贪心保留递增子列。
    if precut:
        upper = [list(q) for q in chain_pts]
        upper_con = [bool(b) for b in upper_constructed] if upper_constructed else [False] * len(chain_pts)
    else:
        n_over = 0
        if r_f is not None and a is not None:
            r_top_limit = r_f - a + 0.01
            for i in range(i_fold + 1):
                if math.hypot(chain_pts[i][0], chain_pts[i][1]) > r_top_limit:
                    rel[i] = -math.pi  # 标记为必删（比任何 rel 都小，② 一并剔除）
                    n_over += 1
            if n_over:
                print(f"[tooth_solid] 上链剔除齿顶超限伪点 {n_over} 个（r > r_f−a+10μm，共轭高支伪点）")
        upper = [list(chain_pts[0])]
        upper_con = [bool(upper_constructed[0]) if upper_constructed else False]
        rel_kept = rel[0]
        n_bad = 0
        for i in range(1, i_fold + 1):
            if rel[i] > rel_kept:
                upper.append(list(chain_pts[i]))
                upper_con.append(bool(upper_constructed[i]) if upper_constructed else False)
                rel_kept = rel[i]
            else:
                n_bad += 1
        if n_bad:
            print(f"[tooth_solid] 上链剔除极角回退坏点 {n_bad} 个（共轭退化区跳分支）")

    half = math.pi / z_t
    if precut:
        # 斜齿链极角非单调（先升后降）：展布/中心取链的全角域（首尾差会低估展布）
        rel_lo, rel_hi = min(rel), max(rel)
        span = rel_hi - rel_lo
        theta_c = th0 + 0.5 * (rel_lo + rel_hi)
    else:
        th_L = th0
        th_R = math.atan2(upper[-1][1], upper[-1][0])
        span = th_R - th_L
        theta_c = 0.5 * (th_L + th_R)
    if span >= 2.0 * half:
        raise ValueError(
            f"上链展布 {math.degrees(span):.3f}° ≥ 齿距 {math.degrees(2 * half):.3f}°"
            f"（相邻刀齿重叠）：检查 z_t 或刃形覆盖"
        )

    def ellipse_pt(t: float, radius: float) -> list[float]:
        """半径 radius 的刀具圆柱 ∩ 前刀面（解析椭圆弧上的点，极角 t）."""
        z = -(rake.A * radius * math.cos(t) + rake.B * radius * math.sin(t) + rake.const) / rake.C
        return [radius * math.cos(t), radius * math.sin(t), z]

    def ellipse(t: float) -> list[float]:
        return ellipse_pt(t, r_limit)

    # v7 齿根直腿（2026-08-21 用户反馈「丢了 1/2 齿根、阵列有缝」）：恢复 1/2 齿根
    # 延伸（折返角 → 齿距线，阵列相位闭合无缝）但**直线化**——延伸段用弦直线替代
    # 极限圆弧（圆心角 ≈1.6°，弦弧距 ≈4μm 无损；用户报「折线」即旧弧采样折线），
    # 偏置段保持径向直线（P→Q 同极角，XY 投影严格径向）。全腿 = 两直线段。
    d_off = offset_ratio * 2.0 * r_pt
    r_root = r_limit - d_off
    if r_root <= 0.0:
        raise ValueError(
            f"偏置过大：谷底半径 r_limit−偏置 = {r_root:.4f} ≤ 0（offset_ratio={offset_ratio}）"
        )
    # 齿距线就近分配：P_L 连链首（ext_L）、P_R 连链尾（ext_R）。直齿链极角升序
    # （首在低角）→ 默认序不变；斜齿链极角可反向（19° 实测首在 +0.8°、尾 −6.2°）
    # → 首尾就近交换，否则延伸腿横穿整条链（自相交）。
    th_head = math.atan2(upper[0][1], upper[0][0])
    th_tail = math.atan2(upper[-1][1], upper[-1][0])

    def _ang_dist(x: float, y: float) -> float:
        return abs(((x - y + math.pi) % (2.0 * math.pi)) - math.pi)

    t_plus, t_minus = theta_c + half, theta_c - half
    if _ang_dist(th_head, t_minus) + _ang_dist(th_tail, t_plus) > _ang_dist(th_head, t_plus) + _ang_dist(th_tail, t_minus):
        t_head, t_tail = t_plus, t_minus  # 反向链：首就近高端齿距线
    else:
        t_head, t_tail = t_minus, t_plus
    P_L, P_R = ellipse(t_head), ellipse(t_tail)                        # 齿距线极限圆点（L=首侧 / R=尾侧）
    Q_L = ellipse_pt(t_head, r_root)                                   # 齿距线谷底半径点
    Q_R = ellipse_pt(t_tail, r_root)

    def lerp(a: list[float], b: list[float], n: int) -> list[list[float]]:
        return [
            [a[k] + (b[k] - a[k]) * j / (n - 1) for k in range(3)]
            for j in range(n)
        ]

    ext_R = lerp(upper[-1], P_R, n_ext)   # 1/2 齿根延伸弦直线（右）
    ext_L = lerp(P_L, upper[0], n_ext)    # 左（P_L → 折返点序）
    off_R = lerp(P_R, Q_R, n_off)[1:-1]   # 径向偏置直线内部点
    off_L = lerp(Q_L, P_L, n_off)[1:-1]
    # 谷底圆弧：v6 反向保留——凸侧背离刀具轴（模仿轴心齿底圆：弧在弦外靠材料侧）
    arc = _valley_arc(Q_R, Q_L, rake, n_arc)

    # 物理构造序闭环（v3，2026-08-21）：废弃形心极角重排——深谷轮廓（谷底半径
    # r_limit−偏置 vs 拱顶半径差大）相对点平均形心**非星形**（形心被构造点拉向
    # 谷底、贴近腿端），极角序 ≠ 物理边界序，重排产生穿插锯齿形实体。构造序 =
    # 物理边界遍历序（上链→右延伸→右偏置→谷底弧→左偏置→左延伸→回链首），
    # 前后帽用耳切三角化（任意简单多边形，不要求星形）。
    pts: list[list[float]] = [list(p) for p in upper]
    pts += [list(p) for p in ext_R[1:]]   # 右延伸弦直线（去重折返点）
    pts += [list(p) for p in off_R]       # 右径向偏置内部
    pts += [list(p) for p in arc]         # 谷底弧（含 Q_R/Q_L 端点）
    pts += [list(p) for p in off_L]       # 左径向偏置内部（Q_L → P_L）
    pts += [list(p) for p in ext_L[:-1]]  # 左延伸弦直线（去重链首）
    n_upper = len(upper)
    seg_flags = list(upper_con) + [True] * (len(pts) - n_upper)  # 上链桥点 + 底构造段均标构造
    hi_idx = n_upper + (len(ext_R) - 1) + len(off_R)  # 弧首 Q_R
    lo_idx = hi_idx + len(arc) - 1                    # 弧尾 Q_L

    e1, e2 = _rake_basis_2d(rake)
    q2 = [
        (p[0] * e1[0] + p[1] * e1[1] + p[2] * e1[2],
         p[0] * e2[0] + p[1] * e2[1] + p[2] * e2[2])
        for p in pts
    ]
    if _self_intersections_2d(q2) > 0:
        raise ValueError("闭合轮廓自相交：请检查刃形链或增大 offset_ratio")
    cap_idx = _ear_clip_indices(q2)
    if len(cap_idx) != 3 * (len(pts) - 2):
        raise ValueError(
            f"闭合轮廓耳切三角化不完整（{len(cap_idx) // 3} 三角 ≠ {len(pts) - 2}）："
            "轮廓非简单多边形，请检查刃形链或增大 offset_ratio"
        )

    pitch_z = abs(ellipse(theta_c + half)[2] - ellipse(theta_c - half)[2])
    return ToothLoop(
        pts=pts,
        r_limit=r_limit,
        root_radius=r_limit - d_off,
        offset_mm=d_off,
        theta_c=theta_c,
        arch_spread_deg=math.degrees(span),
        pitch_z_mm=pitch_z,
        arc_end_idx=(hi_idx, lo_idx),
        constructed=seg_flags,
        cap_indices=cap_idx,
    )


def _ear_clip_indices(q: list[tuple[float, float]]) -> list[int]:
    """简单多边形耳切三角化（v3：深谷轮廓非星形，扇形剖分不适用）.

    输出三角索引相对原顶点序、统一为 2D 基下的 CCW（法向 +n̂，e1×e2 = n̂）。
    纯 O(n²) 逐点测试（n≈180，前刀面剖分仅此一次）。完整性由调用方校验
    （3·(n−2) 个索引；退化/非简单多边形产不出完整三角）。
    """
    n = len(q)
    if n < 3:
        return []
    idx = list(range(n))
    area2 = sum(q[i][0] * q[(i + 1) % n][1] - q[(i + 1) % n][0] * q[i][1] for i in range(n))
    if area2 < 0:
        idx.reverse()  # 统一 CCW（输出相对原顶点号）

    tris: list[int] = []
    guard = 0
    while len(idx) > 3 and guard < 4 * n:
        guard += 1
        m = len(idx)
        clipped = False
        for k in range(m):
            i0, i1, i2 = idx[(k - 1) % m], idx[k], idx[(k + 1) % m]
            a, b, c = q[i0], q[i1], q[i2]
            cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cr <= 1e-14:
                continue  # 凹角/共线，非耳
            ok = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                px, py = q[j]
                d1 = (b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0])
                d2 = (c[0] - b[0]) * (py - b[1]) - (c[1] - b[1]) * (px - b[0])
                d3 = (a[0] - c[0]) * (py - c[1]) - (a[1] - c[1]) * (px - c[0])
                if d1 >= -1e-12 and d2 >= -1e-12 and d3 >= -1e-12:
                    ok = False  # 三角形内含其它顶点，非耳
                    break
            if ok:
                tris += [i0, i1, i2]
                del idx[k]
                clipped = True
                break
        if not clipped:
            break  # 数值退化（调用方以完整性校验兜底）
    if len(idx) == 3:
        tris += idx
    return tris


def _valley_arc(
    Q_R: list[float], Q_L: list[float], rake: RakeSurface, n_arc: int
) -> list[list[float]]:
    """谷底圆弧（v6 反向）：弦垂直平分线上取**靠刀具轴**侧圆心，凸侧背离轴.

    方向裁定（2026-08-21 用户反馈「方向反了」）：齿底应模仿以轴心的齿底圆——
    弧在弦**外**（靠材料侧、离轴侧凸），曲率中心在轴侧；v3-v5 取背离轴侧圆心
    使弧退向轴侧，与齿底圆方向相反。R = 2.2 × 弦/2 浅圆角。退化（弦≈0 / R 域
    失败）回退直线段。
    """
    chord = math.dist(Q_R, Q_L)
    fallback = [
        [Q_R[k] + (Q_L[k] - Q_R[k]) * j / (n_arc - 1) for k in range(3)]
        for j in range(n_arc)
    ]
    if chord < 1e-9:
        return [list(Q_R)]
    nv = [rake.A, rake.B, rake.C]
    nl = math.sqrt(nv[0] ** 2 + nv[1] ** 2 + nv[2] ** 2)
    nv = [v / nl for v in nv]
    d = [Q_R[k] - Q_L[k] for k in range(3)]
    w = [
        nv[1] * d[2] - nv[2] * d[1],
        nv[2] * d[0] - nv[0] * d[2],
        nv[0] * d[1] - nv[1] * d[0],
    ]
    wl = math.sqrt(w[0] ** 2 + w[1] ** 2 + w[2] ** 2)
    if wl < 1e-12:  # 弦 ∥ 前刀面法向（不可能但守卫）
        return fallback
    w = [v / wl for v in w]
    mid = [0.5 * (Q_R[k] + Q_L[k]) for k in range(3)]
    R = 2.2 * chord / 2.0  # 浅圆角（深 ≈ 0.7mm @算例1；1.15 时深 1.76mm 偏凸，用户反馈调浅）
    disc = R * R - (chord / 2.0) ** 2
    if disc <= 1e-12:
        return fallback
    h = math.sqrt(disc)
    c = min(
        ([mid[k] + s * h * w[k] for k in range(3)] for s in (1.0, -1.0)),
        key=lambda p: math.hypot(p[0], p[1]),  # 靠刀具轴侧（|c_xy| 小者）→ 凸侧背离轴
    )
    v1 = [Q_R[k] - c[k] for k in range(3)]
    v2 = [Q_L[k] - c[k] for k in range(3)]
    R = math.sqrt(sum(v * v for v in v1))
    dot = sum(v1[k] * v2[k] for k in range(3))
    ang = math.acos(max(-1.0, min(1.0, dot / (R * R)))) if R > 1e-12 else 0.0
    nv = [
        v1[1] * v2[2] - v1[2] * v2[1],
        v1[2] * v2[0] - v1[0] * v2[2],
        v1[0] * v2[1] - v1[1] * v2[0],
    ]
    nnv = math.sqrt(sum(v * v for v in nv))
    if R < 1e-9 or ang < 1e-9 or nnv < 1e-12:
        return fallback
    nv = [v / nnv for v in nv]
    perp = [
        nv[1] * v1[2] - nv[2] * v1[1],
        nv[2] * v1[0] - nv[0] * v1[2],
        nv[0] * v1[1] - nv[1] * v1[0],
    ]
    out: list[list[float]] = []
    for j in range(n_arc):
        a = ang * j / (n_arc - 1)
        ca, sa = math.cos(a), math.sin(a)
        out.append([c[k] + v1[k] * ca + perp[k] * sa for k in range(3)])
    # 端点钉死为精确 Q_R/Q_L（重建端点 ~1e-7 漂移会破坏水密）
    out[0] = list(Q_R)
    out[-1] = list(Q_L)
    return out


def _signed_volume(positions: list[float], indices: list[int]) -> float:
    """闭合三角网有向体积（散度定理）."""
    vol = 0.0
    for t in range(len(indices) // 3):
        a, b, c = indices[3 * t], indices[3 * t + 1], indices[3 * t + 2]
        ax, ay, az = positions[3 * a], positions[3 * a + 1], positions[3 * a + 2]
        bx, by, bz = positions[3 * b], positions[3 * b + 1], positions[3 * b + 2]
        cx, cy, cz = positions[3 * c], positions[3 * c + 1], positions[3 * c + 2]
        vol += (
            ax * (by * cz - bz * cy)
            + ay * (bz * cx - bx * cz)
            + az * (bx * cy - by * cx)
        )
    return vol / 6.0


def build_tooth_solid(
    loop: ToothLoop,
    rake: RakeSurface,
    *,
    m_n: float,
    beta_t_deg: float,
    z_t: int,
    L: float,
    n_L: int,
) -> ToothSolid:
    """单齿闭合流形实体：前帽（耳切）+ 闭环 ribbon × n_L + 后帽（截面恒定螺旋扫掠）.

    截面 i = 基环绕 Z 转 −2π·dL_i/Ltp + 平移 −dL_i（K-2.15/16 螺旋导程法同款
    刚体运动；β_t=0 时 Ltp→∞ 退化为纯轴向平移，几何精确）。前后帽用前刀面 2D
    耳切索引（loop.cap_indices，CCW/+n̂）；绕向全局自适应（散度体积 < 0 时整体
    反转，保证 outward 定向）。

    Raises:
        ValueError: L ≤ 0 / n_L < 1 / 耳切索引缺失
    """
    if L <= 0:
        raise ValueError(f"总重磨量 L={L} 必须 > 0")
    if n_L < 1:
        raise ValueError(f"等分数 n_L={n_L} 必须 ≥ 1")
    if len(loop.cap_indices) != 3 * (len(loop.pts) - 2):
        raise ValueError("cap_indices 缺失或不完整（build_tooth_loop 未正常执行）")

    lead = helical_lead_mm(m_n=m_n, z_t=z_t, beta_t_deg=beta_t_deg)

    n = len(loop.pts)

    def sweep_angle(dL: float) -> float:
        return 0.0 if math.isinf(lead) else -2.0 * math.pi * dL / lead

    # 顶点布局：前帽独立副本（n）+ (n_L+1) 截面环 + 后帽独立副本（n）。
    # 帽独立顶点取纯平面法向（硬边）：帽盖与 ribbon 不共享法向——否则边界顶点
    # 法向被 ribbon 平均倾斜，平滑着色下耳切长对角线在共面帽上显形为斜线
    # （用户报「前刀面斜线/两平面」根因之一）；刃口本应是尖锐硬边。
    sections: list[list[list[float]]] = []
    for i in range(n_L + 1):
        dL = i * L / n_L
        sections.append(loop.pts if i == 0 else helical_sweep(loop.pts, sweep_angle(dL), -dL))

    positions: list[float] = []
    for p in loop.pts:  # F 块：前帽独立副本（截面 0 坐标）
        positions += p
    for sec in sections:  # S 块：ribbon 截面环
        for p in sec:
            positions += p
    for p in sections[-1]:  # B 块：后帽独立副本（截面 n_L 坐标）
        positions += p
    base_s = n
    base_b = n + (n_L + 1) * n

    def _flip(tri_list: list[int]) -> list[int]:
        """逐三角反转绕向 [a,b,c] → [a,c,b]."""
        out: list[int] = []
        for t in range(0, len(tri_list), 3):
            out += [tri_list[t], tri_list[t + 2], tri_list[t + 1]]
        return out

    cap = loop.cap_indices
    # 帽绕向跟随环点序：环点序在前刀面 2D 基下 CCW（有向面积 > 0）→ 前帽 +n̂、
    # 后帽 −n̂（直齿原约定）；斜齿链极角可反向（19° 实测 CW）→ 前后帽翻转跟随
    # ribbon 绕向，否则帽/ribbon 边界定向冲突（水密性判据「每边 2 次反向」失败）。
    # 全局 outward 由下方散度体积自适应翻转兜底。
    e1b, e2b = _rake_basis_2d(rake)
    area2 = 0.0
    for i in range(n):
        q0 = loop.pts[i]
        q1 = loop.pts[(i + 1) % n]
        x0 = q0[0] * e1b[0] + q0[1] * e1b[1] + q0[2] * e1b[2]
        y0 = q0[0] * e2b[0] + q0[1] * e2b[1] + q0[2] * e2b[2]
        x1 = q1[0] * e1b[0] + q1[1] * e1b[1] + q1[2] * e1b[2]
        y1 = q1[0] * e2b[0] + q1[1] * e2b[1] + q1[2] * e2b[2]
        area2 += x0 * y1 - x1 * y0
    cw = area2 < 0.0
    cap_front = _flip(list(cap)) if cw else list(cap)
    ribbons: list[int] = []
    for i in range(n_L):
        base = base_s + i * n
        nxt = base_s + (i + 1) * n
        for j in range(n):
            j2 = (j + 1) % n
            ribbons += [base + j, nxt + j2, base + j2]
            ribbons += [base + j, nxt + j, nxt + j2]

    indices = cap_front + ribbons + [base_b + t for t in (cap if cw else _flip(cap))]
    if _signed_volume(positions, indices) < 0:
        # 全局定向反转：绕向约定不一致时保证 outward（散度体积 > 0）
        indices = _flip(indices)
        ribbons = _flip(ribbons)

    def _group_face_normal(tri: list[int]) -> list[float]:
        """三角组面积加权面法向（共面帽 → 均匀单一法向，硬边用）."""
        sx = sy = sz = 0.0
        for t in range(0, len(tri), 3):
            a, b, c = tri[t], tri[t + 1], tri[t + 2]
            ax, ay, az = positions[3 * a], positions[3 * a + 1], positions[3 * a + 2]
            bx, by, bz = positions[3 * b], positions[3 * b + 1], positions[3 * b + 2]
            cx, cy, cz = positions[3 * c], positions[3 * c + 1], positions[3 * c + 2]
            e1 = (bx - ax, by - ay, bz - az)
            e2 = (cx - ax, cy - ay, cz - az)
            sx += e1[1] * e2[2] - e1[2] * e2[1]
            sy += e1[2] * e2[0] - e1[0] * e2[2]
            sz += e1[0] * e2[1] - e1[1] * e2[0]
        l = math.sqrt(sx * sx + sy * sy + sz * sz)
        if l < 1e-12:
            raise ValueError("帽盖三角组退化（面积 ≈ 0）")
        return [sx / l, sy / l, sz / l]

    # 从最终绕向（含全局 flip）切片取帽组：保证法向 outward
    n_front = _group_face_normal(indices[: len(cap)])
    n_rear = _group_face_normal(indices[len(indices) - len(cap):])
    ribbon_normals = compute_vertex_normals(positions, ribbons)  # 仅 ribbon 三角贡献
    normals = (
        list(n_front) * n
        + ribbon_normals[base_s * 3 : base_b * 3]
        + list(n_rear) * n
    )
    return ToothSolid(
        mesh_positions=positions,
        mesh_indices=indices,
        mesh_normals=normals,
        ribbon_indices=ribbons,
        loop=loop,
        volume_mm3=_signed_volume(positions, indices),
        n_loop=n,
        n_sections=n_L + 1,
    )


def build_tool_ring(solid: ToothSolid, *, z_t: int) -> GeometrySpec:
    """整环刀具：单齿闭合实体绕 Z **同相位周向阵列** z_t 份（坐标 T）.

    第 i 齿变换 = 纯绕 Z 旋转 θ_i = i·2π/z_t，**无任何轴向错位**。
    几何依据：单齿本体已是沿导程螺旋扫掠的条带（截面恒定螺旋扫掠，自带扭转），
    各条带共享同一对端面 —— 周向阵列即在任意横截面给出 z_t 个错开 2π/z_t 的完整
    齿廓，齿线自动落在螺旋线上；这正是工件侧 ADR-002「单齿放样 → 阵列 → 并」的
    同构做法，也是设计书 K-3.1「周向阵列 z_t 份」的原义。

    勘误记录（2026-08-27）：TO-3/#34 曾按 ΔZ_i = i·(L_tp/z_t)·j_t 施加逐齿轴向
    错位，用户实测证伪——那会把宽度 L 的单齿串成总跨度 (z_t−1)·p_z 的蜗杆状弹簧，
    齿间出现 p_z≈24mm 的巨大轴向间隙。该语义属 hob 类单头螺纹排布，不适用于
    车齿刀。导程 L_tp 只进入后刀面螺旋扫掠链（helical_lead_mm），与本阵列无关。

    K-3.1 定位不变：三角网伪实体预览级（非 OCCT 实体布尔，K-3.2 刀体结构 W9 未回读）。
    """
    if z_t < 2:
        raise ValueError(f"阵列份数 z_t={z_t} 至少 2")
    n_tooth = len(solid.mesh_positions) // 3
    delta = 2.0 * math.pi / z_t
    positions: list[float] = []
    indices: list[int] = []
    for k in range(z_t):
        ang = k * delta
        c, s = math.cos(ang), math.sin(ang)
        for i in range(0, len(solid.mesh_positions), 3):
            x, y, z = solid.mesh_positions[i], solid.mesh_positions[i + 1], solid.mesh_positions[i + 2]
            positions += [x * c - y * s, x * s + y * c, z]
        indices += [i + k * n_tooth for i in solid.mesh_indices]
    normals = compute_vertex_normals(positions, indices)
    return GeometrySpec(
        kind="mesh", positions=positions, indices=indices, normals=normals,
        layer_id="toolRing",
    )


def build_single_tooth_solid(
    profile_pts,
    plan: ProcessPlan,
    rake: RakeSurface,
    *,
    r_a: float,
    beta_t_deg: float,
    z_t: int,
    m_n: float,
    L: float,
    n_L: int,
    root_offset_ratio: float = ROOT_OFFSET_RATIO_DEFAULT,
    n_arc: int = 17,
    n_ext: int = 4,
    n_off: int = 4,
    m: int = 181,
    theta_range_deg: float = 40.0,
    normals=None,
    r_f: float | None = None,
    b_w: float = 0.0,
    n_z: int = 21,
) -> ToothSolid:
    """B 方案 v7 管线上层：列序刃形链 → 闭合轮廓 → 闭合实体（坐标 T）.

    斜齿（β_w≠0，2026-08-25 第二批）：链走数值求交路线（solve_edge_chain 内部
    分派 compute_helical_edge，需 b_w>0），闭合环走 build_tooth_loop precut 模式
    （顶缝桥点构造标记透传）；实体螺旋扫掠/前后帽管线与直齿同构、天然通用。

    Args:
        profile_pts: 工件齿廓点 [(x, y), ...]（含齿顶弧段——齿根延伸的共轭源）
        plan: ProcessPlan
        rake: RakeSurface
        r_a: 工件齿顶圆半径 [mm]（理论极限 = r_a − a）
        beta_t_deg / z_t / m_n: 刀具螺旋角 [°] / 齿数 / 法向模数 [mm]
        L / n_L: 总重磨量 / 等分数
        root_offset_ratio: 齿根径向偏置 / 分度圆直径（默认 1/20，用户选定）
        n_arc / n_ext / n_off: 谷底圆弧 / 延伸弦直线 / 偏置直线采样
        m / theta_range_deg: 运动离散（透传 solve_edge_chain）
        normals: 廓形法矢（透传）
        r_f: 工件齿根圆半径 [mm]（齿顶伪点判据 r_f−a；None 跳过）
        b_w / n_z: 工件齿宽 / 轴向层数（斜齿数值求交链必需；直齿忽略）

    Returns:
        ToothSolid
    """
    chain_pts, _phis, _cols, bridge = solve_edge_chain(
        profile_pts, plan, rake, m=m, theta_range_deg=theta_range_deg, normals=normals,
        b_w=b_w, n_z=n_z,
    )
    if len(chain_pts) < 8:
        raise ValueError("刃形链过短（外齿轮前刀面符号 T14 未销项）：请使用内齿轮（k_io=−1）")
    r_limit = limit_radius(r_a, plan.a)
    is_helical = abs(plan.beta_w_deg) > 1e-12
    loop = build_tooth_loop(
        chain_pts, rake, z_t=z_t, r_pt=plan.r_pt, r_limit=r_limit,
        offset_ratio=root_offset_ratio, n_arc=n_arc, n_ext=n_ext, n_off=n_off,
        r_f=r_f, a=plan.a,
        precut=is_helical, upper_constructed=bridge if is_helical else None,
    )
    return build_tooth_solid(
        loop, rake, m_n=m_n, beta_t_deg=beta_t_deg, z_t=z_t, L=L, n_L=n_L
    )

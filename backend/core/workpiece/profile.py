"""Module ① 端面齿廓纯数学 — 设计书 K-1.1/K-1.12/K-1.13, 单一权威实现.

不依赖 OCCT。两个表示层均为本模块的薄消费者:
  - builder  (OCCT edges)     ← gear_profile_segments / single_tooth_segments
  - exporter (mesh 三角剖分)  ← sample_profile_points

历史教训 (2026-08-06): 轮廓数学曾内联于 builder 与 exporter 两份拷贝,
右齿面镜像与 ∓inv(α_t) 相位双份错, OCCT 齿根弧还因 first>last 调用取到长弧。
统一后形状级不变量由 test_exporter.TestProfileShape 与
test_workpiece.TestCrossRepresentationConsistency 把守。

坐标约定 (U13): 齿中心线在 tooth_center = i·2π/z_w, 边界 CCW 遍历。
K-1.13: 左齿面 = 渐开线模板旋转, 右齿面 = 模板镜像后旋转;
放置角 ∓(half_tooth_angle + inv(α_t)) 使节圆处齿面极角恰为 ∓half_tooth_angle。
K-1.12 (方案 A): r_b > r_f 时齿根圆角必构, ρ_f = ρ*_f·m_n, 双切
(齿根圆 + 渐开线) 一维搜索定圆心; 渐开线自圆角切点 ξ_f 起始。

ADR-012 (2026-08-07): K-1.1 渐开线单点数学 (involute_point / involute_radius /
xi_at_radius / generate_involute_points) 从 models.py 迁入本模块——
profile.py 是渐开线齿廓的单一权威源，models.py 仅保留数据模型与齿厚反算。
"""

import math
from dataclasses import dataclass

from core.workpiece.models import GearParams, compute_tooth_thickness


# ── K-1.1 渐开线廓形 (端面, 单一权威实现) ──────────────────────────────
# ADR-012: 原位于 models.py, 2026-08-07 迁入 profile.py


def involute_point(r_b: float, xi: float) -> tuple[float, float]:
    """K-1.1 渐开线单点 (端面).

    x = r_b·(cos ξ + ξ·sin ξ)
    y = r_b·(sin ξ − ξ·cos ξ)

    起点 ξ=0 在基圆上: (r_b, 0).

    Args:
        r_b: 基圆半径 [mm]
        xi: 展角参数 (roll angle) [rad]

    Returns:
        (x, y) 渐开线上点坐标 [mm]
    """
    cos_xi = math.cos(xi)
    sin_xi = math.sin(xi)

    x = r_b * (cos_xi + xi * sin_xi)
    y = r_b * (sin_xi - xi * cos_xi)

    return (x, y)


def involute_radius(r_b: float, xi: float) -> float:
    """渐开线上点的径向距离: r(ξ) = r_b·√(1+ξ²).

    Args:
        r_b: 基圆半径 [mm]
        xi: 展角参数 [rad]

    Returns:
        径向距离 [mm]
    """
    return r_b * math.sqrt(1.0 + xi * xi)


def xi_at_radius(r_b: float, r: float) -> float:
    """已知径向距离 r 反求展角 ξ.

    ξ = √((r/r_b)² − 1)

    Args:
        r_b: 基圆半径 [mm]
        r: 目标径向距离 [mm], r ≥ r_b

    Returns:
        展角 ξ [rad]

    Raises:
        ValueError: r < r_b (点在基圆内，无渐开线)
    """
    if r < r_b - 1e-12:
        raise ValueError(f"r={r} < r_b={r_b}: 基圆内无渐开线")
    if abs(r - r_b) < 1e-12:
        return 0.0
    return math.sqrt((r / r_b) ** 2 - 1.0)


def generate_involute_points(
    r_b: float,
    r_a: float,
    n_points: int,
    r_f: float | None = None,
) -> list[tuple[float, float]]:
    """K-1.1 + K-1.12 生成渐开线齿面点集 (端面).

    从基圆 (或齿根圆，取大者) 到齿顶圆，等间距采样。

    Args:
        r_b: 基圆半径 [mm]
        r_a: 齿顶圆半径 [mm]
        n_points: 采样点数
        r_f: 齿根圆半径 [mm], 可选。若 r_b > r_f 则从 r_b 开始；
              否则从 max(r_f, r_b) 开始 (K-1.12 圆角段不由本函数处理)

    Returns:
        [(x, y), ...] 渐开线点集 (从齿根到齿顶)
    """
    if n_points < 2:
        raise ValueError(f"n_points={n_points} 必须 ≥ 2")

    r_start = max(r_b, r_f) if r_f is not None else r_b

    if r_a <= r_start:
        raise ValueError(f"齿顶圆 r_a={r_a} ≤ 起始半径 r_start={r_start}")

    xi_start = xi_at_radius(r_b, r_start)
    xi_end = xi_at_radius(r_b, r_a)

    points: list[tuple[float, float]] = []
    for i in range(n_points):
        t = i / (n_points - 1)
        xi = xi_start + t * (xi_end - xi_start)
        points.append(involute_point(r_b, xi))

    return points


@dataclass(frozen=True)
class Arc:
    """圆弧段: 圆心 + 半径 + 起止角 (遍历方向).

    clockwise=False: CCW 从 a0 到 a1 (a1 > a0, 短弧) — 齿顶/齿根弧;
    clockwise=True:  CW  从 a0 到 a1 (a1 < a0, 短弧) — 齿根圆角 (凹角)。
    """

    radius: float
    a0: float
    a1: float
    center: tuple[float, float] = (0.0, 0.0)
    clockwise: bool = False


@dataclass(frozen=True)
class Polyline:
    """折线段: 有序点列 (含端点, 遍历方向)."""

    points: tuple[tuple[float, float], ...]


Segment = Arc | Polyline


def tooth_thickness_half_angle(p: GearParams) -> float:
    """节圆齿厚半角 s_t/(2·r_pw) [rad]."""
    return compute_tooth_thickness(p) / (2.0 * p.pitch_radius())


def involute_phase(p: GearParams) -> float:
    """渐开线相位 inv(α_t) = tan(α_t) − α_t [rad]."""
    alpha_t = math.radians(p.to_transverse()[1])
    return math.tan(alpha_t) - alpha_t


def _rot(pt: tuple[float, float], ca: float, sa: float) -> tuple[float, float]:
    return (pt[0] * ca - pt[1] * sa, pt[0] * sa + pt[1] * ca)


# ── K-1.12 齿根圆角 (方案 A) ─────────────────────────────────────────


@dataclass(frozen=True)
class RootFillet:
    """K-1.12 圆角解 (模板坐标系, 未旋转未镜像的左齿面渐开线).

    xi_f: 渐开线起始展角 (圆角-渐开线切点)
    center_t: 圆角圆心
    tang_inv_t: 渐开线切点 (= involute_point(r_b, xi_f))
    tang_root_t: 齿根圆切点 (在圆心-原点连线上, 半径 r_f)
    """

    xi_f: float
    center_t: tuple[float, float]
    tang_inv_t: tuple[float, float]
    tang_root_t: tuple[float, float]


def solve_root_fillet(p: GearParams, n_search: int = 200) -> RootFillet:
    """K-1.12: 一维数值搜索求双切圆角 (切齿根圆 + 切渐开线).

    在模板坐标系求解, 凹角填充侧取极角小于齿面的一侧 (左齿面齿槽侧);
    右齿面由调用方镜像获得。

    Args:
        p: 齿轮参数 (要求 r_b > r_f)
        n_search: 搜索采样数

    Returns:
        RootFillet

    Raises:
        ValueError: r_b <= r_f (无需圆角) 或搜索不收敛
    """
    r_b = p.base_radius()
    r_f = p.root_radius()
    rho = p.rho_f * p.m_n

    if r_b <= r_f:
        raise ValueError(f"r_b={r_b:.3f} <= r_f={r_f:.3f}: 渐开线直达齿根, 无需圆角")

    target = r_f + rho
    xi_max = xi_at_radius(r_b, min(r_b * 1.5, r_f + 3.0 * rho))

    def center_at(xi: float) -> tuple[float, float]:
        """凹角侧候选圆心: C = P − rho·n, n = (−sin ξ, cos ξ)."""
        px, py = involute_point(r_b, xi)
        return (px + rho * math.sin(xi), py - rho * math.cos(xi))

    def resid(xi: float) -> float:
        cx, cy = center_at(xi)
        return math.hypot(cx, cy) - target

    # 粗扫找变号区间 (仅取凹角侧: 圆心极角 < 渐开线点极角).
    # 解存在条件 ≈ r_f + rho > r_b (|P−rho·n| 最小值 √(r_b²+rho²) 在 ξ=0);
    # 深齿根 (r_b − r_f > rho 量级) 无双切解 —— 真实齿根为滚刀摆线
    # (方案 B, T13 未销项), 调用方回退径向连接线。
    step = xi_max / n_search
    bracket: tuple[float, float] | None = None
    prev_xi: float | None = None
    prev_r: float | None = None
    for i in range(n_search + 1):
        xi = xi_max * i / n_search
        cx, cy = center_at(xi)
        px, py = involute_point(r_b, xi)
        if math.atan2(cy, cx) < math.atan2(py, px):
            r = resid(xi)
            if prev_r is not None and prev_r * r <= 0 and (prev_r or r):
                bracket = (prev_xi, xi)  # type: ignore[assignment]
                break
            prev_r, prev_xi = r, xi

    if bracket is None:
        raise ValueError(
            f"K-1.12 双切圆角无解 (r_b={r_b:.3f}, r_f={r_f:.3f}, rho={rho:.3f}); "
            f"需方案 B 摆线或回退径向连接"
        )

    # 二分精确化
    lo, hi = bracket
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if resid(lo) * resid(mid) <= 0:
            hi = mid
        else:
            lo = mid
    xi0 = 0.5 * (lo + hi)

    center_t = center_at(xi0)
    tang_inv_t = involute_point(r_b, xi0)
    scale = r_f / target
    tang_root_t = (center_t[0] * scale, center_t[1] * scale)

    return RootFillet(xi_f=xi0, center_t=center_t, tang_inv_t=tang_inv_t, tang_root_t=tang_root_t)


# ── 廓形段构建 ───────────────────────────────────────────────────────


def _cw_unwrap(a0: float, a1: float) -> float:
    """把 a1 解卷为 a0 + d, d ∈ (−π, 0) (顺时针短弧).

    注意跨 ±π 边界时 a1 主值与 a0 差 ≈ 2π, 必须用 a0 + d 重构而非返回原值。
    """
    d = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
    return a0 + d


def _ccw_unwrap(a0: float, a1: float) -> float:
    """把 a1 解卷为 a0 + d, d ∈ (0, π) (逆时针短弧). 见 _cw_unwrap 边界说明."""
    d = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
    return a0 + d


def _tooth_open_segments(
    p: GearParams,
    i_tooth: int,
    n_involute: int,
    theta_offset: float = 0.0,
) -> tuple[list[Segment], tuple[float, float], tuple[float, float], float, float]:
    """单齿开放段 (左圆角→左齿面→齿顶→右齿面→右圆角) + 齿根切点与放置角.

    theta_offset: 绕 Z 轴额外旋转角 [rad], 用于斜齿轮截面扭转.

    Returns:
        (segs, t_root_right, t_root_left, right_root_ang, next_left_root_ang)
        后两个角为左右齿根圆切点极角 (供齿根弧闭合用)
    """
    z_w = p.z_w
    r_a = p.tip_radius()
    r_b = p.base_radius()
    pitch_angle = 2.0 * math.pi / z_w
    half = tooth_thickness_half_angle(p)
    inv_at = involute_phase(p)

    tooth_center = i_tooth * pitch_angle + theta_offset
    left_angle = tooth_center - half - inv_at
    right_angle = tooth_center + half + inv_at

    cos_la, sin_la = math.cos(left_angle), math.sin(left_angle)
    cos_ra, sin_ra = math.cos(right_angle), math.sin(right_angle)

    r_f = p.root_radius()
    fil: RootFillet | None = None
    if r_b > r_f:
        try:
            fil = solve_root_fillet(p)
        except ValueError:
            # 双切无解 (深齿根, r_b − r_f ≳ rho): 回退径向连接线
            # (真实齿根为滚刀摆线 = 方案 B, T13 未销项)
            fil = None
    if fil is not None:
        xi_start = fil.xi_f
    elif r_f > r_b:
        xi_start = xi_at_radius(r_b, r_f)
    else:
        xi_start = 0.0
    xi_end = xi_at_radius(r_b, r_a)

    template = [
        involute_point(r_b, xi_start + (xi_end - xi_start) * i / n_involute)
        for i in range(n_involute + 1)
    ]

    left_pts = tuple(_rot(pt, cos_la, sin_la) for pt in template)
    right_pts = tuple(_rot((pt[0], -pt[1]), cos_ra, sin_ra) for pt in template)

    left_tip_ang = math.atan2(left_pts[-1][1], left_pts[-1][0])
    right_tip_ang = _ccw_unwrap(left_tip_ang, math.atan2(right_pts[-1][1], right_pts[-1][0]))

    segs: list[Segment] = []

    if fil is not None:
        # 左圆角 (模板解旋转): 齿根切点 → 渐开线切点, CW (凹角)
        c_l = _rot(fil.center_t, cos_la, sin_la)
        tr_l = _rot(fil.tang_root_t, cos_la, sin_la)
        ti_l = _rot(fil.tang_inv_t, cos_la, sin_la)
        a0 = math.atan2(tr_l[1] - c_l[1], tr_l[0] - c_l[0])
        a1 = _cw_unwrap(a0, math.atan2(ti_l[1] - c_l[1], ti_l[0] - c_l[0]))
        segs.append(Arc(p.rho_f * p.m_n, a0, a1, center=c_l, clockwise=True))

    segs.append(Polyline(left_pts))
    segs.append(Arc(r_a, left_tip_ang, right_tip_ang))
    segs.append(Polyline(tuple(reversed(right_pts))))

    # ── 齿根连接 (遍历: 右齿根 → 下一齿左齿根) ──
    conn: list[Segment] = []
    if fil is not None:
        # 右圆角 (模板解镜像后旋转): 渐开线切点 → 齿根切点, CW (凹角)
        c_r = _rot((fil.center_t[0], -fil.center_t[1]), cos_ra, sin_ra)
        ti_r = _rot((fil.tang_inv_t[0], -fil.tang_inv_t[1]), cos_ra, sin_ra)
        tr_r = _rot((fil.tang_root_t[0], -fil.tang_root_t[1]), cos_ra, sin_ra)
        a0 = math.atan2(ti_r[1] - c_r[1], ti_r[0] - c_r[0])
        a1 = _cw_unwrap(a0, math.atan2(tr_r[1] - c_r[1], tr_r[0] - c_r[0]))
        segs.append(Arc(p.rho_f * p.m_n, a0, a1, center=c_r, clockwise=True))
        t_root_right, t_root_left = tr_r, tr_l
        right_root_ang = math.atan2(tr_r[1], tr_r[0])
        next_left_root_ang = math.atan2(tr_l[1], tr_l[0]) + pitch_angle
        conn.append(Arc(r_f, right_root_ang, _ccw_unwrap(right_root_ang, next_left_root_ang)))
    else:
        right_root = right_pts[0]
        left_root = left_pts[0]
        t_root_right, t_root_left = right_root, left_root
        right_root_ang = math.atan2(right_root[1], right_root[0])
        next_left_root_ang = math.atan2(left_root[1], left_root[0]) + pitch_angle
        if r_b > r_f:
            # 双切无解回退: 径向 r_b→r_f + 齿根弧 + 径向 r_f→r_b
            conn.append(Polyline((
                right_root,
                (r_f * math.cos(right_root_ang), r_f * math.sin(right_root_ang)),
            )))
            nla = _ccw_unwrap(right_root_ang, next_left_root_ang)
            conn.append(Arc(r_f, right_root_ang, nla))
            cos_n, sin_n = math.cos(nla), math.sin(nla)
            next_left_root_b = _rot(
                template[0],
                math.cos(left_angle + pitch_angle),
                math.sin(left_angle + pitch_angle),
            )
            conn.append(Polyline(((r_f * cos_n, r_f * sin_n), next_left_root_b)))
        else:
            conn.append(Arc(r_f, right_root_ang, _ccw_unwrap(right_root_ang, next_left_root_ang)))

    return segs, conn, t_root_right, t_root_left, right_root_ang


def tooth_segments(
    p: GearParams,
    i_tooth: int,
    n_involute: int = 40,
    n_tip: int = 10,
    n_root: int = 5,
) -> list[Segment]:
    """第 i_tooth 齿的廓形段 (CCW): 开放段 + 齿根弧 (至下一齿左齿根).

    Args:
        p: 齿轮参数
        i_tooth: 齿序号
        n_involute: 每侧渐开线采样点数
        n_tip: 齿顶弧内部采样点数 (exporter 用; builder 用真弧)
        n_root: 齿根弧内部采样点数 (同上)

    Returns:
        段列表, 首尾点与相邻齿段衔接 (重复点由消费者去重)
    """
    segs, conn, _, _, _ = _tooth_open_segments(p, i_tooth, n_involute)
    return segs + conn


def gear_profile_segments(
    p: GearParams,
    n_involute: int = 40,
    n_tip: int = 10,
    n_root: int = 5,
) -> list[Segment]:
    """全齿圈闭合廓形段 (CCW, z_w 个 tooth_segments 首尾衔接)."""
    return [
        seg
        for i in range(p.z_w)
        for seg in tooth_segments(p, i, n_involute, n_tip, n_root)
    ]


def single_tooth_segments(
    p: GearParams,
    n_involute: int = 40,
    theta_offset: float = 0.0,
) -> list[Segment]:
    """单齿闭合廓形段 (CCW): 开放段 + 齿根闭合.

    theta_offset: 绕 Z 轴额外旋转角 [rad], 用于斜齿轮截面扭转.

    与 tooth_segments 的区别: tooth_segments 的 conn 连接到下一齿;
    本函数闭合到同一齿的起始点 (供 ThruSections 单齿截面用)。
    """
    r_f = p.root_radius()
    r_b = p.base_radius()
    pitch_angle = 2.0 * math.pi / p.z_w
    half = tooth_thickness_half_angle(p)
    inv_at = involute_phase(p)

    tooth_center = theta_offset
    left_angle = tooth_center - half - inv_at
    right_angle = tooth_center + half + inv_at

    # 构建左齿面模板点 (用于回退路径的端点)
    r_a = p.tip_radius()
    xi_end = xi_at_radius(r_b, r_a)

    fil: RootFillet | None = None
    if r_b > r_f:
        try:
            fil = solve_root_fillet(p)
        except ValueError:
            fil = None
    if fil is not None:
        xi_start = fil.xi_f
    elif r_f > r_b:
        xi_start = xi_at_radius(r_b, r_f)
    else:
        xi_start = 0.0

    template = [
        involute_point(r_b, xi_start + (xi_end - xi_start) * i / n_involute)
        for i in range(n_involute + 1)
    ]

    # 用 _tooth_open_segments 获取开放段 + 齿根信息
    segs, conn, t_root_right, t_root_left, right_root_ang = _tooth_open_segments(
        p, 0, n_involute, theta_offset
    )

    left_root_ang = math.atan2(t_root_left[1], t_root_left[0])

    if fil is not None or r_f >= r_b:
        # 圆角存在 或 渐开线直达齿根: 直接用根弧闭合
        segs.append(Arc(r_f, right_root_ang, left_root_ang + 2.0 * math.pi))
    else:
        # r_b > r_f 但双切无解: 回退径向连接, 闭合到同一齿左侧
        cos_ra, sin_ra = math.cos(right_angle), math.sin(right_angle)
        cos_la, sin_la = math.cos(left_angle), math.sin(left_angle)
        right_root = _rot(template[0], cos_ra, sin_ra)
        left_root = _rot(template[0], cos_la, sin_la)

        segs.append(Polyline((
            right_root,
            (r_f * math.cos(right_root_ang), r_f * math.sin(right_root_ang)),
        )))
        segs.append(Arc(r_f, right_root_ang, left_root_ang + 2.0 * math.pi))
        segs.append(Polyline((
            (r_f * math.cos(left_root_ang), r_f * math.sin(left_root_ang)),
            left_root,
        )))

    return segs


def _arc_samples(arc: Arc, n: int) -> list[tuple[float, float]]:
    """弧采样点 (含两端点 + n 个内部点), 沿遍历方向 a0→a1.

    端点显式入列, 相邻段重合点由 sample_profile_points 去重。
    """
    cx, cy = arc.center
    pts = [
        (
            cx + arc.radius * math.cos(arc.a0 + (arc.a1 - arc.a0) * j / (n + 1)),
            cy + arc.radius * math.sin(arc.a0 + (arc.a1 - arc.a0) * j / (n + 1)),
        )
        for j in range(n + 2)
    ]
    return pts


def sample_profile_points(
    p: GearParams,
    n_involute: int = 40,
    n_tip: int = 10,
    n_root: int = 5,
    n_fillet: int = 8,
) -> list[tuple[float, float]]:
    """全齿圈轮廓采样点列 (简单闭合多边形, CCW, 无连续重复点).

    弧段按 n_tip/n_root/n_fillet 内部采样; 折线段端点与相邻段去重。
    """
    r_a = p.tip_radius()
    pts: list[tuple[float, float]] = []
    for seg in gear_profile_segments(p, n_involute, n_tip, n_root):
        if isinstance(seg, Polyline):
            start = 1 if pts and math.dist(pts[-1], seg.points[0]) <= 1e-9 else 0
            pts.extend(seg.points[start:])
        else:
            if seg.clockwise:
                n = n_fillet
            elif abs(seg.radius - r_a) <= 1e-9 and seg.center == (0.0, 0.0):
                n = n_tip
            else:
                n = n_root
            pts.extend(_arc_samples(seg, n))
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) <= 1e-9:
        pts.pop()
    return pts

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
    rho: 实际圆角半径 [mm] (深下切时放大到最小可行双切半径, 方案 A 扩展)
    """

    xi_f: float
    center_t: tuple[float, float]
    tang_inv_t: tuple[float, float]
    tang_root_t: tuple[float, float]
    rho: float


def solve_root_fillet(p: GearParams, n_search: int = 200) -> RootFillet:
    """K-1.12: 一维数值搜索求双切圆角 (切齿根圆 + 切渐开线).

    在模板坐标系求解, 凹角填充侧取极角小于齿面的一侧 (左齿面齿槽侧);
    右齿面由调用方镜像获得。

    Args:
        p: 齿轮参数
        n_search: 搜索采样数

    Returns:
        RootFillet

    Raises:
        ValueError: 双切圆角无解 (深齿根等, 需方案 B 摆线) 或搜索不收敛
    """
    r_b = p.base_radius()
    r_f = p.root_radius()
    rho_req = p.rho_f * p.m_n
    # 方案 A 扩展 (填死区): r_b > r_f 且请求半径太小塞不下时, 放大到最小可行双切半径.
    # 双切解存在条件 √(r_b²+ρ²) ≤ r_f+ρ ⟺ ρ ≥ (r_b²−r_f²)/(2r_f).
    # 放大后仍是真正的双切圆角 (方案 A), 只是实际半径 > 请求值; 可解范围零变化。
    if r_b > r_f:
        rho_min = (r_b * r_b - r_f * r_f) / (2.0 * r_f)
        rho = max(rho_req, rho_min * 1.001)
    else:
        rho = rho_req

    target = r_f + rho
    # 搜索起点: r_b > r_f (有根切) 时齿面从基圆起始 (ξ=0); r_b <= r_f (无根切,
    # 高齿数) 时齿面从齿根圆起始——齿面与齿根圆在连接处成角, 双切圆角仍可解。
    xi_start = 0.0 if r_b > r_f else xi_at_radius(r_b, r_f)
    xi_max = max(xi_start + 1e-9, xi_at_radius(r_b, min(r_b * 1.5, r_f + 3.0 * rho)))

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
    step = (xi_max - xi_start) / n_search
    bracket: tuple[float, float] | None = None
    prev_xi: float | None = None
    prev_r: float | None = None
    for i in range(n_search + 1):
        xi = xi_start + (xi_max - xi_start) * i / n_search
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

    return RootFillet(xi_f=xi0, center_t=center_t, tang_inv_t=tang_inv_t, tang_root_t=tang_root_t, rho=rho)


def root_fillet_actual_mm(p: GearParams) -> float:
    """齿根圆角实际半径 [mm]: 开关关 / 无双切解时 0, 否则实际 ρ (深下切时放大)."""
    if not p.root_fillet:
        return 0.0
    try:
        fil = solve_root_fillet(p)
    except ValueError:
        return 0.0
    return fil.rho


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


# ── T02/T03: 齿顶处理 (ADR-014 产品扩展) ─────────────────────────────
# 齿顶圆角/倒角不在设计书参数字典 (ADR-013 缺口), 默认 tip_mode='none' 零变化。
# 圆角 = 凸角双切 (切齿面渐开线 + 切齿顶圆), 与 solve_root_fillet 对称;
# 倒角 = 沿齿面量 c·mₙ、过切点画与齿面切线 45° 线、交齿顶弧 (构造唯一)。


def _linspace(a: float, b: float, n: int) -> list[float]:
    """n+1 个从 a 到 b 的等间距点."""
    return [a + (b - a) * i / n for i in range(n + 1)]


def _ang_diff(a: float, b: float) -> float:
    """两角最小差绝对值 (0..π)."""
    return abs((a - b + math.pi) % (2.0 * math.pi) - math.pi)


def _solve_tip_fillet(
    rho: float,
    r_b: float,
    r_a: float,
    xi_start: float,
    xi_end: float,
    ca: float,
    sa: float,
    mirror: int,
    n_bisect: int = 200,
) -> tuple[float, tuple[float, float], tuple[float, float], tuple[float, float]] | None:
    """凸角齿顶圆角双切求解: 切齿面渐开线 + 切齿顶圆, 半径 rho [mm].

    在旋转 (ca,sa) 帧内求解。mirror=+1 左齿面 (模板不镜像), −1 右齿面 (模板 y 镜像)。
    齿侧法向 (沿 xi 增大, 齿侧): 左 (−sin ξ, cos ξ), 右 (−sin ξ, −cos ξ)。
    |C|² 在 ξ=ρ/r_b 处最小 (=r_b); 解位于 [max(xi_start, ρ/r_b), xi_end]。

    Returns:
        (xi_f, center, flank_tangent, tip_tangent)。None: 无解 (ρ ≥ r_a−r_b 等), 调用方收敛为锐齿顶。
    """
    if rho <= 0.0 or rho >= r_a:
        return None
    target = r_a - rho
    if target < 0.0:
        return None

    def pt(xi: float) -> tuple[float, float]:
        x, y = involute_point(r_b, xi)
        if mirror < 0:
            y = -y
        return _rot((x, y), ca, sa)

    def normal(xi: float) -> tuple[float, float]:
        nx, ny = -math.sin(xi), math.cos(xi)
        if mirror < 0:
            ny = -ny
        return _rot((nx, ny), ca, sa)

    def resid(xi: float) -> float:
        px, py = pt(xi)
        nx, ny = normal(xi)
        return math.hypot(px + rho * nx, py + rho * ny) - target

    lo = max(xi_start, rho / r_b)
    hi = xi_end
    r_lo, r_hi = resid(lo), resid(hi)
    if r_lo >= 0.0 or r_hi <= 0.0:
        return None
    for _ in range(n_bisect):
        mid = 0.5 * (lo + hi)
        if resid(mid) > 0.0:
            hi = mid
        else:
            lo = mid
    xi_f = 0.5 * (lo + hi)
    px, py = pt(xi_f)
    nx, ny = normal(xi_f)
    c = (px + rho * nx, py + rho * ny)
    norm_c = math.hypot(*c)
    t = (c[0] * r_a / norm_c, c[1] * r_a / norm_c)
    return xi_f, c, (px, py), t


def _fillet_arc(
    a_pt: tuple[float, float],
    b_pt: tuple[float, float],
    c: tuple[float, float],
    rho: float,
    tangent_at_start: float,
) -> Arc:
    """圆角弧 (a_pt→b_pt 绕 c, 半径 rho), 选起点切线 = tangent_at_start 的弧向 (G1)."""
    a_A = math.atan2(a_pt[1] - c[1], a_pt[0] - c[0])
    a_B = math.atan2(b_pt[1] - c[1], b_pt[0] - c[0])
    d_ccw = _ang_diff(a_A + math.pi / 2.0, tangent_at_start)
    d_cw = _ang_diff(a_A - math.pi / 2.0, tangent_at_start)
    if d_ccw <= d_cw:
        return Arc(rho, a_A, _ccw_unwrap(a_A, a_B), center=c, clockwise=False)
    return Arc(rho, a_A, _cw_unwrap(a_A, a_B), center=c, clockwise=True)


def _tooth0_tip_context(p: GearParams, n_involute: int = 40):
    """tooth0 齿顶处理上下文: 半径/展角区间/齿面旋转角 (供收敛与 actual 计算).

    Returns:
        (r_b, r_a, xi_start, xi_end, cos_la, sin_la, cos_ra, sin_ra, n_involute)
    """
    r_b = p.base_radius()
    r_a = p.tip_radius()
    r_f = p.root_radius()
    xi_end = xi_at_radius(r_b, r_a)
    fil = None
    if p.root_fillet:
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
    half = tooth_thickness_half_angle(p)
    inv_at = involute_phase(p)
    la = -half - inv_at
    ra = half + inv_at
    return (r_b, r_a, xi_start, xi_end,
            math.cos(la), math.sin(la), math.cos(ra), math.sin(ra), n_involute)


def _max_feasible_by_search(req: float, builds, n: int = 40) -> float:
    """二分求 builds(c) 成立的最大 c ∈ (0, req]; builds(0)=False (c≤0 视为无解), 下限 0."""
    if builds(req):
        return req
    lo, hi, best = 0.0, req, 0.0
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        if builds(mid):
            best = mid
            lo = mid
        else:
            hi = mid
    return best


def _tip_build_at(
    value_mm: float,
    r_b: float,
    r_a: float,
    xi_start: float,
    xi_end: float,
    left_pts: tuple,
    right_pts: tuple,
    cos_la: float,
    sin_la: float,
    cos_ra: float,
    sin_ra: float,
    solve_side,
    build_mid,
) -> list[Segment] | None:
    """给定齿顶处理尺寸 value_mm 的中间段 (None = 无解/重叠).

    solve_side(value_mm, r_b, r_a, xi_start, xi_end, ca, sa, mirror) → (xi_f, f, t, extra) | None
    build_mid(f_l, t_l, ex_l, f_r, t_r, ex_r, a_l, a_r, value_mm, r_a) → 中间两段 + 齿顶弧
    """
    sol_l = solve_side(value_mm, r_b, r_a, xi_start, xi_end, cos_la, sin_la, mirror=1)
    sol_r = solve_side(value_mm, r_b, r_a, xi_start, xi_end, cos_ra, sin_ra, mirror=-1)
    if sol_l is None or sol_r is None:
        return None
    xi_f_l, f_l, t_l, ex_l = sol_l
    xi_f_r, f_r, t_r, ex_r = sol_r
    a_l = math.atan2(t_l[1], t_l[0])
    a_r = _ccw_unwrap(a_l, math.atan2(t_r[1], t_r[0]))
    if a_r - a_l <= 1e-9:
        return None  # 两侧处理在齿顶弧上重叠
    n_inv = len(left_pts) - 1
    left_trim = tuple(
        _rot(involute_point(r_b, xi), cos_la, sin_la) for xi in _linspace(xi_start, xi_f_l, n_inv)
    )
    right_trim = tuple(
        _rot((involute_point(r_b, xi)[0], -involute_point(r_b, xi)[1]), cos_ra, sin_ra)
        for xi in _linspace(xi_start, xi_f_r, n_inv)
    )
    mid = build_mid(f_l, t_l, ex_l, f_r, t_r, ex_r, a_l, a_r, value_mm, r_a)
    if mid is None:
        return None
    return [Polyline(left_trim), *mid, Polyline(tuple(reversed(right_trim)))]


def _tip_feasible_mm(
    req_mm: float,
    r_b: float,
    r_a: float,
    xi_start: float,
    xi_end: float,
    left_pts: tuple,
    right_pts: tuple,
    cos_la: float,
    sin_la: float,
    cos_ra: float,
    sin_ra: float,
    solve_side,
    build_mid,
) -> float:
    """齿顶处理最大可行尺寸 [mm]: 请求可行则原值, 否则二分收敛 (Q8)."""
    if req_mm <= 0:
        return 0.0
    builds = lambda v: _tip_build_at(v, r_b, r_a, xi_start, xi_end, left_pts, right_pts,
                                     cos_la, sin_la, cos_ra, sin_ra, solve_side, build_mid) is not None
    return _max_feasible_by_search(req_mm, builds)


def _tip_middle(
    req_mm: float,
    r_b: float,
    r_a: float,
    xi_start: float,
    xi_end: float,
    left_pts: tuple,
    right_pts: tuple,
    cos_la: float,
    sin_la: float,
    cos_ra: float,
    sin_ra: float,
    solve_side,
    build_mid,
) -> list[Segment] | None:
    """齿顶处理中间段, 超限自动收敛 (Q8)."""
    if req_mm <= 0:
        return None
    v_use = _tip_feasible_mm(req_mm, r_b, r_a, xi_start, xi_end, left_pts, right_pts,
                             cos_la, sin_la, cos_ra, sin_ra, solve_side, build_mid)
    if v_use <= 0:
        return None
    return _tip_build_at(v_use, r_b, r_a, xi_start, xi_end, left_pts, right_pts,
                         cos_la, sin_la, cos_ra, sin_ra, solve_side, build_mid)


# ── round 策略对 (凸角双切圆角) ───────────────────────────────────────

def _round_side(
    value_mm: float, r_b: float, r_a: float, xi_start: float, xi_end: float,
    ca: float, sa: float, mirror: int,
) -> tuple[float, tuple, tuple, tuple] | None:
    """齿顶圆角单侧: (xi_f, f, t, (center, 齿面切线角))."""
    sol = _solve_tip_fillet(value_mm, r_b, r_a, xi_start, xi_end, ca, sa, mirror)
    if sol is None:
        return None
    xi_f, c, f, t = sol
    tx, ty = _rot((math.cos(xi_f), math.sin(xi_f)), ca, sa)
    if mirror < 0:
        ty = -ty
    return xi_f, f, t, (c, math.atan2(ty, tx))


def _round_mid(f_l, t_l, ex_l, f_r, t_r, ex_r, a_l, a_r, v, r_a) -> list[Segment]:
    c_l, tan_l = ex_l
    c_r, _ = ex_r
    return [_fillet_arc(f_l, t_l, c_l, v, tan_l),
            Arc(r_a, a_l, a_r),
            _fillet_arc(t_r, f_r, c_r, v, a_r + math.pi / 2.0)]


def _tip_round_middle(
    p: GearParams,
    r_b: float,
    r_a: float,
    xi_start: float,
    xi_end: float,
    left_pts: tuple,
    right_pts: tuple,
    cos_la: float,
    sin_la: float,
    cos_ra: float,
    sin_ra: float,
) -> list[Segment] | None:
    """齿顶圆角中间段, 超限自动收敛 (Q8)."""
    return _tip_middle(p.rho_tip * p.m_n, r_b, r_a, xi_start, xi_end, left_pts, right_pts,
                       cos_la, sin_la, cos_ra, sin_ra, _round_side, _round_mid)


def tip_fillet_actual_mm(p: GearParams) -> float:
    """齿顶圆角实际半径 [mm]: 请求可行则原值, 否则收敛到最大可行 (Q8)."""
    if p.tip_mode != "round" or p.rho_tip <= 0:
        return 0.0
    r_b, r_a, xi_start, xi_end, c_la, s_la, c_ra, s_ra, n = _tooth0_tip_context(p)
    left_pts = tuple(_rot(involute_point(r_b, xi), c_la, s_la) for xi in _linspace(xi_start, xi_end, n))
    right_pts = tuple(_rot((involute_point(r_b, xi)[0], -involute_point(r_b, xi)[1]), c_ra, s_ra)
                      for xi in _linspace(xi_start, xi_end, n))
    return _tip_feasible_mm(p.rho_tip * p.m_n, r_b, r_a, xi_start, xi_end, left_pts, right_pts,
                            c_la, s_la, c_ra, s_ra, _round_side, _round_mid)


def _ray_circle(
    f: tuple[float, float],
    d: tuple[float, float],
    r_a: float,
) -> tuple[float, float] | None:
    """射线 f + t·d 与圆心原点半径 r_a 圆的第一个交点 (t>0), 无则 None."""
    a = d[0] * d[0] + d[1] * d[1]
    b = 2.0 * (f[0] * d[0] + f[1] * d[1])
    cc = f[0] * f[0] + f[1] * f[1] - r_a * r_a
    disc = b * b - 4.0 * a * cc
    if disc < 0:
        return None
    sq = math.sqrt(disc)
    ts = [t for t in ((-b - sq) / (2.0 * a), (-b + sq) / (2.0 * a)) if t > 1e-9]
    if not ts:
        return None
    t = min(ts)
    return (f[0] + t * d[0], f[1] + t * d[1])


def _solve_tip_chamfer_side(
    c: float,
    r_b: float,
    r_a: float,
    xi_start: float,
    xi_end: float,
    ca: float,
    sa: float,
    mirror: int,
) -> tuple[float, tuple[float, float], tuple[float, float]] | None:
    """单侧齿顶倒角: 沿齿面量 c [mm] 得 P_f, 过 P_f 画与齿面切线 45° 线, 交齿顶圆.

    渐开线弧长 s(ξ) = (r_b/2)(ξ_end² − ξ²); 从角点回退 c 得 ξ_f。
    倒角线方向 = 齿面切线 ±45° (mirror=+1 左齿面齿侧 +45°, −1 右齿面 −45°)。

    Returns:
        (xi_f, P_f, P_t) 或 None (无解 → 收敛为锐齿顶)。
    """
    x2 = xi_end * xi_end - 2.0 * c / r_b
    if x2 <= 1e-12:
        return None
    xi_f = math.sqrt(x2)
    if xi_f <= xi_start + 1e-12:
        return None

    def pt(xi):
        x, y = involute_point(r_b, xi)
        if mirror < 0:
            y = -y
        return _rot((x, y), ca, sa)

    f = pt(xi_f)
    tx, ty = math.cos(xi_f), math.sin(xi_f)
    if mirror < 0:
        ty = -ty
    tx, ty = _rot((tx, ty), ca, sa)
    tan_ang = math.atan2(ty, tx)

    d_ang = tan_ang + math.pi / 4.0 if mirror > 0 else tan_ang - math.pi / 4.0
    inter = _ray_circle(f, (math.cos(d_ang), math.sin(d_ang)), r_a)
    if inter is None:
        return None
    return xi_f, f, inter


# ── chamfer 策略对 (45° 沿齿面) ──────────────────────────────────────

def _chamfer_side(
    value_mm: float, r_b: float, r_a: float, xi_start: float, xi_end: float,
    ca: float, sa: float, mirror: int,
) -> tuple[float, tuple, tuple, None] | None:
    """齿顶倒角单侧: (xi_f, f, t, None)."""
    sol = _solve_tip_chamfer_side(value_mm, r_b, r_a, xi_start, xi_end, ca, sa, mirror)
    if sol is None:
        return None
    xi_f, f, t = sol
    return xi_f, f, t, None


def _chamfer_mid(f_l, t_l, ex_l, f_r, t_r, ex_r, a_l, a_r, v, r_a) -> list[Segment]:
    return [Polyline((f_l, t_l)), Arc(r_a, a_l, a_r), Polyline((t_r, f_r))]


def _tip_chamfer_middle(
    p: GearParams,
    r_b: float,
    r_a: float,
    xi_start: float,
    xi_end: float,
    left_pts: tuple,
    right_pts: tuple,
    cos_la: float,
    sin_la: float,
    cos_ra: float,
    sin_ra: float,
) -> list[Segment] | None:
    """齿顶倒角中间段, 超限自动收敛 (Q8)."""
    return _tip_middle(p.chamfer_tip * p.m_n, r_b, r_a, xi_start, xi_end, left_pts, right_pts,
                       cos_la, sin_la, cos_ra, sin_ra, _chamfer_side, _chamfer_mid)


def tip_chamfer_actual_mm(p: GearParams) -> float:
    """齿顶倒角实际尺寸 [mm]: 请求可行则原值, 否则收敛到最大可行 (Q8)."""
    if p.tip_mode != "chamfer" or p.chamfer_tip <= 0:
        return 0.0
    r_b, r_a, xi_start, xi_end, c_la, s_la, c_ra, s_ra, n = _tooth0_tip_context(p)
    left_pts = tuple(_rot(involute_point(r_b, xi), c_la, s_la) for xi in _linspace(xi_start, xi_end, n))
    right_pts = tuple(_rot((involute_point(r_b, xi)[0], -involute_point(r_b, xi)[1]), c_ra, s_ra)
                      for xi in _linspace(xi_start, xi_end, n))
    return _tip_feasible_mm(p.chamfer_tip * p.m_n, r_b, r_a, xi_start, xi_end, left_pts, right_pts,
                            c_la, s_la, c_ra, s_ra, _chamfer_side, _chamfer_mid)


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
    # ADR-014: 齿根圆角开关。root_fillet=False 时跳过双切求解 (锐齿根)。
    # solve_root_fillet 已支持 r_b<=r_f (无根切高齿数: 齿面-齿根圆连接角圆角);
    # 深齿根无双切解时抛 ValueError → 回退径向连接线 (方案 B/T13 未销项)。
    if p.root_fillet:
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
        segs.append(Arc(fil.rho, a0, a1, center=c_l, clockwise=True))

    # T02/T03 (ADR-014): 齿顶处理。默认 tip_mode='none' 走原路径零变化;
    # round/chamfer 由 _tip_*_middle 返回中间段, 无解时回退锐齿顶。
    tip_middle: list[Segment] | None = None
    if p.tip_mode == "round" and p.rho_tip > 0:
        tip_middle = _tip_round_middle(
            p, r_b, r_a, xi_start, xi_end, left_pts, right_pts,
            cos_la, sin_la, cos_ra, sin_ra,
        )
    elif p.tip_mode == "chamfer" and p.chamfer_tip > 0:
        tip_middle = _tip_chamfer_middle(
            p, r_b, r_a, xi_start, xi_end, left_pts, right_pts,
            cos_la, sin_la, cos_ra, sin_ra,
        )
    if tip_middle is not None:
        segs.extend(tip_middle)
    else:
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
        segs.append(Arc(fil.rho, a0, a1, center=c_r, clockwise=True))
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


def neighborhood_segments(p: GearParams, n: int = 3) -> list[Segment]:
    """以第 0 齿为中心的 n 齿**连续**齿廓段（开放链，CCW 遍历）.

    每齿开放段（含齿根过渡圆角 ρ*_f·m_n，K-1.12/ISO 53）+ 齿根连接弧
    （右齿根 → 下一齿左齿根），首尾开放不闭合——即「三齿连成一体」的廓形。

    Args:
        p: 齿轮参数
        n: 齿数（默认 3：左 1 + 目标 + 右 1）
    """
    z = p.z_w
    half = (n - 1) // 2
    segs: list[Segment] = []
    for j in range(-half, half + 1):
        idx = j % z
        open_segs, conn, *_ = _tooth_open_segments(p, idx, n_involute=40)
        segs.extend(open_segs)
        if j < half:
            segs.extend(conn)
    return segs


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

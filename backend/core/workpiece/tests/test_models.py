"""Tests for data models (GearParams, WorkpieceResult) and pure-math profile (K-1.1, K-1.2).

Verification against design book:
- §4.1.3 K-1.1 渐开线
- §4.1.3 K-1.2 端面/法向换算
- §6 算例1 (ex1_analytic.json)
"""

import math
import pytest


class TestNormalToTransverseConversion:
    """K-1.2 端面/法向换算"""

    def test_spur_gear_no_conversion(self):
        """β=0 直齿轮: m_t = m_n, α_t = α_n"""
        from core.workpiece.models import normal_to_transverse

        m_t, alpha_t = normal_to_transverse(
            m_n=2.5, alpha_n_deg=20.0, beta_deg=0.0
        )
        assert m_t == pytest.approx(2.5)
        assert alpha_t == pytest.approx(20.0)

    def test_helical_ex1_pinion(self):
        """算例1 产形轮 (β=15°): m_t ≈ 2.070552, α_t ≈ 20.6469°"""
        from core.workpiece.models import normal_to_transverse

        m_t, alpha_t = normal_to_transverse(
            m_n=2.0, alpha_n_deg=20.0, beta_deg=15.0
        )
        assert m_t == pytest.approx(2.070552, rel=1e-5)
        assert alpha_t == pytest.approx(20.6469, rel=1e-4)

    def test_helical_high_angle(self):
        """β=30° 中等螺旋角"""
        from core.workpiece.models import normal_to_transverse

        m_t, alpha_t = normal_to_transverse(
            m_n=3.0, alpha_n_deg=20.0, beta_deg=30.0
        )
        # m_t = 3.0 / cos(30°) = 3.0 / 0.866025 = 3.4641...
        assert m_t == pytest.approx(3.0 / math.cos(math.radians(30.0)))
        # tan(α_t) = tan(20°) / cos(30°)
        expected_tan = math.tan(math.radians(20.0)) / math.cos(math.radians(30.0))
        expected_alpha_t = math.degrees(math.atan(expected_tan))
        assert alpha_t == pytest.approx(expected_alpha_t)


class TestInvoluteProfile:
    """K-1.1 渐开线廓形（端面）"""

    def test_base_circle_point(self):
        """ξ=0 时渐开线起点在基圆上: (r_b, 0)"""
        from core.workpiece.profile import involute_point

        r_b = 50.0
        x, y = involute_point(r_b, xi=0.0)
        assert x == pytest.approx(r_b)
        assert y == pytest.approx(0.0)

    def test_involute_parametric_form(self):
        """验证渐开线公式: x = r_b(cosξ + ξ sinξ), y = r_b(sinξ − ξ cosξ)"""
        from core.workpiece.profile import involute_point
        import math

        r_b = 50.0
        xi = 0.3
        x, y = involute_point(r_b, xi)
        expected_x = r_b * (math.cos(xi) + xi * math.sin(xi))
        expected_y = r_b * (math.sin(xi) - xi * math.cos(xi))
        assert x == pytest.approx(expected_x)
        assert y == pytest.approx(expected_y)

    def test_involute_monotonic(self):
        """渐开线随 ξ 增加向外展开"""
        from core.workpiece.profile import involute_point

        r_b = 50.0
        _, y1 = involute_point(r_b, 0.0)
        _, y2 = involute_point(r_b, 0.2)
        _, y3 = involute_point(r_b, 0.5)
        # 渐开线在第一象限展开，y 单调递增
        assert y1 < y2 < y3

    def test_involute_generates_expected_radius(self):
        """渐开线上任意点半径 r(ξ) = r_b·√(1+ξ²)"""
        from core.workpiece.profile import involute_point
        import math

        r_b = 50.0
        xi = 0.5
        x, y = involute_point(r_b, xi)
        r = math.sqrt(x * x + y * y)
        expected_r = r_b * math.sqrt(1 + xi * xi)
        assert r == pytest.approx(expected_r)

    def test_ex1_pinion_involute_start(self):
        """算例1 产形轮基圆 r_b1 = d_b1/2 = 39.728mm"""
        from core.workpiece.profile import involute_point

        r_b1 = 79.456 / 2.0  # d_b1 from [23]表3.2
        x, y = involute_point(r_b1, xi=0.0)
        assert x == pytest.approx(r_b1)
        assert y == pytest.approx(0.0)

    def test_generate_full_profile(self):
        """生成渐开线点集: 从基圆到齿顶圆"""
        from core.workpiece.profile import generate_involute_points

        r_b = 48.0  # 基圆半径
        r_a = 54.0  # 齿顶圆半径
        n_points = 50
        points = generate_involute_points(r_b, r_a, n_points)

        assert len(points) == n_points
        # 第一点在基圆上
        assert abs(math.sqrt(points[0][0]**2 + points[0][1]**2) - r_b) < 1e-8
        # 最后一点接近齿顶圆
        r_last = math.sqrt(points[-1][0]**2 + points[-1][1]**2)
        assert abs(r_last - r_a) < 1e-6


class TestGearParams:
    """GearParams 数据类"""

    def test_default_values(self):
        """默认值与前端 gearParams 对齐"""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=2.5, z_w=41, b_w=20.0)
        assert p.profile_type == "involute"
        assert p.k_io == 1
        assert p.alpha_n_deg == 20.0
        assert p.h_an == 1.0
        assert p.c_n == 0.25
        assert p.rho_f == 0.38
        assert p.x_w == 0.0
        assert p.beta_w_deg == 0.0
        assert p.j_w == 1
        assert p.tooth_method == "x_w"

    def test_minimal_required_fields(self):
        """必填字段: m_n, z_w, b_w"""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=3.0, z_w=20, b_w=15.0)
        assert p.m_n == 3.0
        assert p.z_w == 20
        assert p.b_w == 15.0

    def test_normal_to_transverse_method(self):
        """模型方法: normal_to_transverse()"""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, beta_w_deg=15.0)
        m_t, alpha_t = p.to_transverse()
        assert m_t == pytest.approx(2.070552, rel=1e-5)
        assert alpha_t == pytest.approx(20.6469, rel=1e-4)

    def test_pitch_radius(self):
        """分度圆半径: r = m_t * z / 2"""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=2.5, z_w=41, b_w=20.0)
        # β=0 → m_t = m_n
        r_pw = p.pitch_radius()
        assert r_pw == pytest.approx(2.5 * 41 / 2.0)  # = 51.25

    def test_base_radius(self):
        """基圆半径: r_b = r_pw * cos(α_t)"""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=2.5, z_w=41, b_w=20.0)
        r_b = p.base_radius()
        r_pw = 2.5 * 41 / 2.0
        expected = r_pw * math.cos(math.radians(20.0))
        assert r_b == pytest.approx(expected)

    def test_tip_diameter(self):
        """齿顶圆直径: d_a = m_t*z_w + 2*h_an*m_n (标准齿)"""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=2.5, z_w=41, b_w=20.0)
        d_a = p.tip_diameter()
        expected = 2.5 * 41 + 2 * 1.0 * 2.5  # = 102.5 + 5 = 107.5
        assert d_a == pytest.approx(expected)

    def test_root_diameter(self):
        """齿根圆直径: d_f = m_t*z_w - 2*(h_an+c_n)*m_n (标准齿)"""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=2.5, z_w=41, b_w=20.0)
        d_f = p.root_diameter()
        expected = 2.5 * 41 - 2 * (1.0 + 0.25) * 2.5  # = 102.5 - 6.25 = 96.25
        assert d_f == pytest.approx(expected)


class TestInternalGearGeometry:
    """内齿轮 k_io=−1 — ISO 负齿数模型公式 (ADR-015, spec §4.1)."""

    def test_internal_da_df_formulas(self):
        """内齿: d_a = z·m_t − 2(h_an+x)m_n (小径), d_f = z·m_t + 2(h_an+c_n−x)m_n (大径), d_a < d_f."""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, x_w=0.0)
        m_t, _ = p.to_transverse()
        exp_da = p.z_w * m_t - 2.0 * (p.h_an + p.x_w) * p.m_n
        exp_df = p.z_w * m_t + 2.0 * (p.h_an + p.c_n - p.x_w) * p.m_n
        assert p.tip_diameter() == pytest.approx(exp_da)
        assert p.root_diameter() == pytest.approx(exp_df)
        assert p.tip_diameter() < p.root_diameter()

    def test_internal_radius_methods(self):
        """内齿半径方法: tip=小径/2, root=大径/2."""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, x_w=0.0)
        assert p.tip_radius() == pytest.approx(p.tip_diameter() / 2.0)
        assert p.root_radius() == pytest.approx(p.root_diameter() / 2.0)
        assert p.tip_radius() < p.root_radius()

    def test_internal_full_tooth_height_invariant(self):
        """全齿高不变量: (d_f−d_a)/2 = 2·h_an + c_n, 随任意 x_w 不漂移."""
        from core.workpiece.models import GearParams

        for x in (-0.5, 0.0, 0.5):
            p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, x_w=x)
            h = (p.root_diameter() - p.tip_diameter()) / 2.0
            assert h == pytest.approx((2.0 * p.h_an + p.c_n) * p.m_n)

    def test_internal_tooth_thickness_positive_shift(self):
        """内齿 +x 变厚 (ISO 约定 Q5): s_t(0.5) > s_t(0); 标准齿 x=0: s_t = π·m_t/2."""
        from core.workpiece.models import GearParams, compute_tooth_thickness

        p_std = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, x_w=0.0)
        p_pos = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, x_w=0.5)
        assert compute_tooth_thickness(p_pos) > compute_tooth_thickness(p_std)
        m_t, _ = p_std.to_transverse()
        assert compute_tooth_thickness(p_std) == pytest.approx(math.pi * m_t / 2.0)

    def test_internal_m_round_trip(self):
        """内齿跨棒距往返: x_w → M → x_w 收敛 (M = d_b/cos(α_M) − d_p, 偶数齿).

        ⚠️ T13 未销: inv(α_M)→x 关系式的物理正确性未获独立主源证实,
        本测试仅锁**内齿 M 分支自洽**（防回归护栏）。研究见
        docs/research/内齿轮工件几何.md ②开放问题。
        """
        from core.workpiece.models import back_solve_x_w_from_M, GearParams

        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, x_w=0.2)
        m_t, alpha_t_deg = p.to_transverse()
        alpha_t = math.radians(alpha_t_deg)
        alpha_n = math.radians(p.alpha_n_deg)

        d_p = 1.44 * m_t  # 内齿轮推荐量棒径 ≈1.44×m_n
        d_b = 2.0 * p.base_radius()

        # 正向: inv(α_M) = inv(α_t) + d_p/d_b − π/(2z) + 2x·tan(α_n)/z (与 back_solve 同假定)
        inv_at = math.tan(alpha_t) - alpha_t
        inv_aM = inv_at + d_p / d_b - math.pi / (2.0 * p.z_w) + 2.0 * p.x_w * math.tan(alpha_n) / p.z_w
        aM_guess = alpha_t + 0.2
        for _ in range(30):
            f = math.tan(aM_guess) - aM_guess - inv_aM
            df = math.tan(aM_guess) ** 2
            aM_guess -= f / df
            if abs(f) < 1e-14:
                break
        alpha_M = aM_guess

        # 内齿轮跨棒距: M = d_b/cos(α_M) − d_p（偶数齿；跨齿槽内量棒之间）
        M = d_b / math.cos(alpha_M) - d_p

        x_w_solved = back_solve_x_w_from_M(p, M, d_p)
        assert abs(x_w_solved - 0.2) < 0.02


class TestInternalGearProfile:
    """内齿轮 k_io=−1 — 端面齿廓 (S5, spec §4.2)."""

    def test_internal_profile_tip_small_root_large(self):
        """内齿廓: 轮廓点 min 半径 ≈ 齿顶小径 d_a/2, max ≈ 齿根大径 d_f/2."""
        from core.workpiece.models import GearParams
        from core.workpiece.profile import sample_profile_points

        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, root_fillet=True)
        pts = sample_profile_points(p)
        radii = [math.hypot(x, y) for x, y in pts]
        assert min(radii) == pytest.approx(p.tip_diameter() / 2.0, rel=1e-6)
        assert max(radii) == pytest.approx(p.root_diameter() / 2.0, rel=1e-6)
        assert min(radii) < max(radii)

    def test_internal_no_fillet_arcs(self):
        """内齿锐顶锐根无圆角段 (Q3): 单齿廓所有弧段圆心在原点, 无 fillet 弧."""
        from core.workpiece.models import GearParams
        from core.workpiece.profile import single_tooth_segments, Arc

        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, root_fillet=True)
        segs = single_tooth_segments(p)
        for seg in segs:
            if isinstance(seg, Arc):
                assert math.hypot(*seg.center) < 1e-9, f"内齿不应有圆角弧: center={seg.center}"


class TestInternalGearGap:
    """内齿轮齿槽廓形 tooth_gap_segments (ADR-017: Boolean Cut 构造用).

    齿槽（齿间隙）= 相邻两齿之间空隙: 右齿面 + 齿根弧 + 下一齿左齿面 + 齿顶弧。
    与 single_tooth_segments（齿形）互补铺满 [d_a, d_f] 环带。
    """

    @staticmethod
    def _sample(segs, n=24):
        """段序列 → 去重点列."""
        from core.workpiece.profile import Arc, Polyline
        pts: list[tuple[float, float]] = []
        for seg in segs:
            if isinstance(seg, Polyline):
                pts.extend(seg.points)
            else:
                cx, cy = seg.center
                a0, a1 = seg.a0, seg.a1
                for j in range(n + 1):
                    ang = a0 + (a1 - a0) * j / n
                    pts.append((cx + seg.radius * math.cos(ang),
                                cy + seg.radius * math.sin(ang)))
        out = [pts[0]]
        for pt in pts[1:]:
            if math.dist(out[-1], pt) > 1e-9:
                out.append(pt)
        return out

    @staticmethod
    def _signed_area(pts):
        s = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            s += x0 * y1 - x1 * y0
        return s / 2.0

    def test_gap_bounding_radii(self):
        """齿槽廓形: min 半径 ≈ r_a(小径), max ≈ r_f(大径), min < max."""
        from core.workpiece.profile import tooth_gap_segments
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        pts = self._sample(tooth_gap_segments(p, 0))
        radii = [math.hypot(x, y) for x, y in pts]
        assert min(radii) == pytest.approx(p.tip_radius(), rel=1e-4)
        assert max(radii) == pytest.approx(p.root_radius(), rel=1e-4)
        assert min(radii) < max(radii)

    def test_gap_is_closed_ccw(self):
        """齿槽廓形闭合且 CCW (有向面积 > 0, 供 MakeFace/Prism 正体积)."""
        from core.workpiece.profile import tooth_gap_segments
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        pts = self._sample(tooth_gap_segments(p, 0))
        assert math.dist(pts[0], pts[-1]) < 1e-9
        assert self._signed_area(pts) > 0.0

    def test_gap_area_matches_analytic(self):
        """齿槽面积 = 极坐标解析积分（独立闭式，非对单齿廓取差）.

        齿槽 θ 宽(r) = pitch − 2·half + 2·inv(α_t) − 2·J(r), J(r)=ξ−atan(ξ), ξ=√((r/r_b)²−1):
          A = (pitch−2·half+2·inv_at)·(r_f²−r_a²)/2 − 2·∫_{r_a}^{r_f} J(r)·r dr
          ∫J·r dr = r_b²·[ξ³/3 − (ξ²+1)/2·atan(ξ) + ξ/2]
        """
        from core.workpiece.profile import (
            tooth_gap_segments, tooth_thickness_half_angle, involute_phase,
        )
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        r_a, r_f, r_b = p.tip_radius(), p.root_radius(), p.base_radius()
        half = tooth_thickness_half_angle(p)
        inv_at = involute_phase(p)
        pitch = 2.0 * math.pi / p.z_w

        def _intJ(r):
            xi = math.sqrt((r / r_b) ** 2 - 1.0)
            return r_b ** 2 * (xi ** 3 / 3.0 - (xi ** 2 + 1.0) / 2.0 * math.atan(xi) + xi / 2.0)

        gap_analytic = (pitch - 2.0 * half + 2.0 * inv_at) * (r_f ** 2 - r_a ** 2) / 2.0 \
            - 2.0 * (_intJ(r_f) - _intJ(r_a))
        gap_sampled = abs(self._signed_area(self._sample(tooth_gap_segments(p, 0))))
        assert gap_sampled == pytest.approx(gap_analytic, rel=1e-3)

    def test_gap_area_invariant_across_xw(self):
        """齿槽面积随 x 变化 (x 大 → 齿厚大 → 齿槽小)."""
        from core.workpiece.profile import tooth_gap_segments
        from core.workpiece.models import GearParams
        p0 = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, x_w=0.0)
        p5 = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, x_w=0.5)
        a0 = abs(self._signed_area(self._sample(tooth_gap_segments(p0, 0))))
        a5 = abs(self._signed_area(self._sample(tooth_gap_segments(p5, 0))))
        assert a5 < a0

    def test_gap_helical_theta_offset(self):
        """齿槽廓形带 theta_offset (斜齿截面扭转): 全点绕原点旋转 offset."""
        from core.workpiece.profile import tooth_gap_segments
        from core.workpiece.models import GearParams
        import math as _m
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, beta_w_deg=15.0)
        off = 0.3
        pts_off = self._sample(tooth_gap_segments(p, 0, theta_offset=off))
        pts_0 = self._sample(tooth_gap_segments(p, 0, theta_offset=0.0))
        ca, sa = _m.cos(off), _m.sin(off)
        for (x, y) in pts_0:
            xr, yr = x * ca - y * sa, x * sa + y * ca
            assert any(_m.hypot(xr - xx, yr - yy) < 1e-6 for xx, yy in pts_off), \
                f"旋转点 {(xr, yr)} 不在 offset 齿槽上"


class TestInternalGearValidation:
    """内齿轮 k_io=−1 — __post_init__ 校验 (Q8/Q4/Q2/Q1, spec §4.4)."""

    def test_internal_da_below_base_rejected(self):
        """d_a < d_b（齿顶落入基圆内，渐开线无法到达）→ ValueError (Q8)."""
        from core.workpiece.models import GearParams

        with pytest.raises(ValueError, match="齿顶"):
            GearParams(m_n=2.0, z_w=20, b_w=20.0, k_io=-1)

    def test_internal_helical_accepts(self):
        """内斜齿 β_w>0 现已支持 (ADR-017, 替代 Q4 阻塞)."""
        from core.workpiece.models import GearParams

        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, beta_w_deg=15.0)
        assert p.beta_w_deg == 15.0
        # 端面参数随 β 换算 (m_t/α_t)
        m_t, alpha_t = p.to_transverse()
        assert m_t > p.m_n
        assert alpha_t > p.alpha_n_deg

    def test_internal_helical_q8_beta_aware(self):
        """Q8 (d_a ≥ d_b) β 感知: 高 β 下 α_t 增大 → cos α_t 减小 → d_b 相对变小,
        最小齿数阈值下移. 例: z=28, β=0 阻塞; β=30 放行 (ADR-017 共享理解 G10)."""
        from core.workpiece.models import GearParams

        with pytest.raises(ValueError, match="齿顶"):
            GearParams(m_n=2.0, z_w=28, b_w=20.0, k_io=-1, beta_w_deg=0.0)
        p = GearParams(m_n=2.0, z_w=28, b_w=20.0, k_io=-1, beta_w_deg=30.0)
        m_t, alpha_t_deg = p.to_transverse()
        d_a = p.tip_diameter()
        d_b = p.z_w * m_t * math.cos(math.radians(alpha_t_deg))
        assert d_a >= d_b, f"β=30 时 d_a={d_a} 应 ≥ d_b={d_b}"

    def test_internal_w_k_rejected(self):
        """内齿 tooth_method=W_k → ValueError (Q2)."""
        from core.workpiece.models import GearParams

        with pytest.raises(ValueError, match="公法线"):
            GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1,
                       tooth_method="W_k", W_k=100.0, k_teeth=3)

    def test_internal_d_rim_clamped_to_minimum(self):
        """内齿 d_rim 过小/缺省 → 有效值钳制到 d_f + 2·m_n; 够大则原值 (Q9)."""
        from core.workpiece.models import GearParams

        p_small = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, d_rim=160.0)
        assert p_small.effective_rim_diameter() == pytest.approx(p_small.root_diameter() + 2.0 * p_small.m_n)
        p_none = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        assert p_none.effective_rim_diameter() == pytest.approx(p_none.root_diameter() + 2.0 * p_none.m_n)
        p_big = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, d_rim=180.0)
        assert p_big.effective_rim_diameter() == pytest.approx(180.0)


class TestWorkpieceResult:
    """WorkpieceResult 数据类"""

    def test_create_result(self):
        from core.workpiece.models import WorkpieceResult

        result = WorkpieceResult(
            d_a=107.5, d_f=96.25, r_b=48.164,
            r_pw=51.25, m_t=2.5, alpha_t_deg=20.0, z_w=41,
        )
        assert result.d_a == 107.5
        assert result.d_f == 96.25
        assert result.r_b == 48.164
        assert result.r_pw == 51.25

    def test_result_round_trip(self):
        """序列化/反序列化往返"""
        from core.workpiece.models import WorkpieceResult
        import json

        result = WorkpieceResult(
            d_a=107.5, d_f=96.25, r_b=48.164,
            r_pw=51.25, m_t=2.5, alpha_t_deg=20.0, z_w=41,
        )
        d = result.to_dict()
        restored = WorkpieceResult.from_dict(d)
        assert restored.d_a == result.d_a
        assert restored.r_b == result.r_b
        assert restored.alpha_t_deg == result.alpha_t_deg

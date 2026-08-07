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

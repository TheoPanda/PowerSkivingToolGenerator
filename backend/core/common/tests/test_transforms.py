"""Tests for K-0.x transform library (纯数学，不依赖 OCCT).

Verification against design book §2.4 formulas and §6 worked examples.
"""

import math
import numpy as np
import pytest


class TestRotX:
    """K-0.1 Rot_x(θ) — 右手定则绕 X 轴旋转"""

    def test_identity(self):
        """Rot_x(0) = I₄"""
        from core.common.transforms import rot_x
        result = rot_x(0.0)
        np.testing.assert_array_almost_equal(result, np.eye(4))

    def test_pi_half(self):
        """Rot_x(π/2): y → z, z → −y"""
        from core.common.transforms import rot_x
        result = rot_x(math.pi / 2)
        # 点 (0, 1, 0, 1) 应映射到 (0, 0, 1, 1)
        v = np.array([0.0, 1.0, 0.0, 1.0])
        rotated = result @ v
        np.testing.assert_array_almost_equal(rotated, [0.0, 0.0, 1.0, 1.0])

    def test_pi(self):
        """Rot_x(π): y → −y, z → −z"""
        from core.common.transforms import rot_x
        result = rot_x(math.pi)
        expected = np.array([
            [1, 0, 0, 0],
            [0, -1, 0, 0],
            [0, 0, -1, 0],
            [0, 0, 0, 1],
        ])
        np.testing.assert_array_almost_equal(result, expected)

    def test_negative_angle(self):
        """Rot_x(−θ) = Rot_x(θ)ᵀ (旋转矩阵的逆=转置)"""
        from core.common.transforms import rot_x
        θ = 0.7
        result = rot_x(-θ)
        expected = rot_x(θ).T
        np.testing.assert_array_almost_equal(result, expected)


class TestRotY:
    """K-0.1 Rot_y(θ)"""

    def test_identity(self):
        from core.common.transforms import rot_y
        result = rot_y(0.0)
        np.testing.assert_array_almost_equal(result, np.eye(4))

    def test_pi_half(self):
        """Rot_y(π/2): z → x, x → −z"""
        from core.common.transforms import rot_y
        result = rot_y(math.pi / 2)
        # 点 (0, 0, 1, 1) 应映射到 (1, 0, 0, 1)
        v = np.array([0.0, 0.0, 1.0, 1.0])
        rotated = result @ v
        np.testing.assert_array_almost_equal(rotated, [1.0, 0.0, 0.0, 1.0])

    def test_formula_match(self):
        """与设计书 §2.4 K-0.1 Rot_y 公式逐元素对照"""
        from core.common.transforms import rot_y
        θ = 0.5
        result = rot_y(θ)
        c, s = math.cos(θ), math.sin(θ)
        expected = np.array([
            [c, 0, s, 0],
            [0, 1, 0, 0],
            [-s, 0, c, 0],
            [0, 0, 0, 1],
        ])
        np.testing.assert_array_almost_equal(result, expected)


class TestRotZ:
    """K-0.1 Rot_z(θ)"""

    def test_identity(self):
        from core.common.transforms import rot_z
        result = rot_z(0.0)
        np.testing.assert_array_almost_equal(result, np.eye(4))

    def test_pi_half(self):
        """Rot_z(π/2): x → y, y → −x"""
        from core.common.transforms import rot_z
        result = rot_z(math.pi / 2)
        v = np.array([1.0, 0.0, 0.0, 1.0])
        rotated = result @ v
        np.testing.assert_array_almost_equal(rotated, [0.0, 1.0, 0.0, 1.0])

    def test_standard_form(self):
        """Rot_z 矩阵公式: [[c,-s,0,0],[s,c,0,0],[0,0,1,0],[0,0,0,1]]"""
        from core.common.transforms import rot_z
        θ = 0.3
        result = rot_z(θ)
        c, s = math.cos(θ), math.sin(θ)
        expected = np.array([
            [c, -s, 0, 0],
            [s, c, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ])
        np.testing.assert_array_almost_equal(result, expected)

    def test_array_rotation(self):
        """验证批量点绕 Z 轴旋转: 齿圈阵列的基础"""
        from core.common.transforms import rot_z
        θ = 2 * math.pi / 41  # 41 齿齿轮的齿距角
        result = rot_z(θ)
        # 单位圆上一点 (1, 0, 0, 1) 旋转 360/41 度
        v = np.array([1.0, 0.0, 0.0, 1.0])
        rotated = result @ v
        expected_angle = 2 * math.pi / 41
        np.testing.assert_array_almost_equal(
            rotated[:2],
            [math.cos(expected_angle), math.sin(expected_angle)],
        )


class TestTran:
    """K-0.2 Tran(axis, d) — 平移算子"""

    def test_tran_x(self):
        from core.common.transforms import tran_x
        result = tran_x(5.0)
        expected = np.array([
            [1, 0, 0, 5],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ])
        np.testing.assert_array_equal(result, expected)

    def test_tran_y(self):
        from core.common.transforms import tran_y
        result = tran_y(-3.0)
        expected = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, -3],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ])
        np.testing.assert_array_equal(result, expected)

    def test_tran_z(self):
        from core.common.transforms import tran_z
        result = tran_z(10.0)
        expected = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 10],
            [0, 0, 0, 1],
        ])
        np.testing.assert_array_equal(result, expected)

    def test_tran_zero(self):
        """平移 0 = 单位阵"""
        from core.common.transforms import tran_x, tran_y, tran_z
        np.testing.assert_array_equal(tran_x(0.0), np.eye(4))
        np.testing.assert_array_equal(tran_y(0.0), np.eye(4))
        np.testing.assert_array_equal(tran_z(0.0), np.eye(4))

    def test_compose_translations(self):
        """Tran(x, a) · Tran(y, b) = 相对于原点的复合平移"""
        from core.common.transforms import tran_x, tran_y
        T = tran_x(3.0) @ tran_y(4.0)
        expected = np.array([
            [1, 0, 0, 3],
            [0, 1, 0, 4],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ])
        np.testing.assert_array_equal(T, expected)


class TestHelicalSurface:
    """K-0.6 S_w(u, θ) — 工件螺旋面参数化"""

    def test_spur_gear_degenerates_to_planar(self):
        """β_w=0 时 z 分量恒为 0 → 退化为平面廓形"""
        from core.common.transforms import helical_surface
        # 任意 x0, y0 函数，β_w=0
        def x0(u):
            return float(u)
        def y0(u):
            return 0.0

        result = helical_surface(x0, y0, j_w=1, r_pw=50.0, beta_w=0.0, u=1.0, theta=0.5)
        assert result[2] == 0.0  # z 分量恒为 0

    def test_helical_z_component(self):
        """β_w≠0 时 z = j_w·θ·r_pw/tan(β_w)"""
        from core.common.transforms import helical_surface
        import math

        r_pw = 50.0
        beta_w = math.radians(15.0)  # 15° 螺旋角
        j_w = 1  # 右旋
        theta = math.pi / 6  # 30°

        def x0(u):
            return r_pw * math.cos(u)
        def y0(u):
            return r_pw * math.sin(u)

        result = helical_surface(x0, y0, j_w, r_pw, beta_w, u=0.0, theta=theta)
        expected_z = j_w * theta * r_pw / math.tan(beta_w)
        assert abs(result[2] - expected_z) < 1e-10

    def test_left_hand_helix(self):
        """j_w=−1 左旋：z 分量符号反转"""
        from core.common.transforms import helical_surface
        import math

        r_pw = 50.0
        beta_w = math.radians(15.0)
        theta = math.pi / 6

        def x0(u):
            return float(u)
        def y0(u):
            return 0.0

        right = helical_surface(x0, y0, j_w=1, r_pw=r_pw, beta_w=beta_w, u=1.0, theta=theta)
        left = helical_surface(x0, y0, j_w=-1, r_pw=r_pw, beta_w=beta_w, u=1.0, theta=theta)
        assert right[2] == -left[2]

    def test_theta_zero_preserves_profile(self):
        """θ=0 时螺旋面 = 原始廓形 (x0, y0, 0)"""
        from core.common.transforms import helical_surface

        def x0(u):
            return 2.0 * u
        def y0(u):
            return u * u

        result = helical_surface(x0, y0, j_w=1, r_pw=50.0, beta_w=0.3, u=3.0, theta=0.0)
        assert result[0] == x0(3.0)
        assert result[1] == y0(3.0)
        assert result[2] == 0.0


class TestTransformConventions:
    """验证 U1/U2/U6 约定"""

    def test_left_multiply_right_to_left(self):
        """U2: 复合变换左乘、从右向左施加"""
        from core.common.transforms import rot_z, tran_x

        # 先平移再旋转: Rot_z · Tran_x · v
        # 向量 v 先在 X 方向平移，再绕 Z 旋转
        v = np.array([1.0, 0.0, 0.0, 1.0])
        θ = math.pi / 2
        T = rot_z(θ) @ tran_x(2.0)
        result = T @ v

        # v=(1,0,0,1) → Tran_x(2): (3,0,0,1) → Rot_z(π/2): (0,3,0,1)
        np.testing.assert_array_almost_equal(result, [0.0, 3.0, 0.0, 1.0])

    def test_point_is_column_vector(self):
        """U1: 点为列向量 [x,y,z,1]ᵀ"""
        from core.common.transforms import rot_z

        v = np.array([1.0, 2.0, 3.0, 1.0])
        result = rot_z(math.pi) @ v
        np.testing.assert_array_almost_equal(result, [-1.0, -2.0, 3.0, 1.0])

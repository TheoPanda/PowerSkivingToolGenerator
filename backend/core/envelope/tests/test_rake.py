"""模块②a 前刀面（K-2.1）测试 — 纯数学，可入 CI."""

import math

import pytest

from core.envelope.rake import build_plane_rake, normal_arrow, plane_patch


class TestBuildPlaneRake:
    def test_example1_coefficients(self):
        """算例1 γ=5°、β_t=15°、r_pt=42.455 → A/B/C/const 精确吻合（容差 1e-6）."""
        s = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=42.455)
        assert s.A == pytest.approx(0.087156, abs=1e-6)
        assert s.B == pytest.approx(0.257834, abs=1e-6)
        assert s.C == pytest.approx(0.962250, abs=1e-6)
        # const = −A·r₁ 为派生量，设计书只给 4 位小数（−3.7002），且放大 A 的舍入 → 容差放宽到 1e-4
        assert s.const == pytest.approx(-3.7002, abs=1e-4)
        assert s.p_ref == pytest.approx((42.455, 0.0, 0.0), abs=1e-9)

    def test_unit_normal_invariant(self):
        """|(A,B,C)| = 1 不变量（任意 γ/β_t 组合）."""
        for gamma in (0.0, 5.0, 20.0, -15.0):
            for beta in (0.0, 15.0, 30.0):
                s = build_plane_rake(gamma_deg=gamma, beta_t_deg=beta, r_pt=42.455)
                norm = math.sqrt(s.A ** 2 + s.B ** 2 + s.C ** 2)
                assert norm == pytest.approx(1.0, abs=1e-12)

    def test_invalid_radius(self):
        with pytest.raises(ValueError):
            build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=0.0)


class TestGeometry:
    def test_patch_is_planar(self):
        """平面片 4 顶点均落在前刀面方程 F=0 上."""
        s = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=42.455)
        patch = plane_patch(s)
        assert len(patch.positions) == 12  # 4 顶点 × 3
        for i in range(4):
            x, y, z = patch.positions[3 * i:3 * i + 3]
            assert s.A * x + s.B * y + s.C * z + s.const == pytest.approx(0.0, abs=1e-6)

    def test_arrow_along_normal(self):
        """法矢箭头：起点 = P_ref，方向 = n_rake."""
        s = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=42.455)
        arrow = normal_arrow(s)
        assert arrow.positions[0:3] == pytest.approx(list(s.p_ref), abs=1e-9)
        tip = arrow.positions[3:6]
        length = math.dist(tip, s.p_ref)
        assert length > 0
        dx, dy, dz = tip[0] - s.p_ref[0], tip[1] - s.p_ref[1], tip[2] - s.p_ref[2]
        inv = 1.0 / length
        assert (dx * inv, dy * inv, dz * inv) == pytest.approx(s.n_rake, abs=1e-6)

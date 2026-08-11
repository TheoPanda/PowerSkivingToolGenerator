"""Integration tests for OCCT gear builder (K-1.12, K-1.13, ThruSections).

Requires: conda env power-skiving with pythonocc-core (OCP).

OCP 7.9.3 限制: TopoDS_Vertex 不能在 Python 层正确 downcast,
因此不使用 BRep_Tool.Pnt_s 测量。几何精度由 test_models.py 的纯数学测试覆盖。
"""

import math
import pytest

from core.workpiece.models import GearParams


@pytest.fixture
def spur_41() -> GearParams:
    """Standard spur gear: z=41, m_n=2.5."""
    return GearParams(m_n=2.5, z_w=41, b_w=20.0)


# ── Shape validity ───────────────────────────────────────────────────

class TestGearShapeValidity:
    """验证 OCCT 产出可用的几何体."""

    def test_build_returns_non_null(self, spur_41):
        """build_gear() 返回非空形状."""
        from core.workpiece.builder import build_gear
        shape = build_gear(spur_41)
        assert not shape.IsNull()

    def test_build_completes_without_error(self, spur_41):
        """无异常完成."""
        from core.workpiece.builder import build_gear
        shape = build_gear(spur_41)
        assert shape is not None

    def test_wire_is_closed(self, spur_41):
        """全齿圈 2D wire 闭合."""
        from core.workpiece.builder import _build_full_gear_2d_wire
        wire = _build_full_gear_2d_wire(spur_41)
        assert wire.Closed()

    def test_spur_gear_performance(self, spur_41):
        """直齿轮构建 < 5s (单次拉伸，无 Boolean union)."""
        import time
        from core.workpiece.builder import build_gear

        t0 = time.time()
        build_gear(spur_41)
        elapsed = time.time() - t0
        assert elapsed < 5.0, f"构建耗时 {elapsed:.1f}s > 5s"


# ── Gear type support ────────────────────────────────────────────────

class TestGearTypeSupport:
    """验证不同齿轮类型的构建."""

    def test_helical_gear_builds(self):
        """斜齿轮 (beta=15, z=10) — 原生 Wire 直接构建, 无需 downcast.

        z=10 是为了避免 Boolean fuse 41 齿的 O(n²) 耗时。
        """
        from core.workpiece.builder import build_gear
        p = GearParams(m_n=2.5, z_w=10, b_w=20.0, beta_w_deg=15.0)
        shape = build_gear(p, n_slices=6)
        assert not shape.IsNull()

    def test_helical_gear_with_tip_round_builds(self):
        """斜齿轮 + 齿顶圆角: 逐截面携带, ThruSections 放样正常 (ADR-014)."""
        from core.workpiece.builder import build_gear
        p = GearParams(m_n=2.5, z_w=10, b_w=20.0, beta_w_deg=15.0,
                       tip_mode="round", rho_tip=0.2)
        shape = build_gear(p, n_slices=6)
        assert not shape.IsNull()

    def test_internal_gear_tooth_wire(self):
        """内齿轮 (k_io=-1) 单齿 wire 构建闭合."""
        from core.workpiece.builder import build_full_tooth_wire
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0, k_io=-1)
        wire = build_full_tooth_wire(p)
        assert wire.Closed()

    def test_small_gear_builds(self):
        """小齿数齿轮 (z=20, m=3) 构建不报错."""
        from core.workpiece.builder import build_gear
        p = GearParams(m_n=3.0, z_w=20, b_w=15.0)
        shape = build_gear(p)
        assert not shape.IsNull()

    def test_large_gear_builds(self):
        """大齿数齿轮 (z=82, m=2) 构建不报错."""
        from core.workpiece.builder import build_gear
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0)
        shape = build_gear(p)
        assert not shape.IsNull()


# ── 跨表示一致性 (profile.py 单一权威) ────────────────────────────────

class TestCrossRepresentationConsistency:
    """OCCT wire 与 mesh 采样两表示必须一致.

    历史教训: 轮廓数学双份实现时, OCCT 齿根弧取到长弧而 mesh 侧正确,
    无任何测试察觉。面积一致性把守两表示分叉。
    """

    @pytest.mark.parametrize("params", [
        dict(m_n=2.5, z_w=41, b_w=20.0),
        dict(m_n=2.0, z_w=82, b_w=20.0),
    ])
    def test_occt_face_area_matches_sampled_polygon(self, params):
        """OCCT face 面积 ≈ 采样多边形鞋带面积 (相对差 < 1e-3)."""
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        from core.workpiece.builder import _build_full_gear_2d_wire
        from core.workpiece.profile import sample_profile_points

        p = GearParams(**params)
        wire = _build_full_gear_2d_wire(p)
        face = BRepBuilderAPI_MakeFace(wire).Face()
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        area_occt = props.Mass()

        pts = sample_profile_points(p)
        area_poly = 0.0
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            area_poly += x0 * y1 - x1 * y0
        area_poly = abs(area_poly) / 2.0

        rel = abs(area_occt - area_poly) / area_poly
        assert rel < 1e-3, (
            f"OCCT 面积 {area_occt:.1f} vs 采样多边形 {area_poly:.1f} (相对差 {rel:.2e})"
        )


# ── Tooth thickness back-solve (K-1.11) ──────────────────────────────

class TestToothThicknessBacksolve:
    """K-1.11 齿厚反算."""

    def test_from_x_w_direct(self):
        """x_w 直接输入: s_t = pi*m_t/2."""
        from core.workpiece.models import compute_tooth_thickness
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0, tooth_method="x_w", x_w=0.0)
        s_t = compute_tooth_thickness(p)
        m_t, _ = p.to_transverse()
        expected = math.pi * m_t / 2
        assert abs(s_t - expected) < 0.01

    def test_from_x_w_positive_shift(self):
        """正变位 x_w=+0.5: 齿厚 > 标准齿厚."""
        from core.workpiece.models import compute_tooth_thickness
        p_std = GearParams(m_n=2.5, z_w=41, b_w=20.0, x_w=0.0)
        p_pos = GearParams(m_n=2.5, z_w=41, b_w=20.0, x_w=0.5)
        assert compute_tooth_thickness(p_pos) > compute_tooth_thickness(p_std)

    def test_w_k_backsolve_consistency(self):
        """W_k 反算: x_w=0 时反推 x_w ≈ 0."""
        from core.workpiece.models import back_solve_x_w_from_W_k
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0)
        m_t, alpha_t_deg = p.to_transverse()
        alpha_t = math.radians(alpha_t_deg)
        alpha_n = math.radians(p.alpha_n_deg)
        k = round(p.z_w * alpha_t_deg / 180.0 + 0.5)
        inv_at = math.tan(alpha_t) - alpha_t
        W_k = p.m_n * math.cos(alpha_n) * ((k - 0.5) * math.pi + p.z_w * inv_at)
        x_w_solved = back_solve_x_w_from_W_k(p, W_k, k)
        assert abs(x_w_solved - 0.0) < 0.01

    def test_m_backsolve_consistency(self):
        """M 反算: 正向计算 M 再反推 x_w ≈ 原始值."""
        from core.workpiece.models import back_solve_x_w_from_M
        import math

        p = GearParams(m_n=2.5, z_w=41, b_w=20.0, x_w=0.2)
        m_t, alpha_t_deg = p.to_transverse()
        alpha_t = math.radians(alpha_t_deg)
        alpha_n = math.radians(p.alpha_n_deg)

        # 计算标准齿轮的 M 值
        d_p = 1.68 * m_t
        d_b = 2.0 * p.base_radius()

        # inv(alpha_M) = inv(alpha_t) + d_p/d_b - pi/(2*z_w) + 2*x_w*tan(alpha_n)/z_w
        inv_at = math.tan(alpha_t) - alpha_t
        inv_aM = inv_at + d_p / d_b - math.pi / (2.0 * p.z_w) + 2.0 * p.x_w * math.tan(alpha_n) / p.z_w

        # 数值求解 alpha_M
        aM_guess = alpha_t + 0.2
        for _ in range(30):
            f = math.tan(aM_guess) - aM_guess - inv_aM
            df = math.tan(aM_guess) ** 2
            aM_guess -= f / df
            if abs(f) < 1e-14:
                break
        alpha_M = aM_guess

        if p.k_io == 1:
            M = d_b / math.cos(alpha_M) + d_p
        else:
            M = d_b / math.cos(alpha_M) - d_p

        x_w_solved = back_solve_x_w_from_M(p, M, d_p)
        assert abs(x_w_solved - 0.2) < 0.02

    def test_negative_shift_backsolve(self):
        """负变位 x_w=-0.3: 反算正确."""
        from core.workpiece.models import compute_tooth_thickness, back_solve_x_w_from_W_k
        p = GearParams(m_n=2.5, z_w=41, b_w=20.0, x_w=-0.3)
        m_t, alpha_t_deg = p.to_transverse()
        alpha_t = math.radians(alpha_t_deg)
        alpha_n = math.radians(p.alpha_n_deg)
        k = round(p.z_w * alpha_t_deg / 180.0 + 0.5)
        inv_at = math.tan(alpha_t) - alpha_t
        # W_k with x_w=-0.3
        W_k = p.m_n * math.cos(alpha_n) * (
            (k - 0.5) * math.pi + p.z_w * inv_at + 2 * (-0.3) * math.tan(alpha_n)
        )
        x_w_solved = back_solve_x_w_from_W_k(p, W_k, k)
        assert abs(x_w_solved - (-0.3)) < 0.01


# ── Design book regression ────────────────────────────────────────────

class TestDesignBookRegression:
    """设计书算例回归."""

    def test_ex1_workpiece_wire_closed(self):
        """算例1 工件 (z=82, m=2): 全齿圈 wire 闭合."""
        from core.workpiece.builder import _build_full_gear_2d_wire
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0)
        wire = _build_full_gear_2d_wire(p)
        assert wire.Closed()

    def test_ex1_workpiece_builds(self):
        """算例1 工件构建不报错."""
        from core.workpiece.builder import build_gear
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0)
        shape = build_gear(p)
        assert not shape.IsNull()

    def test_ex2_workpiece_builds(self):
        """算例2 工件 (z=47, m=2.5) 构建不报错."""
        from core.workpiece.builder import build_gear
        p = GearParams(m_n=2.5, z_w=47, b_w=25.0)
        shape = build_gear(p)
        assert not shape.IsNull()


# ── Edge cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    """边界情况."""

    def test_minimum_teeth(self):
        """最少齿数 z=5."""
        from core.workpiece.builder import build_gear
        p = GearParams(m_n=5.0, z_w=5, b_w=10.0)
        shape = build_gear(p)
        assert not shape.IsNull()

    def test_pressure_angle_25(self):
        """大压力角 alpha_n=25."""
        from core.workpiece.builder import build_gear
        from core.workpiece.builder import _build_full_gear_2d_wire
        p = GearParams(m_n=3.0, z_w=30, b_w=15.0, alpha_n_deg=25.0)
        wire = _build_full_gear_2d_wire(p)
        assert wire.Closed()
        shape = build_gear(p)
        assert not shape.IsNull()

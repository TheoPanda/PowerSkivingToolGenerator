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


# ── 内齿轮环形实体 (T02) ───────────────────────────────────────────

class TestInternalGearSolid:
    """内齿轮 (k_io=−1) 环形实体: 外圈 d_rim + 内齿孔."""

    def test_internal_cap_face_has_two_wires(self):
        """cap_face 为环形: 2 条边界 wire (外圈 d_rim + 内齿孔)."""
        from core.workpiece.builder import build_gear_model
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_WIRE

        p = GearParams(m_n=2.0, z_w=41, b_w=20.0, k_io=-1, d_rim=120.0)
        model = build_gear_model(p)
        n_wires = 0
        ex = TopExp_Explorer(model.cap_face, TopAbs_WIRE)
        while ex.More():
            n_wires += 1
            ex.Next()
        assert n_wires == 2, f"内齿 cap_face 应有 2 条边界 wire (外圈+内孔), 实得 {n_wires}"

    def test_internal_solid_not_null(self):
        """内齿轮实体非空."""
        from core.workpiece.builder import build_gear_model

        p = GearParams(m_n=2.0, z_w=41, b_w=20.0, k_io=-1, d_rim=120.0)
        model = build_gear_model(p)
        assert not model.solid.IsNull()

    def test_internal_solid_volume_positive_and_bounded(self):
        """内齿轮实体体积 > 0, 且 < 外圈 d_rim 圆柱体积 (有孔)."""
        from core.workpiece.builder import build_gear_model
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp

        p = GearParams(m_n=2.0, z_w=41, b_w=20.0, k_io=-1, d_rim=120.0)
        model = build_gear_model(p)
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(model.solid, props)
        vol = props.Mass()
        rim_vol = math.pi * (p.d_rim / 2.0) ** 2 * p.b_w
        assert vol > 0.0
        assert vol < rim_vol, f"体积 {vol:.1f} ≥ 外圈圆柱体积 {rim_vol:.1f} (无孔?)"


# ── 内斜齿轮环形实体 (T02, ADR-017) ────────────────────────────────

class TestInternalHelicalSolid:
    """内斜齿轮 (k_io=−1, β_w>0) 实体 — Boolean Cut 构造 (ADR-017, G7)."""

    @pytest.fixture
    def internal_helical(self):
        return GearParams(m_n=2.0, z_w=41, b_w=20.0, k_io=-1, beta_w_deg=15.0, d_rim=120.0)

    @staticmethod
    def _volume(shape) -> float:
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, props)
        return props.Mass()

    @staticmethod
    def _analytic_volume(p: GearParams) -> float:
        """内齿解析期望体积 = (环形 [d_rim,d_a] − Σ齿槽) × b_w (ADR-017 G7)."""
        from core.workpiece.profile import tooth_gap_segments, Arc, Polyline

        def _sample(segs, n=24):
            pts = []
            for seg in segs:
                if isinstance(seg, Polyline):
                    pts.extend(seg.points)
                else:
                    cx, cy = seg.center
                    for j in range(n + 1):
                        ang = seg.a0 + (seg.a1 - seg.a0) * j / n
                        pts.append((cx + seg.radius * math.cos(ang),
                                    cy + seg.radius * math.sin(ang)))
            out = [pts[0]]
            for pt in pts[1:]:
                if math.dist(out[-1], pt) > 1e-9:
                    out.append(pt)
            return out

        gap_pts = _sample(tooth_gap_segments(p, 0))
        gap_area = 0.5 * abs(sum(
            x0 * y1 - x1 * y0
            for (x0, y0), (x1, y1) in zip(gap_pts, gap_pts[1:] + gap_pts[:1])
        ))
        r_rim = p.effective_rim_diameter() / 2.0
        r_a = p.tip_radius()
        return (math.pi * (r_rim ** 2 - r_a ** 2) - p.z_w * gap_area) * p.b_w

    def test_build_valid(self, internal_helical):
        """内斜齿实体非空且 BRepCheck 有效."""
        from core.workpiece.builder import build_gear_model
        from OCP.BRepCheck import BRepCheck_Analyzer
        model = build_gear_model(internal_helical, n_slices=6)
        assert not model.solid.IsNull()
        assert BRepCheck_Analyzer(model.solid).IsValid()

    def test_volume_matches_analytic(self, internal_helical):
        """G7: 内斜齿体积 ≈ 解析期望 (环形 [d_rim,d_a] − Σ齿槽) × b_w.

        ⚠️ 不能用同参数直齿对比: β 改变 m_t → d_a/d_f 全变, 齿轮几何不同。
        solid 为粗放样 (n_involute=8), 容差 5e-3。
        """
        from core.workpiece.builder import build_gear_model
        p = internal_helical
        v = self._volume(build_gear_model(p, n_slices=6).solid)
        expected = self._analytic_volume(p)
        assert v == pytest.approx(expected, rel=5e-3)
        assert v > 0.0

    @pytest.mark.parametrize("params", [
        # G9: 低齿数高β (β 放宽 Q8 → z=28 在 β=30 有效)
        dict(m_n=2.0, z_w=28, b_w=20.0, k_io=-1, beta_w_deg=30.0, d_rim=110.0),
        # G9: 高β + 宽齿宽 (大扭转 θ_total = b_w·tanβ/r_pw, 放样/网格压力)
        dict(m_n=2.0, z_w=41, b_w=40.0, k_io=-1, beta_w_deg=30.0, d_rim=120.0),
    ])
    def test_extreme_combos_build_valid(self, params):
        """G9: 极限组合构建有效 (BRepCheck) + 体积≈解析期望 (rel 5e-3) + < rim 圆柱."""
        from core.workpiece.builder import build_gear_model
        from OCP.BRepCheck import BRepCheck_Analyzer
        p = GearParams(**params)
        model = build_gear_model(p, n_slices=6)
        assert not model.solid.IsNull()
        assert BRepCheck_Analyzer(model.solid).IsValid(), "极限组合实体无效"
        v = self._volume(model.solid)
        assert v == pytest.approx(self._analytic_volume(p), rel=5e-3)
        rim_vol = math.pi * (p.effective_rim_diameter() / 2.0) ** 2 * p.b_w
        assert 0.0 < v < rim_vol

    def test_volume_bounded_by_rim_cylinder(self, internal_helical):
        """体积 < 外 rim 圆柱体积 (有内孔), > 0."""
        from core.workpiece.builder import build_gear_model
        p = internal_helical
        v = self._volume(build_gear_model(p, n_slices=6).solid)
        rim_vol = math.pi * (p.effective_rim_diameter() / 2.0) ** 2 * p.b_w
        assert 0.0 < v < rim_vol

    def test_cap_face_has_two_wires(self, internal_helical):
        """cap_face 环形: 2 条边界 wire (外 rim + 内齿廓孔), 供 exporter mesh."""
        from core.workpiece.builder import build_gear_model
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_WIRE
        model = build_gear_model(internal_helical, n_slices=6)
        n_wires = 0
        ex = TopExp_Explorer(model.cap_face, TopAbs_WIRE)
        while ex.More():
            n_wires += 1
            ex.Next()
        assert n_wires == 2

    def test_helical_sections_set(self, internal_helical):
        """helical_sections 含 n_slices+1 个截面, θ(z) 单调随 z 增大 (j_w=+1)."""
        from core.workpiece.builder import build_gear_model
        p = internal_helical
        model = build_gear_model(p, n_slices=6)
        secs = model.helical_sections
        assert secs is not None and len(secs) == 7
        zs = [z for z, _ in secs]
        thetas = [t for _, t in secs]
        assert zs == sorted(zs)
        assert thetas[0] == 0.0
        assert thetas[-1] == pytest.approx(
            p.j_w * p.b_w * math.tan(math.radians(p.beta_w_deg)) / p.pitch_radius()
        )

    def test_helical_sections_hand_flips(self):
        """j_w=−1 时 θ(z) 为负 (左旋)."""
        from core.workpiece.builder import build_gear_model
        p = GearParams(m_n=2.0, z_w=41, b_w=20.0, k_io=-1,
                       beta_w_deg=15.0, j_w=-1, d_rim=120.0)
        model = build_gear_model(p, n_slices=6)
        assert model.helical_sections[-1][1] < 0.0


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

"""模块②c 后刀面（K-2.18/2.19）测试 — 纯数学，可入 CI."""

import math

import pytest

from core.envelope.edge import extract_edge
from core.envelope.flank import compute_resharpen_schedule, generate_flank, generate_flank_helical_lead
from core.envelope.process_plan import compute_process_plan
from core.envelope.rake import build_plane_rake
from core.envelope.swept_cloud import extract_gap_points


class TestResharpenSchedule:
    def test_example2_golden_internal(self):
        """算例2 内齿轮：a=6.7938、L=2、n_L=4、α₀=8°、k_io=−1 → Δa_i 四段 golden."""
        sched = compute_resharpen_schedule(a=6.7938, L=2.0, n_L=4, alpha_0_deg=8.0, k_io=-1)
        assert [s.da for s in sched] == pytest.approx([0.07027, 0.14054, 0.21081, 0.28108], abs=1e-5)
        assert [s.a_i for s in sched] == pytest.approx([6.86407, 6.93434, 7.00461, 7.07488], abs=1e-5)
        assert [s.dL for s in sched] == pytest.approx([0.5, 1.0, 1.5, 2.0], abs=1e-12)

    def test_external_gear_direction(self):
        """外齿轮 k_io=+1：a_i = a − Δa_i（方向推导，T14）."""
        sched = compute_resharpen_schedule(a=6.7938, L=2.0, n_L=4, alpha_0_deg=8.0, k_io=+1)
        assert sched[0].da == pytest.approx(0.07027, abs=1e-5)
        assert sched[0].a_i == pytest.approx(6.7938 - 0.07027, abs=1e-5)

    def test_invalid(self):
        with pytest.raises(ValueError):
            compute_resharpen_schedule(a=6.0, L=0.0, n_L=4, alpha_0_deg=8.0, k_io=-1)
        with pytest.raises(ValueError):
            compute_resharpen_schedule(a=6.0, L=2.0, n_L=0, alpha_0_deg=8.0, k_io=-1)


class TestGenerateFlank:
    def _plan(self):
        return compute_process_plan(
            z_w=82, z_t=41, m_n=2.0,
            beta_w_deg=0.0, beta_t_deg=15.0,
            j_w=1, j_t=-1, k_io=-1,
        )

    def test_mesh_nonempty(self):
        """后刀面三角网非空 + 截面数 = n_L+1（含前刀面刃形）."""
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = self._plan()
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
        prof = extract_gap_points(p, n_points=50)
        flank = generate_flank(
            prof, plan, rake, L=2.0, n_L=4, alpha_0_deg=8.0, k_io=-1,
            m=31, theta_range_deg=20.0,
        )
        assert len(flank.schedule) == 4
        assert len(flank.mesh_positions) > 0
        assert len(flank.mesh_indices) > 0
        # 法向与 positions 等长
        assert len(flank.mesh_normals) == len(flank.mesh_positions)

    def test_external_gear_empty_edge_raises(self):
        """外齿轮（k_io=+1）刃形为空（T14 未销项）→ 抛明确 ValueError，而非底层 positions 为空."""
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=41, b_w=20.0, k_io=1)
        plan = compute_process_plan(
            z_w=41, z_t=41, m_n=2.0,
            beta_w_deg=0.0, beta_t_deg=15.0,
            j_w=1, j_t=-1, k_io=1,
        )
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
        prof = extract_gap_points(p, n_points=50)
        with pytest.raises(ValueError, match="T14"):
            generate_flank(
                prof, plan, rake, L=2.0, n_L=4, alpha_0_deg=8.0, k_io=1,
                m=31, theta_range_deg=20.0,
            )

    def test_flank_expands_along_axis(self):
        """后刀面沿 Z 轴展开（重磨轴向分量），不再塌在前刀面里（修复前 z 跨度仅 0.024mm）."""
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = self._plan()
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
        prof = extract_gap_points(p, n_points=50)
        flank = generate_flank(
            prof, plan, rake, L=2.0, n_L=4, alpha_0_deg=8.0, k_io=-1,
            m=31, theta_range_deg=20.0,
        )
        zs = [flank.mesh_positions[i] for i in range(2, len(flank.mesh_positions), 3)]
        z_span = max(zs) - min(zs)
        # 轴向展开应与总重磨量 L=2mm 同量级（修复前仅 ~0.024mm）
        assert z_span > 1.0

    def test_large_L_empty_section_raises(self):
        """重磨量 L 太大 → 某截面刃形为空 → 抛明确 ValueError，而非空 geometry."""
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = self._plan()
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
        prof = extract_gap_points(p, n_points=50)
        with pytest.raises(ValueError, match="刃形为空"):
            generate_flank(
                prof, plan, rake, L=5.0, n_L=4, alpha_0_deg=8.0, k_io=-1,
                m=31, theta_range_deg=20.0,
            )

    def test_helical_lead_constant_cross_section(self):
        """螺旋导程法（圆柱刀 K-2.15/16）：截面恒定——顶缘半径跨截面不变（无重磨集成法的径向膨胀）."""
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = self._plan()
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
        prof = extract_gap_points(p, n_points=50)
        flank = generate_flank_helical_lead(
            prof, plan, rake, z_t=41, m_n=2.0, beta_t_deg=15.0,
            L=2.0, n_L=4, k_io=-1, m=31, theta_range_deg=20.0,
        )
        # 导程 Ltp = z_t·m_n·π/sin β_t（算例1 = 995.33mm）
        assert flank.lead_pitch == pytest.approx(
            41 * 2.0 * math.pi / math.sin(math.radians(15.0)), rel=1e-9
        )
        # 截面恒定：后刀面顶缘半径 == 基刃形顶缘半径（螺旋扫掠纯旋转+平移，不改半径）
        edge = extract_edge(prof, plan, rake, m=31, theta_range_deg=20.0, k_io=-1)
        base_rmax = max(math.hypot(q[0], q[1]) for seg in edge.segments for q in seg.pts)
        flank_rs = [
            math.hypot(flank.mesh_positions[i], flank.mesh_positions[i + 1])
            for i in range(0, len(flank.mesh_positions), 3)
        ]
        assert max(flank_rs) == pytest.approx(base_rmax, abs=1e-6)
        # 沿 Z 轴展开（总重磨量 L=2mm 同量级）
        zs = [flank.mesh_positions[i] for i in range(2, len(flank.mesh_positions), 3)]
        assert max(zs) - min(zs) > 1.0

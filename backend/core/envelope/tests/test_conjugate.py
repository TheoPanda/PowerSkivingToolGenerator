"""模块②b 产形面（K-2.6 离散数值啮合）测试 — 纯数学，可入 CI."""

import math

import pytest

from core.envelope.conjugate import compute_conjugate_surface
from core.envelope.edge import extract_edge
from core.envelope.process_plan import compute_process_plan
from core.envelope.rake import build_plane_rake
from core.envelope.swept_cloud import extract_gap_points


def _internal_case():
    from core.workpiece.models import GearParams
    plan = compute_process_plan(
        z_w=82, z_t=41, m_n=2.0,
        beta_w_deg=0.0, beta_t_deg=15.0,
        j_w=1, j_t=-1, k_io=-1,
    )
    p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
    prof = extract_gap_points(p, n_points=50)[0]
    return p, plan, prof


class TestConjugateSurface:
    def test_full_coverage_and_mesh_nonempty(self):
        """内齿轮全点命中 + 三角网非空 + 法向与顶点等长."""
        p, plan, prof = _internal_case()
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=9, m=61, theta_range_deg=40.0,
        )
        assert surf.coverage["pass"] is True
        assert surf.coverage["found"] == surf.coverage["total_points"]
        assert len(surf.mesh_positions) > 0
        assert len(surf.mesh_indices) > 0
        assert len(surf.mesh_normals) == len(surf.mesh_positions)

    def test_barrel_shape_middle_widest(self):
        """产形面桶形：中段（z_gear=0）最大半径 > 端部（[12] barrel-shaped）."""
        p, plan, prof = _internal_case()
        n_z = 9
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=n_z, m=61, theta_range_deg=40.0,
        )
        n = len(prof)
        pts = [surf.mesh_positions[i:i + 3] for i in range(0, len(surf.mesh_positions), 3)]
        # 行主序 index = iz·n + iu；中段行 iz = n_z//2，端部行 iz = 0
        mid = pts[(n_z // 2) * n: (n_z // 2 + 1) * n]
        end = pts[0:n]
        mid_rmax = max(math.hypot(q[0], q[1]) for q in mid)
        end_rmax = max(math.hypot(q[0], q[1]) for q in end)
        assert mid_rmax > end_rmax

    def test_radius_consistent_with_edge(self):
        """产形面半径范围与刃形自洽（刃形 = 产形面 ∩ 前刀面）."""
        p, plan, prof = _internal_case()
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=9, m=61, theta_range_deg=40.0,
        )
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
        edge = extract_edge(prof, plan, rake, m=61, theta_range_deg=40.0, k_io=-1)
        conjugate_rs = [
            math.hypot(surf.mesh_positions[i], surf.mesh_positions[i + 1])
            for i in range(0, len(surf.mesh_positions), 3)
        ]
        edge_rs = [math.hypot(q[0], q[1]) for seg in edge.segments for q in seg.pts]
        # 刃形半径范围应落在产形面半径范围之内（容差 0.1mm，离散采样）
        assert min(conjugate_rs) <= min(edge_rs) + 0.1
        assert max(conjugate_rs) + 0.1 >= max(edge_rs)

    def test_invalid_inputs(self):
        p, plan, prof = _internal_case()
        with pytest.raises(ValueError):
            compute_conjugate_surface(prof, plan, b_w=0.0, k_io=-1)
        with pytest.raises(ValueError):
            compute_conjugate_surface(prof, plan, b_w=20.0, k_io=-1, n_z=1)
        with pytest.raises(ValueError):
            compute_conjugate_surface(prof, plan, b_w=20.0, k_io=-1, m=1)
        with pytest.raises(ValueError):
            compute_conjugate_surface([prof[0]], plan, b_w=20.0, k_io=-1)

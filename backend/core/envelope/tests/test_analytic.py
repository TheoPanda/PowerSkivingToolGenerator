"""模块②b 解析路线（K-2.8 + 双路线互检）测试 — 纯数学，可入 CI."""

import pytest

from core.envelope.analytic import compute_analytic_edge, cross_check
from core.envelope.edge import extract_edge
from core.envelope.process_plan import compute_process_plan
from core.envelope.rake import build_plane_rake
from core.envelope.swept_cloud import extract_gap_points


def _plan():
    return compute_process_plan(
        z_w=82, z_t=41, m_n=2.0,
        beta_w_deg=0.0, beta_t_deg=15.0,
        j_w=1, j_t=-1, k_io=-1,
    )


class TestAnalyticEdge:
    def test_edge_points_on_rake_face(self):
        """解析刃形点应落在前刀面方程 F=0 上（K-2.8 求交正确性）."""
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
        prof = extract_gap_points(p, n_points=100)
        edge = compute_analytic_edge(prof, plan, rake, theta_range_deg=20.0)
        assert len(edge) > 0
        for (x, y, z) in edge:
            assert rake.A * x + rake.B * y + rake.C * z + rake.const == pytest.approx(0.0, abs=1e-6)

    def test_cross_check_finite(self):
        """解析（二分）vs 离散（采样）刃形互检返回有限距离（均在前刀面，应极小）."""
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
        prof = extract_gap_points(p, n_points=100)
        analytic = compute_analytic_edge(prof, plan, rake, theta_range_deg=20.0)
        edge = extract_edge(prof, plan, rake, m=181, theta_range_deg=20.0, k_io=-1)
        discrete = [pt for seg in edge.segments for pt in seg.pts]
        result = cross_check(analytic, discrete)
        assert "max_delta_um" in result
        assert "pass" in result
        assert result["max_delta_um"] >= 0.0

    def test_cross_check_empty(self):
        """空输入 → 返回未通过（有限哨兵，避免 JSON 序列化 inf 崩溃）."""
        result = cross_check([], [])
        assert result["pass"] is False
        assert result["max_delta_um"] == 1e9

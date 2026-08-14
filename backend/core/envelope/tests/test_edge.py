"""模块②b 刃形（K-2.8 前刀面交线刃形）测试 — 纯数学，可入 CI.

刃形 = 前刀面 ∩ 生成面，本模块用 K-2.8 离散路线（扫掠采样 + 线性插值求前刀面
交点）。断言：刃形点落在前刀面 F=0 上、完整覆盖、左右两段、ffα 闭环自洽。
"""

import math

import pytest

from core.envelope.edge import compute_discrete_edge, extract_edge, split_flank_segments
from core.envelope.process_plan import compute_process_plan
from core.envelope.rake import build_plane_rake
from core.envelope.swept_cloud import extract_gap_points
from core.workpiece.models import GearParams


def _plan():
    """内齿轮安装方案（算例1 参数，标准渐开线）."""
    return compute_process_plan(
        z_w=82, z_t=41, m_n=2.0,
        beta_w_deg=0.0, beta_t_deg=15.0,
        j_w=1, j_t=-1, k_io=-1,
    )


def _rake(plan):
    return build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)


class TestComputeDiscreteEdge:
    def test_edge_points_on_rake_face(self):
        """离散刃形点应落在前刀面 F=0 上（线性插值误差 < 采样间隔，容差放宽）."""
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        rake = _rake(plan)
        prof = extract_gap_points(p, n_points=100)
        pts, roots, found = compute_discrete_edge(prof, plan, rake, m=181, theta_range_deg=20.0)
        assert len(pts) == len(roots) == len(prof)
        assert all(found)
        for (x, y, z) in pts:
            assert rake.A * x + rake.B * y + rake.C * z + rake.const == pytest.approx(0.0, abs=1e-4)


class TestSplitFlankSegments:
    def test_closed_loop_two_segments(self):
        """闭合环在半径极值处断开 → 两段."""
        pts = [[r * math.cos(t), r * math.sin(t), 0.0]
               for r, t in [(5.0, -0.5), (6.0, -0.3), (7.0, 0.0), (6.0, 0.3), (5.0, 0.5)]]
        segs = split_flank_segments(pts, closed=True)
        assert len(segs) == 2
        assert all(len(s) >= 2 for s in segs)

    def test_open_curve_two_segments(self):
        """开放曲线在半径极大(齿顶)处断开 → 两段."""
        pts = [[5.0, 0.0, 0.0], [6.0, 0.2, 0.0], [7.0, 0.0, 0.0], [6.0, -0.2, 0.0], [5.0, -0.3, 0.0]]
        segs = split_flank_segments(pts, closed=False)
        assert len(segs) == 2
        assert all(len(s) >= 2 for s in segs)

    def test_empty(self):
        assert split_flank_segments([], closed=True) == []


class TestExtractEdge:
    def test_segments_structure(self):
        """完整管线：左右两段 + coverage + ffα（闭环自洽，ffα 接近 0）."""
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        rake = _rake(plan)
        prof = extract_gap_points(p, n_points=200)
        edge = extract_edge(prof, plan, rake, m=181, theta_range_deg=20.0, k_io=-1)
        assert len(edge.segments) == 2
        for seg in edge.segments:
            assert len(seg.pts) > 0
            assert all(len(pt) == 3 for pt in seg.pts)
            assert seg.continuity in ("continuous", "discontinuous")
        assert "coverage_ratio" in edge.coverage_report
        assert edge.ffa_um >= 0.0
        # 闭环自洽：正向=反向逆 → ffα 应接近 0（数值误差量级，非绝对正确）
        assert edge.ffa_um < 1.0

    def test_full_coverage(self):
        """内齿轮：所有廓形点命中前刀面 → 覆盖 100%."""
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        rake = _rake(plan)
        prof = extract_gap_points(p, n_points=100)
        edge = extract_edge(prof, plan, rake, m=181, theta_range_deg=20.0, k_io=-1)
        assert edge.coverage_report["pass"] is True
        assert edge.coverage_report["coverage_ratio"] == 1.0

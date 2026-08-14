"""模块②b 刃形提取（K-2.10~2.13）测试 — 纯数学，可入 CI."""

import math

import numpy as np
import pytest

from core.envelope.edge import (
    compute_coverage,
    extract_edge,
    extract_inner_boundary,
    project_to_xy,
)
from core.envelope.swept_cloud import extract_gap_points, generate_envelope_cloud
from core.envelope.process_plan import compute_process_plan


def _plan():
    """内齿轮安装方案（算例1 参数，标准渐开线）."""
    return compute_process_plan(
        z_w=82, z_t=41, m_n=2.0,
        beta_w_deg=0.0, beta_t_deg=15.0,
        j_w=1, j_t=-1, k_io=-1,
    )


class TestProjectToXY:
    def test_project(self):
        cloud = np.array([[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]])
        out = project_to_xy(cloud)
        assert out.shape == (1, 2, 2)
        np.testing.assert_allclose(out[0, 0], [1.0, 2.0])


class TestExtractInnerBoundary:
    def test_fan_cloud(self):
        """半径 5~10、角度 ±30° 扇形点云 → 内边界（y 接近 0）上下两侧."""
        pts = []
        for r in np.linspace(5.0, 10.0, 40):
            for ang in np.linspace(-math.radians(30), math.radians(30), 50):
                pts.append((r * math.cos(ang), r * math.sin(ang)))
        cloud2d = np.array(pts)
        upper, lower = extract_inner_boundary(cloud2d, NR=40)
        assert len(upper) > 0
        assert len(lower) > 0
        # upper y≥0、lower y≤0（浮点容差）
        assert all(y >= -1e-6 for (_, y) in upper)
        assert all(y <= 1e-6 for (_, y) in lower)

    def test_empty(self):
        upper, lower = extract_inner_boundary(np.empty((0, 2)), NR=10)
        assert upper == [] and lower == []


class TestComputeCoverage:
    def test_full_coverage(self):
        """工件廓形与刃形同源 → 覆盖率≈1."""
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        prof = extract_gap_points(p, n_points=200)
        cloud = generate_envelope_cloud(prof, plan, m=181, theta_range_deg=20.0)
        edge = extract_edge(cloud.cloud, prof, plan, NR=200)
        assert edge.coverage_report["coverage_ratio"] > 0.9


class TestForwardEnvelopeFFa:
    def test_self_closure_small(self):
        """圆弧廓形自证闭环 → ffα 小（径向距离近似）."""
        plan = _plan()
        prof = [(plan.r_pw * math.cos(t), plan.r_pw * math.sin(t))
                for t in np.linspace(-0.05, 0.05, 100)]
        cloud = generate_envelope_cloud(prof, plan, m=181, theta_range_deg=20.0)
        edge = extract_edge(cloud.cloud, prof, plan, NR=200)
        assert edge.ffa_um < 50.0  # 径向距离近似，容差放宽


class TestExtractEdge:
    def test_segments_structure(self):
        """完整管线：左右两段 + continuity 标记 + coverage + ffα."""
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        prof = extract_gap_points(p, n_points=200)
        cloud = generate_envelope_cloud(prof, plan, m=181, theta_range_deg=20.0)
        edge = extract_edge(cloud.cloud, prof, plan, NR=200)
        assert len(edge.segments) >= 1
        for seg in edge.segments:
            assert len(seg.pts) > 0
            assert all(len(pt) == 3 for pt in seg.pts)
            assert seg.continuity in ("continuous", "discontinuous")
        assert "coverage_ratio" in edge.coverage_report
        assert edge.ffa_um >= 0.0

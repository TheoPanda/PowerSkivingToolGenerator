"""模块②b 离散包络点云（K-2.9）测试 — 纯数学，可入 CI."""

import numpy as np
import pytest

from core.envelope.gen_surface import extract_gap_points, generate_envelope_cloud
from core.envelope.process_plan import compute_process_plan


def _plan_ex2():
    """算例2 安装参数（内齿轮三圆弧，Σ=15°/a=6.7938/同步比 1.5）."""
    return compute_process_plan(
        z_w=102, z_t=68, m_n=0.399635,
        beta_w_deg=0.0, beta_t_deg=15.0,
        j_w=1, j_t=-1, k_io=-1,
    )


class TestGenerateEnvelopeCloud:
    """K-2.9 运动包络点云 + 三角网连片"""

    def test_cloud_shape(self):
        plan = _plan_ex2()
        pts = [(20.3814, 0.0), (20.0, 1.0), (19.0, 2.0)]
        cloud = generate_envelope_cloud(pts, plan, m=11, theta_range_deg=20.0)
        assert cloud.cloud.shape == (11, 3, 3)
        assert cloud.phi_t.shape == (11,)

    def test_single_point_center(self):
        """φ_t=0（中点）时首点 (r_pw,0) 变换后 x = r_pw−a（= r_pt 精确值）."""
        plan = _plan_ex2()
        pts = [(plan.r_pw, 0.0), (20.0, 0.0)]
        cloud = generate_envelope_cloud(pts, plan, m=181, theta_range_deg=20.0)
        mid = 90  # φ_t=0
        # φ_t=0 → φ_w=0 → M = Rot_x(−Σ)·Tran(x,−a)，y=z=0 不变 → x = r_pw − a
        np.testing.assert_allclose(cloud.cloud[mid, 0], [plan.r_pw - plan.a, 0.0, 0.0], atol=1e-6)

    def test_mesh_topology(self):
        """三角网每格两三角：(m−1)(n−1) 格 × 6 索引；顶点 m×n×3."""
        plan = _plan_ex2()
        pts = [(20.3814, 0.0), (20.0, 1.0), (19.0, 2.0)]
        n, m = 3, 11
        cloud = generate_envelope_cloud(pts, plan, m=m, theta_range_deg=20.0)
        assert len(cloud.mesh_positions) == m * n * 3
        assert len(cloud.mesh_indices) == (m - 1) * (n - 1) * 6
        # 索引范围合法
        assert max(cloud.mesh_indices) < m * n
        assert min(cloud.mesh_indices) >= 0

    def test_invalid_inputs(self):
        plan = _plan_ex2()
        with pytest.raises(ValueError, match="至少 2"):
            generate_envelope_cloud([(1.0, 0.0)], plan, m=11)
        with pytest.raises(ValueError, match="至少 2"):
            generate_envelope_cloud([(1.0, 0.0), (2.0, 0.0)], plan, m=1)


class TestExtractGapPoints:
    """从 GearParams 提取单齿槽廓形点（包络输入）"""

    def test_internal_gear_gap_points(self):
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        pts = extract_gap_points(p, n_points=200)
        assert len(pts) == 200
        assert all(len(pt) == 2 for pt in pts)
        # 点落在齿根/齿顶环带内（齿顶小径 80、齿根大径 84.5）
        radii = [np.hypot(x, y) for (x, y) in pts]
        assert min(radii) >= 79.0
        assert max(radii) <= 85.0

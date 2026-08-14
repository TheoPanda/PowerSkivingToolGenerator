"""模块②b 离散包络点云（K-2.9）测试 — 纯数学，可入 CI."""

import numpy as np
import pytest

from core.envelope.swept_cloud import WIREFRAME_COLOR, extract_gap_points, generate_envelope_cloud, jet
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


class TestJet:
    """jet 光谱色 ramp（蓝→青→绿→黄→红）"""

    def test_blue_start(self):
        r, g, b = jet(0.0)
        assert r == 0.0 and g == 0.0
        assert b > r and b > g  # 蓝端（b 主导）

    def test_red_end(self):
        r, g, b = jet(1.0)
        assert g == 0.0 and b == 0.0
        assert r > g and r > b  # 红端（r 主导）

    def test_green_midpoint(self):
        r, g, b = jet(0.5)
        assert g == 1.0
        assert g >= r and g >= b  # 中段过绿

    def test_wireframe_color_neutral_gray(self):
        assert WIREFRAME_COLOR == (0x1F / 255.0, 0x29 / 255.0, 0x37 / 255.0)


class TestSweptCloudVisualization:
    """扫掠点云顶点色 + 线框（可视化增强）"""

    def test_mesh_colors_spectral(self):
        plan = _plan_ex2()
        pts = [(20.3814, 0.0), (20.0, 1.0), (19.0, 2.0)]
        m, n = 11, 3
        cloud = generate_envelope_cloud(pts, plan, m=m, theta_range_deg=20.0)
        assert len(cloud.mesh_colors) == m * n * 3
        # 首顶点（行 0）蓝、末顶点（行 m−1）红
        assert cloud.mesh_colors[0:3] == [0.0, 0.0, 0.5]
        assert cloud.mesh_colors[-3:] == [1.0, 0.0, 0.0]

    def test_wireframe_indices_triangle_edges(self):
        plan = _plan_ex2()
        pts = [(20.3814, 0.0), (20.0, 1.0), (19.0, 2.0)]
        m, n = 11, 3
        cloud = generate_envelope_cloud(pts, plan, m=m, theta_range_deg=20.0)
        # 线框 = 三角片边、含重复共享边：每条三角片 3 边 × 2 索引 = 6，故 2×mesh_indices
        assert len(cloud.wireframe_indices) == 12 * (m - 1) * (n - 1)
        assert len(cloud.wireframe_indices) == 2 * len(cloud.mesh_indices)
        assert max(cloud.wireframe_indices) < m * n
        assert min(cloud.wireframe_indices) >= 0


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

    def test_external_gear_single_tooth_open_span(self):
        """外齿轮齿廓应为开放单齿（约一个齿距 4°），非 350° 根弧闭合."""
        import math
        from core.workpiece.models import GearParams
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=1)
        pts = extract_gap_points(p, n_points=200)
        assert len(pts) == 200
        # 角跨度 < 10°（一个齿距量级），杜绝 350° 闭合回归
        ang = [math.atan2(y, x) for (x, y) in pts]
        unw = [ang[0]]
        for a in ang[1:]:
            d = (a - unw[-1] + math.pi) % (2 * math.pi) - math.pi
            unw.append(unw[-1] + d)
        span = abs(unw[-1] - unw[0]) * 180 / math.pi
        assert span < 10.0
        # 半径落在齿根~齿顶环带内（外齿 79.5~84）
        radii = [math.hypot(x, y) for (x, y) in pts]
        assert min(radii) >= 79.0
        assert max(radii) <= 84.5

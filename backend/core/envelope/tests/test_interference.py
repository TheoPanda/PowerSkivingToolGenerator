"""模块②b 干涉热力图（K-2.6 符号距离着色）测试 — 纯数学，可入 CI."""

import math

import numpy as np
import pytest

from core.envelope.conjugate import compute_conjugate_surface
from core.envelope.interference import (
    _diverging_color,
    _nearest_distance,
    _point_in_polygon,
    compute_interference,
)
from core.envelope.process_plan import compute_process_plan
from core.envelope.swept_cloud import extract_gap_points
from core.workpiece.models import GearParams


def _case(z_t: int = 41):
    """内齿轮安装方案（算例1 参数，标准渐开线）."""
    plan = compute_process_plan(
        z_w=82, z_t=z_t, m_n=2.0,
        beta_w_deg=0.0, beta_t_deg=15.0,
        j_w=1, j_t=-1, k_io=-1,
    )
    p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
    prof = extract_gap_points(p, n_points=50)[0]
    return p, plan, prof


class TestPointInPolygon:
    def test_inside_outside(self):
        poly = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]])
        pts = np.array([[1.0, 1.0], [3.0, 3.0], [-1.0, 1.0]])
        inside = _point_in_polygon(poly, pts)
        assert inside[0] and not inside[1] and not inside[2]


class TestDivergingColor:
    def test_red_white_blue(self):
        d = np.array([-1.0, 0.0, 1.0])
        col = _diverging_color(d, 1.0)
        # 负 → 红 (1,0,0)，0 → 白 (1,1,1)，正 → 蓝 (0,0,1)
        assert col[0] == pytest.approx([1.0, 0.0, 0.0])
        assert col[1] == pytest.approx([1.0, 1.0, 1.0])
        assert col[2] == pytest.approx([0.0, 0.0, 1.0])

    def test_clamped_range(self):
        d = np.array([-5.0, 5.0])
        col = _diverging_color(d, 0.5)
        assert (col >= 0.0).all() and (col <= 1.0).all()


class TestInterference:
    def test_colors_aligned_and_valid(self):
        """顶点色与 positions 等长 + RGB ∈ [0,1] + 非全同色."""
        p, plan, prof = _case()
        res = compute_interference(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, n_z=5, m=61, theta_range_deg=40.0,
        )
        assert len(res.mesh_colors) == len(res.mesh_positions)
        assert len(res.mesh_normals) == len(res.mesh_positions)
        for v in res.mesh_colors:
            assert 0.0 <= v <= 1.0
        # 干涉(红)与间隙(蓝)并存 → 颜色非全同
        rs = {round(res.mesh_colors[i], 2) for i in range(0, len(res.mesh_colors), 3)}
        assert len(rs) > 1

    def test_tangency_band_exists(self):
        """正确啮合下存在相切带（白色 d≈0 点，接触线附近）."""
        p, plan, prof = _case()
        res = compute_interference(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, n_z=5, m=61, theta_range_deg=40.0,
        )
        white = 0
        for i in range(0, len(res.mesh_colors), 3):
            r, g, b = res.mesh_colors[i], res.mesh_colors[i + 1], res.mesh_colors[i + 2]
            if abs(r - 1.0) < 0.1 and abs(g - 1.0) < 0.1 and abs(b - 1.0) < 0.1:
                white += 1
        assert white > 0

    def test_offset_increases_interference(self):
        """中心距 a 偏离标准 → 干涉（符号距离为负）点数增多（标准啮合最优）.

        诊断：a+0.5 时干涉点 83→158、a+1.0 时 83→175（单调增）；直接测符号距离 d
        （compute_interference 的核心量），不经 color 饱和阈值（浅干涉不入饱和红）。
        """
        from core.common.transforms import apply_transform_batch, install_transform

        p, plan, prof = _case()
        single = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=5, m=61, theta_range_deg=40.0,
        )
        pos = single.mesh_positions
        n_vert = len(pos) // 3
        poly = np.array([(x, y) for x, y in prof])

        def count_interference(a_val: float) -> int:
            M = install_transform(a_val, math.radians(plan.sigma_deg))
            qws = np.empty((n_vert, 2))
            for i in range(n_vert):
                x, y, z = pos[3 * i], pos[3 * i + 1], pos[3 * i + 2]
                qw = apply_transform_batch(M, np.array([[x], [y], [z], [1.0]])).ravel()
                qws[i] = qw[:2]
            d_abs = _nearest_distance(qws, poly)
            inside = _point_in_polygon(poly, qws)
            d = np.where(inside, d_abs, -d_abs)
            return int((d < -0.01).sum())

        assert count_interference(plan.a + 0.5) > count_interference(plan.a)

    def test_vertex_count_z_t_multiples(self):
        """阵列后顶点数 = z_t 整数倍，且 > 0."""
        p, plan, prof = _case()
        res = compute_interference(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, n_z=5, m=61, theta_range_deg=40.0,
        )
        n_vert = len(res.mesh_positions) // 3
        assert n_vert > 0
        assert n_vert % 41 == 0

    def test_coverage_matches_single(self):
        """干涉热力图覆盖报告沿用单齿槽产形面."""
        p, plan, prof = _case()
        single = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=5, m=61, theta_range_deg=40.0,
        )
        res = compute_interference(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, n_z=5, m=61, theta_range_deg=40.0,
        )
        assert res.coverage == single.coverage

    def test_invalid_inputs(self):
        p, plan, prof = _case()
        with pytest.raises(ValueError):
            compute_interference(prof, plan, b_w=p.b_w, k_io=-1, z_t=0)
        with pytest.raises(ValueError):
            compute_interference(prof, plan, b_w=p.b_w, k_io=-1, z_t=41, clamp_mm=0.0)

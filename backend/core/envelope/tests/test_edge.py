"""模块②b 刃形（K-2.8 产形面 ∩ 前刀面）测试 — 纯数学，可入 CI.

刃形 = 产形面（共轭面）∩ 前刀面（Tsai 2023 step 3），本模块消元解 g=0 ∧ F=0。
断言：刃形点落在前刀面 F=0 上、落在产形面上（几何不变量，旧穿面法偏离 ~0.2mm
会被此判据抓住）、完整覆盖、左右两段、ffα 闭环自洽。
"""

import math

import numpy as np
import pytest

from core.envelope.conjugate import compute_conjugate_surface
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
        prof = extract_gap_points(p, n_points=100)[0]
        pts, roots, found = compute_discrete_edge(prof, plan, rake, m=181, theta_range_deg=40.0)
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
        prof = extract_gap_points(p, n_points=200)[0]
        edge = extract_edge(prof, plan, rake, m=181, theta_range_deg=40.0, k_io=-1)
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
        prof = extract_gap_points(p, n_points=100)[0]
        edge = extract_edge(prof, plan, rake, m=181, theta_range_deg=40.0, k_io=-1)
        assert edge.coverage_report["pass"] is True
        assert edge.coverage_report["coverage_ratio"] == 1.0


def _closest_point_on_triangle(p, a, b, c):
    """点到三角形最近点（Ericson, Real-Time Collision Detection 5.1.5）."""
    ab = b - a
    ac = c - a
    ap = p - a
    d1 = float(ab @ ap)
    d2 = float(ac @ ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a
    bp = p - b
    d3 = float(ab @ bp)
    d4 = float(ac @ bp)
    if d3 >= 0.0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return a + v * ab
    cp = p - c
    d5 = float(ab @ cp)
    d6 = float(ac @ cp)
    if d6 >= 0.0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return a + w * ac
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return b + w * (c - b)
    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    return a + ab * v + ac * w


class TestEdgeOnConjugateSurface:
    def test_edge_lies_on_conjugate_surface(self):
        """刃形点应落在产形面上（几何不变量，≤ 60 μm；旧穿面法偏离 ~0.2mm 会失败）.

        只检查齿面内部刃形点——齿顶/齿根圆弧段刃形点对应产形面已修剪的边界
        （产形面 = 刀具侧刃面，不含齿顶/齿根圆弧）。
        """
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        rake = _rake(plan)
        n_pt = 60
        prof, norms = extract_gap_points(p, n_points=n_pt)
        edge_pts, _roots, _found = compute_discrete_edge(
            prof, plan, rake, m=181, theta_range_deg=40.0, normals=norms
        )

        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=21, m=181, theta_range_deg=40.0, normals=norms
        )
        pos = np.array(surf.mesh_positions, dtype=np.float64).reshape(-1, 3)
        idx = np.array(surf.mesh_indices, dtype=np.int64).reshape(-1, 3)
        tri_a = pos[idx[:, 0]]
        tri_b = pos[idx[:, 1]]
        tri_c = pos[idx[:, 2]]

        # 齿面内部 = 半径在 (r_min+trim, r_max−trim) 内（产形面边界修剪一致）
        r_prof = np.array([math.hypot(x, y) for (x, y) in prof])
        r_lo, r_hi = r_prof.min(), r_prof.max()
        trim = 0.01 * (r_hi - r_lo)

        max_d = 0.0
        checked = 0
        for q, rr in zip(edge_pts, r_prof):
            if not (r_lo + trim < rr < r_hi - trim):
                continue
            checked += 1
            qa = np.array(q, dtype=np.float64)
            best = float("inf")
            for i in range(len(idx)):
                cp = _closest_point_on_triangle(qa, tri_a[i], tri_b[i], tri_c[i])
                best = min(best, float(np.linalg.norm(cp - qa)))
            max_d = max(max_d, best)
        assert checked > 0, "齿面内部刃形点应非空"
        # 网格分片线性近似误差 ~ 单元尺度；刃形点应严格位于表面（< 60 μm）
        assert max_d < 0.06, f"刃形点到产形面最大距离 {max_d:.4f} mm 超容差 0.06"

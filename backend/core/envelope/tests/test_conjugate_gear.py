"""模块②b 等效产形齿轮（K-2.6 阵列 z_t 份 + 补齿顶/齿根回转面）测试 — 纯数学，可入 CI."""

import math

import numpy as np
import pytest

from core.envelope.conjugate import compute_conjugate_surface
from core.envelope.conjugate_gear import _build_cap_face, compute_conjugate_gear
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
    prof = extract_gap_points(p, n_points=30)[0]
    return p, plan, prof


class TestConjugateGear:
    def test_mesh_nonempty_and_normals_aligned(self):
        """产形齿轮三角网非空 + 法向与顶点等长."""
        p, plan, prof = _case()
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, n_z=5, m=61, theta_range_deg=40.0,
        )
        assert len(gear.mesh_positions) > 0
        assert len(gear.mesh_indices) > 0
        assert len(gear.mesh_normals) == len(gear.mesh_positions)

    def test_vertex_count_z_t_multiples_and_caps_added(self):
        """顶点数 = z_t 整数倍，且 > z_t×单齿槽顶点数（齿顶/齿根弧面新增顶点）."""
        p, plan, prof = _case()
        z_t = 41
        single = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=5, m=61, theta_range_deg=40.0,
        )
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=z_t, n_z=5, m=61, theta_range_deg=40.0,
        )
        n_single = len(single.mesh_positions) // 3
        n_gear = len(gear.mesh_positions) // 3
        assert n_gear % z_t == 0
        assert n_gear > z_t * n_single

    def test_rotation_array_correct(self):
        """第 k 份 = 第 0 份绕 z 轴旋转 k·2π/z_t（抽样首 3 顶点）."""
        p, plan, prof = _case()
        z_t = 41
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=z_t, n_z=5, m=61, theta_range_deg=40.0,
        )
        pos = gear.mesh_positions
        n_gear = len(pos) // 3
        n_base = n_gear // z_t
        delta = 2.0 * math.pi / z_t
        k = 1
        c, s = math.cos(delta), math.sin(delta)
        for i in range(3):
            x0, y0, z0 = pos[3 * i], pos[3 * i + 1], pos[3 * i + 2]
            j = k * n_base + i
            xk, yk, zk = pos[3 * j], pos[3 * j + 1], pos[3 * j + 2]
            assert xk == pytest.approx(x0 * c - y0 * s, abs=1e-9)
            assert yk == pytest.approx(x0 * s + y0 * c, abs=1e-9)
            assert zk == pytest.approx(z0, abs=1e-12)

    def test_normals_unit_and_no_degenerate(self):
        """被引用顶点法向模 ≈1（未引用顶点法向为零，无害）."""
        p, plan, prof = _case()
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, n_z=5, m=61, theta_range_deg=40.0,
        )
        nrm = gear.mesh_normals
        n_vert = len(nrm) // 3
        nonzero = 0
        for i in range(0, len(nrm), 3):
            L = math.sqrt(nrm[i] ** 2 + nrm[i + 1] ** 2 + nrm[i + 2] ** 2)
            if L > 0.5:
                nonzero += 1
                assert L == pytest.approx(1.0, abs=1e-6)
        assert nonzero > n_vert // 2

    def test_all_radii_finite(self):
        """所有顶点半径有限（弧面生成无 NaN/离群点）."""
        p, plan, prof = _case()
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, n_z=5, m=61, theta_range_deg=40.0,
        )
        pos = gear.mesh_positions
        rs = [math.hypot(pos[3 * i], pos[3 * i + 1]) for i in range(len(pos) // 3)]
        assert all(math.isfinite(r) for r in rs)
        assert max(rs) > min(rs)  # 非退化（齿顶 > 齿根）

    def test_coverage_matches_single(self):
        """产形齿轮覆盖报告沿用单齿槽（阵列/补面不改覆盖语义）."""
        p, plan, prof = _case()
        single = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=5, m=61, theta_range_deg=40.0,
        )
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, n_z=5, m=61, theta_range_deg=40.0,
        )
        assert gear.coverage == single.coverage

    def test_cap_faces_no_fold(self):
        """齿顶/齿根弧面三角形无退化 + 相邻法向一致（端点顺序稳定，无折叠）."""
        p, plan, _ = _case()
        prof = extract_gap_points(p, n_points=50)[0]
        n_z = 9
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=n_z, m=61, theta_range_deg=40.0,
        )
        n_vert = len(surf.mesh_positions) // 3
        n = n_vert // n_z
        pos = surf.mesh_positions
        for mode in ("top", "root"):
            cap_pos, cap_idx = _build_cap_face(pos, surf.mesh_indices, n, n_z, mode, 9)
            assert len(cap_idx) > 0, f"{mode} 弧面应为非空"
            P = np.array(cap_pos, dtype=np.float64).reshape(-1, 3)
            tris = [cap_idx[i:i + 3] for i in range(0, len(cap_idx), 3)]
            fns = []
            for a, b, c in tris:
                cr = np.cross(P[b] - P[a], P[c] - P[a])
                L = float(np.linalg.norm(cr))
                assert L > 1e-6, f"{mode} 面存在退化三角形（折叠）"
                fns.append(cr / L)
            for i in range(1, len(fns)):
                assert float(np.dot(fns[i - 1], fns[i])) > 0.0, f"{mode} 面第 {i} 个三角形法向翻转（折叠）"

    def test_invalid_inputs(self):
        p, plan, prof = _case()
        with pytest.raises(ValueError):
            compute_conjugate_gear(prof, plan, b_w=p.b_w, k_io=-1, z_t=0)
        with pytest.raises(ValueError):
            compute_conjugate_gear(prof, plan, b_w=p.b_w, k_io=-1, z_t=41, n_arc=2)

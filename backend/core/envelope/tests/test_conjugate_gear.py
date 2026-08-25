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
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        assert len(gear.mesh_positions) > 0
        assert len(gear.mesh_indices) > 0
        assert len(gear.mesh_normals) == len(gear.mesh_positions)

    def test_axial_extent_bounded(self):
        """轴向扩展 2×b_w：T 系 z 范围有界（2026-08-20 校核修正，原 5× 达 ±65mm）."""
        p, plan, prof = _case()
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        pos = gear.mesh_positions
        zs = [pos[3 * i + 2] for i in range(len(pos) // 3)]
        # 2×b_w=40 输入 + Σ 倾斜投影 → |z| < 35（原 5× 扩展时达 65）
        assert max(zs) < 35.0 and min(zs) > -35.0

    def test_vertex_count_z_t_multiples_and_caps_added(self):
        """顶点数 = z_t 整数倍，且 > z_t×单齿槽顶点数（齿顶/齿根弧面新增顶点）."""
        p, plan, prof = _case()
        z_t = 41
        single = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=5, m=61, theta_range_deg=40.0,
        )
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=z_t, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
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
            prof, plan, b_w=p.b_w, k_io=-1, z_t=z_t, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
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
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
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
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        pos = gear.mesh_positions
        rs = [math.hypot(pos[3 * i], pos[3 * i + 1]) for i in range(len(pos) // 3)]
        assert all(math.isfinite(r) for r in rs)
        assert max(rs) > min(rs)  # 非退化（齿顶 > 齿根）

    def test_coverage_matches_single(self):
        """产形齿轮覆盖率（2× z 扩展后应 100% 命中，总点数 2× 单齿槽口径）."""
        p, plan, prof = _case()
        single2 = compute_conjugate_surface(
            prof, plan, b_w=p.b_w * 2, k_io=-1, n_z=10, m=61, theta_range_deg=40.0,
        )
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        # 2× z 扩展：总点数与 2×b_w 单齿槽一致；覆盖率 100%（原 5× 时跌至 0.876）
        assert gear.coverage["total_points"] == single2.coverage["total_points"]
        assert gear.coverage["coverage_ratio"] >= 0.99

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
            cap_pos, cap_idx, cap_phi = _build_cap_face(pos, surf.mesh_indices, n, n_z, mode, 9)
            assert len(cap_idx) > 0, f"{mode} 弧面应为非空"
            assert len(cap_phi) == len(cap_pos) // 3, f"{mode} 接触角与顶点应等长"
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

    def test_mesh_colors_aligned_and_valid(self):
        """干涉顶点色与 positions 等长 + RGB ∈ [0,1] + 多色并存（工程色阶分布）."""
        p, plan, prof = _case()
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        assert len(gear.mesh_colors) == len(gear.mesh_positions)
        for v in gear.mesh_colors:
            assert 0.0 <= v <= 1.0
        rs = {round(gear.mesh_colors[i], 2) for i in range(0, len(gear.mesh_colors), 3)}
        assert len(rs) > 1

    def test_interference_stats_consistent(self):
        """interference_stats 计数完备（单份计数 ×z_t = 总顶点数）+ clamp 透传."""
        p, plan, prof = _case()
        z_t = 41
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=z_t, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        st = gear.interference_stats
        n_vert = len(gear.mesh_positions) // 3
        per_tooth = st["n_interference"] + st["n_contact_band"] + st["n_clearance"] + st["n_reference"]
        assert per_tooth * z_t == n_vert
        assert st["clamp_mm"] == 0.5

    def test_interference_legend(self):
        """legend 图例权威数据：7 采样点单调铺满渐变位 + 刻度含 0 + 参考灰."""
        p, plan, prof = _case()
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        lg = gear.interference_stats["legend"]
        stops = lg["stops"]
        assert len(stops) == 7
        assert [s["t"] for s in stops] == sorted(s["t"] for s in stops)  # 位置升序
        assert stops[0]["t"] == 0.0 and stops[-1]["t"] == 1.0
        # 端点色 = 色阶端点：t=−1 深红 (0.888, 0.174, 0.064)、t=+1 蓝 (0.12, 0.25, 0.75)
        assert stops[0]["color"] == pytest.approx([0.888, 0.174, 0.064], abs=0.01)
        assert stops[-1]["color"] == pytest.approx([0.12, 0.25, 0.75], abs=0.01)
        # 刻度 [mm]：±clamp、±0.2·clamp、0
        assert lg["ticks_mm"][2] == 0.0
        assert lg["ticks_mm"][0] == pytest.approx(-0.5)
        assert lg["ticks_mm"][4] == pytest.approx(0.5)
        assert lg["reference_color"] == [0.62, 0.62, 0.66]

    def test_contact_band_majority(self):
        """正确啮合下绿接触带占主导（共轭面 d≈0，工程色阶 GO 绿）."""
        p, plan, prof = _case()
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        st = gear.interference_stats
        n_judged = st["n_interference"] + st["n_contact_band"] + st["n_clearance"]
        assert st["n_contact_band"] > 0.3 * n_judged  # 侧刃共轭区以贴合为主

    def test_no_white_band_in_colors(self):
        """旧红白蓝色阶的白色接触带已废：顶点色无纯白."""
        p, plan, prof = _case()
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        col = gear.mesh_colors
        for i in range(0, len(col), 3):
            r, g, b = col[i], col[i + 1], col[i + 2]
            assert not (r > 0.9 and g > 0.9 and b > 0.9)

    def test_reference_gray_exists(self):
        """齿宽外参考段存在（2× 轴向扩展的悬伸端）且为中性灰（三通道精确判定）."""
        p, plan, prof = _case()
        z_t = 41
        gear = compute_conjugate_gear(
            prof, plan, b_w=p.b_w, k_io=-1, z_t=z_t, z_w=82, n_z=5, m=61, theta_range_deg=40.0,
        )
        st = gear.interference_stats
        assert st["n_reference"] > 0
        col = np.array(gear.mesh_colors).reshape(-1, 3)
        gray = (
            (np.abs(col[:, 0] - 0.62) < 0.02)
            & (np.abs(col[:, 1] - 0.62) < 0.02)
            & (np.abs(col[:, 2] - 0.66) < 0.02)
        )
        assert int(gray.sum()) == st["n_reference"] * z_t

    def test_interference_stats_respond_to_install(self):
        """干涉着色管线 sanity：各色阶类非空 + stats 响应安装参数变化.

        原断言「中心距 +0.5mm → 干涉点单调增多」在 2026-08-24 根修复（物理
        接触相位取代伪 flare 叶相位）后不再成立——std/off 计数与最深侵入持平在
        噪声级，旧单调性是伪叶着色的伪影。改为：① 红/临界/间隙/参考四类全出现
        （管线非退化）；② 中心距偏移改变统计（着色对 plan 敏感，非死数）。
        """
        from dataclasses import replace

        from core.envelope.conjugate_gear import compute_conjugate_gear as ccg

        p, plan, prof = _case()
        gear_std = ccg(prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0)
        plan_off = replace(plan, a=plan.a + 0.5)
        gear_off = ccg(prof, plan_off, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_z=5, m=61, theta_range_deg=40.0)
        st_std = gear_std.interference_stats
        st_off = gear_off.interference_stats
        for key in ("n_interference", "n_contact_band", "n_clearance", "n_reference"):
            assert st_std[key] > 0, f"{key}=0（色阶类缺失）"
        # 安装参数变化 → 统计变化（n_reference/min_d 至少其一响应）
        assert (
            st_std["n_reference"] != st_off["n_reference"]
            or abs(st_std["min_d_mm"] - st_off["min_d_mm"]) > 1e-6
        )

    def test_invalid_inputs(self):
        p, plan, prof = _case()
        with pytest.raises(ValueError):
            compute_conjugate_gear(prof, plan, b_w=p.b_w, k_io=-1, z_t=0, z_w=82)
        with pytest.raises(ValueError):
            compute_conjugate_gear(prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, n_arc=2)
        with pytest.raises(ValueError):
            compute_conjugate_gear(prof, plan, b_w=p.b_w, k_io=-1, z_t=41, z_w=82, clamp_mm=0.0)

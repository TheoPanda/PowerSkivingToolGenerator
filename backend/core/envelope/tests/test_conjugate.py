"""模块②b 产形面（K-2.6 离散数值啮合）测试 — 纯数学，可入 CI."""

import math

import numpy as np
import pytest

from core.envelope.conjugate import compute_conjugate_surface
from core.envelope.edge import extract_edge
from core.envelope.meshing import helical_tooth_grid
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
        """产形面桶形：中段（z_gear=0）最大半径 > 端部（[12] barrel-shaped）.

        只对入网（被三角网引用）顶点断言——未命中/边界列在 positions 中为占位
        坐标（tt 钳制后为采样起点），不入渲染面。
        """
        p, plan, prof = _internal_case()
        n_z = 9
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=n_z, m=61, theta_range_deg=40.0,
        )
        n = len(prof)
        used = set(surf.mesh_indices)
        # 行主序 index = iz·n + iu；中段行 iz = n_z//2，端部行 iz = 0
        mid = [iz_n for iz_n in range((n_z // 2) * n, (n_z // 2 + 1) * n) if iz_n in used]
        end = [iz_n for iz_n in range(0, n) if iz_n in used]
        mid_rmax = max(math.hypot(surf.mesh_positions[3 * v], surf.mesh_positions[3 * v + 1]) for v in mid)
        end_rmax = max(math.hypot(surf.mesh_positions[3 * v], surf.mesh_positions[3 * v + 1]) for v in end)
        assert mid_rmax > end_rmax

    def test_radius_consistent_with_edge(self):
        """产形面半径范围与刃形自洽（刃形 = 产形面 ∩ 前刀面；只看入网顶点）.

        容差依据：刃形链不修剪边界区（渐开线端点/齿顶/齿根圆弧段的共轭区），
        产形面渲染为防尖角法向污染将其修剪——刃形半径可超出入网范围一个边界区
        余量（15% 齿高 + 0.1mm）。2026-08-24 前旧容差 0.1 靠未命中列未钳制的
        外推位置「碰巧」覆盖（tt 钳制后暴露）。
        """
        p, plan, prof = _internal_case()
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=9, m=61, theta_range_deg=40.0,
        )
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
        edge = extract_edge(prof, plan, rake, m=61, theta_range_deg=40.0, k_io=-1)
        conjugate_rs = [
            math.hypot(surf.mesh_positions[3 * v], surf.mesh_positions[3 * v + 1])
            for v in sorted(set(surf.mesh_indices))
        ]
        r_prof = [math.hypot(q[0], q[1]) for q in prof]
        margin = 0.15 * (max(r_prof) - min(r_prof)) + 0.1
        edge_rs = [math.hypot(q[0], q[1]) for seg in edge.segments for q in seg.pts]
        # 刃形半径范围应落在产形面入网半径范围 ± 边界区余量内
        assert min(conjugate_rs) - margin <= min(edge_rs), \
            f"刃形 min {min(edge_rs):.3f} 低于产形面 {min(conjugate_rs):.3f} − {margin:.3f}"
        assert max(conjugate_rs) + margin >= max(edge_rs), \
            f"刃形 max {max(edge_rs):.3f} 高于产形面 {max(conjugate_rs):.3f} + {margin:.3f}"

    def test_include_tooth_grid_fields(self):
        """include_tooth_grid：W 系网格三字段（长度 3N / 掩码和 == coverage found / 默认空）."""
        p, plan, prof = _internal_case()
        n_z = 9
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=n_z, m=61, theta_range_deg=40.0,
            include_tooth_grid=True,
        )
        n = len(prof)
        assert len(surf.tooth_positions) == 3 * n * n_z
        assert len(surf.tooth_normals) == 3 * n * n_z
        assert len(surf.tooth_participating) == n * n_z
        # 掩码与 coverage 同源（最终 found，含全部修剪）
        assert sum(surf.tooth_participating) == surf.coverage["found"]
        # 默认关闭：三字段为空（零回归）
        surf_off = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=n_z, m=61, theta_range_deg=40.0,
        )
        assert surf_off.tooth_positions == []
        assert surf_off.tooth_normals == []
        assert surf_off.tooth_participating == []

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


class TestHelicalToothGrid:
    """K-0.6 螺旋面网格 + 3D 法矢（meshing.helical_tooth_grid）"""

    def test_spur_degenerate(self):
        """直齿 β_w=0：法矢 NZ=0、廓形沿 z 拉伸（零回归）."""
        pts = [(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)]
        norms = [(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)]  # 单位法矢
        zs = np.linspace(-10.0, 10.0, 5)
        X, Y, Z, NX, NY, NZ = helical_tooth_grid(pts, norms, zs, 1, 0.0, 82.0)
        assert np.allclose(NZ, 0.0)
        # 直齿拉伸：X 每层重复端面廓形
        assert np.allclose(X[:3], [1.0, 0.0, -1.0])
        # 法矢单位化保持
        assert np.allclose(NX * NX + NY * NY + NZ * NZ, 1.0)

    def test_helical_twist_and_nz(self):
        """斜齿 β_w≠0：法矢含 z 分量、单位化、廓形随 z 扭转."""
        pts = [(1.0, 0.0)]
        norms = [(0.0, 1.0)]  # 切矢 (1,0) → 法矢 (0,1)，单位
        zs = np.array([0.0, 10.0])
        beta_w = math.radians(19.0)
        X, Y, Z, NX, NY, NZ = helical_tooth_grid(pts, norms, zs, 1, beta_w, 82.0)
        # z=0 层不扭转
        assert np.allclose([X[0], Y[0]], [1.0, 0.0])
        # 法矢含 z 分量（斜齿螺旋面）
        assert abs(NZ[0]) > 1e-3
        # 单位化
        assert np.allclose(NX * NX + NY * NY + NZ * NZ, 1.0)
        # 廓形随 z 扭转（z=10 层绕 z 转了 θ = z·tanβ_w/r_pw > 0）
        assert abs(Y[1]) > 1e-3


class TestHelicalConjugateSurface:
    """斜齿（β_w≠0）产形面 — 桶形保持 + 覆盖全命中"""

    def _helical_case(self):
        # 文献 Tsai 2023 内斜齿轮：β_w=19°（右旋）、刀具 β_t=2°（左旋）→ Σ=21°
        from core.workpiece.models import GearParams
        plan = compute_process_plan(
            z_w=38, z_t=21, m_n=1.25,
            beta_w_deg=19.0, beta_t_deg=2.0,
            j_w=1, j_t=-1, k_io=-1,
        )
        # 斜齿轮端面齿槽廓形：端面参数 m_t=m_n/cosβ_w、α_t 由 β_w=19° 导出
        p = GearParams(m_n=1.25, z_w=38, b_w=12.0, k_io=-1, beta_w_deg=19.0, j_w=1)
        prof = extract_gap_points(p, n_points=50)[0]
        return p, plan, prof

    def test_helical_mesh_nonempty_and_barrel(self):
        """斜齿产形面：全点命中 + 三角网非空 + 桶形（齿根侧 rmin 中段鼓出）.

        斜齿轮接触位随 Σ 更广（β_w=19°/Σ=21° 需 θ_range≥120°，直齿 ±40° 足够）。
        下限已下沉到 compute_conjugate_surface 内部（斜齿自动抬高到 120°），故此处
        传直齿默认 40° 仍应全点命中——验证「下限」语义。桶形体现在齿根侧（rmin 中段
        > 两端，凸齿根部中段鼓出）；齿顶侧 rmax 受齿根圆弧段接触位双根影响，不作桶形
        判据（[12] 桶形 = 中段最粗的「腰部」，齿根侧 rmin 为稳定指标）。
        """
        p, plan, prof = self._helical_case()
        n_z = 9
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=n_z, m=181, theta_range_deg=40.0,
        )
        assert surf.coverage["pass"] is True
        assert len(surf.mesh_positions) > 0
        assert len(surf.mesh_indices) > 0
        assert len(surf.mesh_normals) == len(surf.mesh_positions)
        n = len(prof)
        pts = [surf.mesh_positions[i:i + 3] for i in range(0, len(surf.mesh_positions), 3)]
        mid = pts[(n_z // 2) * n: (n_z // 2 + 1) * n]
        end = pts[0:n]
        mid_rmin = min(math.hypot(q[0], q[1]) for q in mid)
        end_rmin = min(math.hypot(q[0], q[1]) for q in end)
        assert mid_rmin > end_rmin

    def test_helical_include_tooth_grid_fields(self):
        """斜齿 include_tooth_grid：法矢含 z 分量（螺旋面）+ 掩码和 == coverage found."""
        p, plan, prof = self._helical_case()
        n_z = 9
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=n_z, m=181, theta_range_deg=40.0,
            include_tooth_grid=True,
        )
        n = len(prof)
        assert len(surf.tooth_positions) == 3 * n * n_z
        assert len(surf.tooth_normals) == 3 * n * n_z
        assert sum(surf.tooth_participating) == surf.coverage["found"]
        # 斜齿螺旋面：法矢整体应存在非零 z 分量（齿面网格层间扭转所致）
        nzs = surf.tooth_normals[2::3]
        assert max(abs(v) for v in nzs) > 1e-3

    def test_helical_5deg_physical_sheet_selected(self):
        """斜齿 5° 啮合方程双根须选物理叶：产形面点全部落在产形齿径向带（r_pt±齿高+1mm）.

        用户 2026-08-24 目检报告：右产形面偏离齿面、左右两产形面距离过远无法构成
        有效刀具齿廓。根因：g=v·n 每点有两个变号根（物理接触根 + 伪 flare 叶根，
        r_T≈r_pt+12~21mm），盲取首个变号根在一侧齿面选中伪叶。物理根恒为 g 由正
        变负的下降穿越（β_w=0/5/19 全用例标定）。半径带断言 = 法矢朝向翻转的护栏。
        """
        from core.workpiece.models import GearParams
        plan = compute_process_plan(
            z_w=82, z_t=41, m_n=2.0, beta_w_deg=5.0, beta_t_deg=15.0,
            j_w=1, j_t=-1, k_io=-1,
        )
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, beta_w_deg=5.0, j_w=1)
        prof, norms = extract_gap_points(p, n_points=50)
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=9, m=181, theta_range_deg=40.0,
            normals=norms,
        )
        assert surf.coverage["pass"] is True
        # 只断言入网（被三角网引用）顶点：未命中/边界列的位置不入渲染面、可为占位
        used = sorted(set(surf.mesh_indices))
        rs = [
            math.hypot(surf.mesh_positions[3 * v], surf.mesh_positions[3 * v + 1])
            for v in used
        ]
        h = max(math.hypot(q[0], q[1]) for q in prof) - min(math.hypot(q[0], q[1]) for q in prof)
        band = h + 1.0
        offenders = [r for r in rs if abs(r - plan.r_pt) > band]
        assert not offenders, (
            f"{len(offenders)} 个产形面点越出产形齿径向带 r_pt±{band:.2f}"
            f"（min={min(rs):.2f}, max={max(rs):.2f}, r_pt={plan.r_pt:.2f}）——伪叶被选中"
        )

    def test_helical_edge_now_supported(self):
        """斜齿刃形已走数值求交（K-2.8b，2026-08-24）：不再 raise，覆盖全命中.

        原「消元法对螺旋面非仿射失效」的限制由 edge.compute_helical_edge 取代
        （产形面网格逐列解 F=0 + 局部细化）；详细验收在 test_edge.TestHelicalEdge。
        """
        from core.envelope.rake import build_plane_rake
        p, plan, prof = self._helical_case()
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=2.0, r_pt=plan.r_pt)
        res = extract_edge(prof, plan, rake, m=181, theta_range_deg=90.0, k_io=-1, b_w=p.b_w)
        assert res.coverage_report["pass"] is True
        assert res.ffa_um is None


class TestAnimFrames:
    """运动仿真动画帧提取测试."""

    def test_anim_frames_structure(self):
        """include_anim=True 返回正确结构的动画帧数据."""
        p, plan, prof = _internal_case()
        m_anim = 12
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=9, m=61,
            theta_range_deg=40.0, include_anim=True, m_anim=m_anim,
        )
        # 帧数正确
        assert len(surf.anim_frames) == m_anim
        # 每帧有 phi_t_deg 和 positions
        for frame in surf.anim_frames:
            assert isinstance(frame.phi_t_deg, float)
            assert len(frame.positions) > 0
            assert len(frame.positions) % 3 == 0
        # indices 非空（mesh 使用的顶点在原始 N 点中的索引）
        assert len(surf.anim_indices) > 0
        # mesh_indices 非空（重映射后的三角网索引）
        assert len(surf.anim_mesh_indices) > 0
        assert len(surf.anim_mesh_indices) % 3 == 0  # 每三角形 3 个索引

    def test_anim_frames_positions_consistent(self):
        """每帧 positions 长度一致（= n_mesh_verts * 3）."""
        p, plan, prof = _internal_case()
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=9, m=61,
            theta_range_deg=40.0, include_anim=True, m_anim=8,
        )
        lengths = {len(f.positions) for f in surf.anim_frames}
        assert len(lengths) == 1  # 所有帧 positions 长度相同
        n_verts = len(surf.anim_indices)
        assert lengths.pop() == n_verts * 3

    def test_anim_mesh_indices_valid(self):
        """重映射后的 mesh_indices 所有值在 [0, n_verts) 范围内."""
        p, plan, prof = _internal_case()
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=9, m=61,
            theta_range_deg=40.0, include_anim=True, m_anim=4,
        )
        n_verts = len(surf.anim_indices)
        assert all(0 <= idx < n_verts for idx in surf.anim_mesh_indices)

    def test_anim_frames_angle_range(self):
        """首末帧 phi_t_deg 覆盖 ±anim_theta_range_deg（默认 ±360°）."""
        p, plan, prof = _internal_case()
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=9, m=61,
            theta_range_deg=40.0, include_anim=True, m_anim=20,
        )
        first = surf.anim_frames[0].phi_t_deg
        last = surf.anim_frames[-1].phi_t_deg
        assert abs(first - (-360.0)) < 1.0  # 首帧 ≈ -360°
        assert abs(last - 360.0) < 1.0      # 末帧 ≈ +360°

    def test_anim_false_by_default(self):
        """include_anim=False（默认）不返回动画帧."""
        p, plan, prof = _internal_case()
        surf = compute_conjugate_surface(
            prof, plan, b_w=p.b_w, k_io=-1, n_z=9, m=61, theta_range_deg=40.0,
        )
        assert len(surf.anim_frames) == 0
        assert len(surf.anim_indices) == 0
        assert len(surf.anim_mesh_indices) == 0

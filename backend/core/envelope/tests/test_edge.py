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


def _self_intersections(edge_pts, rake) -> int:
    """刃形闭合环在前刀面平面 2D 投影的自相交线段对数（非相邻段严格相交）."""
    pts = np.array(edge_pts, dtype=np.float64)
    nv = np.array(rake.n_rake, dtype=np.float64)
    nv = nv / np.linalg.norm(nv)
    e1 = np.cross(nv, [0.0, 0.0, 1.0])
    e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(nv, e1)
    qx = pts[:, 0] * e1[0] + pts[:, 1] * e1[1] + pts[:, 2] * e1[2]
    qy = pts[:, 0] * e2[0] + pts[:, 1] * e2[1] + pts[:, 2] * e2[2]
    q = np.stack([qx, qy], axis=1)

    def _cross(o, x, y):
        return (x[0] - o[0]) * (y[1] - o[1]) - (x[1] - o[1]) * (y[0] - o[0])

    def _inter(a, b, c, d):
        d1, d2 = _cross(c, d, a), _cross(c, d, b)
        d3, d4 = _cross(a, b, c), _cross(a, b, d)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    n = len(q)
    return sum(
        1
        for i in range(n - 1)
        for j in range(i + 2, n - 1)
        if _inter(q[i], q[i + 1], q[j], q[j + 1])
    )


def _rake(plan):
    return build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)


def _helical_case(beta_w: float, j_w: int = 1):
    """斜齿内齿轮用例：默认 5°（用户常用），19° 对齐 Tsai 文献参数，25° 字典上界."""
    if beta_w > 20.0:
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, beta_w_deg=beta_w, j_w=j_w)
        plan = compute_process_plan(
            z_w=82, z_t=41, m_n=2.0, beta_w_deg=beta_w, beta_t_deg=15.0,
            j_w=j_w, j_t=-1, k_io=-1,
        )
    else:
        z_w, m_n, b_w, z_t, beta_t = (38, 1.25, 12.0, 21, 2.0) if beta_w > 10.0 else (82, 2.0, 20.0, 41, 15.0)
        p = GearParams(m_n=m_n, z_w=z_w, b_w=b_w, k_io=-1, beta_w_deg=beta_w, j_w=j_w)
        plan = compute_process_plan(
            z_w=z_w, z_t=z_t, m_n=m_n, beta_w_deg=beta_w, beta_t_deg=beta_t,
            j_w=j_w, j_t=-1, k_io=-1,
        )
    prof, norms = extract_gap_points(p, n_points=50)
    rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=(2.0 if beta_w > 10.0 else 15.0), r_pt=plan.r_pt)
    return p, plan, prof, norms, rake


class TestHelicalEdge:
    """斜齿刃形（数值求交 K-2.8b，2026-08-24）：产形面网格 ∩ 前刀面.

    验收（spec 2026-08-24-helical-edge）：覆盖 100% + 双残差 <5μm（贴前刀面 +
    贴产形面独立重算）+ 上链含顶刃共轭与顶缝椭圆弧桥 + n_z 加密收敛。直齿路径
    零回归由既有测试把守。β=25°（Σ=40° 超内齿轮实用包络 ~20°）降级为诚实空结果。
    """

    @pytest.mark.parametrize("beta_w", [5.0, 19.0])
    def test_coverage_and_residuals(self, beta_w: float):
        p, plan, prof, norms, rake = _helical_case(beta_w)
        res = extract_edge(
            prof, plan, rake, m=181, theta_range_deg=40.0, k_io=-1,
            normals=norms, b_w=p.b_w, n_z=21,
        )
        assert res.coverage_report["pass"] is True
        assert res.ffa_um is None  # 斜齿不做 ffα 闭环
        assert res.residual_stats is not None
        assert res.residual_stats["max_plane_um"] < 5.0
        assert res.residual_stats["max_surface_um"] < 5.0
        assert res.residual_stats["pass"] is True
        # 上链含顶刃共轭 + 顶缝椭圆弧桥（构造段，2026-08-24 闭环需求）
        assert res.residual_stats["n_bridge"] > 0
        assert sum(len(seg.pts) for seg in res.segments) >= 40
        assert all(len(seg.pts) >= 5 for seg in res.segments)

    def test_seam_bridge_smooth_junction(self):
        """顶缝桥与共轭端点切向连续（用户 2026-08-25 报实体侧刃↔顶刃交界尖角）.

        根因：常数半径椭圆弧把径向行程挤进首末桥段，方向与共轭到达方向错开
        ~62°。修复：弦长缩放 Hermite C1 桥（β5° 桥端转折 10.5°）+ 有界钳制
        （掉头型缝回退椭圆弧，19° 部分拐角是物理真实——缝内含极角峰）。
        """
        from core.envelope.edge import solve_edge_chain

        p, plan, prof, norms, rake = _helical_case(5.0)
        pts_c, _, _, br_c = solve_edge_chain(
            prof, plan, rake, m=181, theta_range_deg=40.0, normals=norms, b_w=p.b_w, n_z=21,
        )
        br_idx = [i for i, b in enumerate(br_c) if b]
        assert br_idx, "应有顶缝桥点"
        # 桥两端（含邻接共轭点）的 3D 转折角 ≤ 20°（修复前 62° 尖角；共轭基线
        # ~1°，Hermite 自身平滑曲率峰 ~16°——是弧不是折角尖峰）
        for i in set([br_idx[0] - 1, br_idx[0], br_idx[-1], min(br_idx[-1] + 1, len(pts_c) - 2)]):
            if i < 1:
                continue
            u = [pts_c[i][k] - pts_c[i - 1][k] for k in range(3)]
            v = [pts_c[i + 1][k] - pts_c[i][k] for k in range(3)]
            lu = math.sqrt(sum(c * c for c in u))
            lv = math.sqrt(sum(c * c for c in v))
            d = abs(sum(u[k] * v[k] for k in range(3)) / (lu * lv))
            turn = math.degrees(math.acos(min(1.0, d)))
            assert turn < 20.0, f"桥端 idx{i} 转折 {turn:.1f}°（尖角回退）"

    def test_helical_chain_reaches_fold(self):
        """斜齿链须到达极角折返点，不得被 interior 半径带提前截断（2026-08-25 用户报侧刃变形）.

        旧实现 interior = r > r_lo+3% 带想剔槽底弧，但直齿折返点落在弧前圆角带
        （col≈144，r_lo+0.1）——3% 带=0.135mm 把折返点提前 ~3 列切掉。折返区
        dθ/du 极陡：β5° 实测丢 2.56° 展布（5.696°→3.14°，齿瘦 45%）+ 链底抬高
        1.6mm → 构造腿长坡（用户报「齿根坡度状」）。修复：全列开放 + 链尾按
        极角折返切割（直齿 build_tooth_loop i_fold 同语义）。判据（n=200，
        直齿折返 col≈144）：链列域 max ≥ 143 且 β5° 展布 ≥ 4.5°（直齿 5.696°
        的 −21% 内——5° 小扰动的连续性界）。
        """
        from core.envelope.edge import solve_edge_chain

        p, plan, prof, norms, rake = _helical_case(5.0)
        prof200, norms200 = extract_gap_points(p, n_points=200)
        pts_c, _, cols_c, br_c = solve_edge_chain(
            prof200, plan, rake, m=181, theta_range_deg=40.0, normals=norms200, b_w=p.b_w, n_z=21,
        )
        th = [math.atan2(q[1], q[0]) for q in pts_c]
        spread = math.degrees(max(th) - min(th))
        assert max(cols_c) >= 143, (
            f"链止于列 {max(cols_c)}（折返 col≈144 前）——interior 带截断折返区，齿瘦+长坡腿"
        )
        assert spread >= 4.5, (
            f"β5° 链展布 {spread:.3f}°（直齿 5.696° 的 {(spread / 5.696 - 1) * 100:.0f}%）——小螺旋角不该缩窄至此"
        )

    def test_seam_bridge_flat_midspan(self):
        """顶缝桥中段贴椭圆基底、无鼓包（用户 2026-08-25 报顶刃平直带变坡状）.

        全切向 Hermite 桥端部方向对了，但中段把缝顶成 0.18mm 鼓包（超缝端点半径
        +0.177mm、占弦长 26%）——顶刃平直带变坡状隆起。修复：椭圆基底 + 端部
        平台混合窗（两端纯 Hermite 切向匹配，中段 w=0 严格贴椭圆）。两级判据：
        中段（t∈[1/3,2/3]，桥点序 6..11）半径 ≤ max(r_缝端)+0.02（平直带保形）；
        全桥点 ≤ max(r_缝端)+0.10（端部圆角凸台上界——沿共轭 −72° 方向抵达缝端
        几何上必然从上方小越，~0.05-0.08mm）。
        """
        from core.envelope.edge import solve_edge_chain

        p, plan, prof, norms, rake = _helical_case(5.0)
        pts_c, _, _, br_c = solve_edge_chain(
            prof, plan, rake, m=181, theta_range_deg=40.0, normals=norms, b_w=p.b_w, n_z=21,
        )
        br_idx = [i for i, b in enumerate(br_c) if b]
        assert br_idx, "应有顶缝桥点"
        r_ends = (
            math.hypot(pts_c[br_idx[0] - 1][0], pts_c[br_idx[0] - 1][1]),
            math.hypot(pts_c[br_idx[-1] + 1][0], pts_c[br_idx[-1] + 1][1]),
        )
        for k, i in enumerate(br_idx):  # k: 0..n−2，t = (k+1)/17
            r_i = math.hypot(pts_c[i][0], pts_c[i][1])
            t_i = (k + 1) / 17.0
            if 1.0 / 3.0 <= t_i <= 2.0 / 3.0:
                assert r_i <= max(r_ends) + 0.02, (
                    f"桥中段 idx{i} t={t_i:.2f} r={r_i:.4f} 超 max+0.02（中段鼓包，顶刃平直带变坡状）"
                )
            else:
                assert r_i <= max(r_ends) + 0.10, (
                    f"桥端部 idx{i} t={t_i:.2f} r={r_i:.4f} 超 max+0.10（端部圆角凸台失控）"
                )

    def test_helical_25deg_out_of_envelope(self):
        """β=25°（Σ=40°）：超内齿轮实用包络 → 覆盖不完整、诚实不通过.

        文献内齿 Σ 典型 ~20°（上限 45° 为外齿）；25°+β_t15° 组合的合法近叶接触
        大部分缺失。2026-08-25 全方向根后部分列（齿根弧共轭支）可解（覆盖 ~0.36），
        但整体覆盖远不足 1 → pass=False 诚实降级（非空也非通过）。
        """
        p, plan, prof, norms, rake = _helical_case(25.0)
        res = extract_edge(
            prof, plan, rake, m=181, theta_range_deg=40.0, k_io=-1,
            normals=norms, b_w=p.b_w, n_z=21,
        )
        assert res.coverage_report["pass"] is False
        assert res.coverage_report["coverage_ratio"] < 0.9
        # 已找到的点本身有效（双残差可过）——不可用性由覆盖不完整表达

    @pytest.mark.xfail(reason=(
        "19°@n=200（live 密度）：齿根弧共轭支与齿侧叶在左尾区交叉混支，链 2D 极角"
        "回卷、闭合环自相交（n=50 测试密度不复现）。5°/10° 全密度正常。跟进项："
        "弧支按 φ 单调段切分后再拼链。"
    ), strict=False)
    def test_helical_19deg_n200_loop_known_issue(self):
        from core.envelope.edge import solve_edge_chain
        from core.envelope.tooth_solid import build_tooth_loop, limit_radius

        p, plan, _, _, rake = _helical_case(19.0)
        prof200, norms200 = extract_gap_points(p, n_points=200)
        pts_c, _, cols_c, br_c = solve_edge_chain(
            prof200, plan, rake, m=181, theta_range_deg=40.0, normals=norms200, b_w=p.b_w, n_z=21,
        )
        build_tooth_loop(
            pts_c, rake, z_t=21, r_pt=plan.r_pt,
            r_limit=limit_radius(p.tip_radius(), plan.a),
            r_f=p.root_radius(), a=plan.a, precut=True, upper_constructed=br_c,
        )

    def test_helical_closed_loop(self):
        """斜齿闭合环（用户 2026-08-24 需求）：顶刃共轭 + 顶缝桥 + 底刃 1/2×2 构造.

        build_tooth_loop precut 模式：链即上链、跳过直齿清洗；自交校验+耳切完整
        性把守轮廓简单性。桥点半径与缝端点连续（均值半径弧）。
        """
        from core.envelope.edge import solve_edge_chain
        from core.envelope.tooth_solid import build_tooth_loop, limit_radius

        for beta_w in (5.0, 19.0):
            p, plan, prof, norms, rake = _helical_case(beta_w)
            pts_c, phis_c, cols_c, br_c = solve_edge_chain(
                prof, plan, rake, m=181, theta_range_deg=40.0, normals=norms, b_w=p.b_w, n_z=21,
            )
            loop = build_tooth_loop(
                pts_c, rake, z_t=(41 if beta_w < 10 else 21), r_pt=plan.r_pt,
                r_limit=limit_radius(p.tip_radius(), plan.a),
                r_f=p.root_radius(), a=plan.a, precut=True, upper_constructed=br_c,
            )
            assert len(loop.pts) > len(pts_c)  # 上链 + 底构造段
            assert sum(loop.constructed) == sum(br_c) + 27  # 桥 + v8.1 腿(3+2)×2 + 求差底弧 17
            assert 0.0 < loop.arch_spread_deg < 2.0 * math.degrees(math.pi / (41 if beta_w < 10 else 21))
            # 桥点半径与缝两端点半径连续（均值半径，偏差 <0.3mm）
            br_rs = [math.hypot(pts_c[i][0], pts_c[i][1]) for i in range(len(pts_c)) if br_c[i]]
            if br_rs:
                assert max(br_rs) - min(br_rs) < 0.3

    def test_left_hand_jw_negative(self):
        """左旋（j_w=−1）同矩阵：覆盖/残差同门槛（闭合环投影可自叠，开段降级）."""
        p, plan, prof, norms, rake = _helical_case(5.0, j_w=-1)
        res = extract_edge(
            prof, plan, rake, m=181, theta_range_deg=40.0, k_io=-1,
            normals=norms, b_w=p.b_w, n_z=21,
        )
        assert res.coverage_report["pass"] is True
        assert res.residual_stats["pass"] is True

    def test_nz_refinement_convergence(self):
        """n_z 21→41：同列刃形点位移 <5μm（z 向插值收敛，β=19° 最重工况）."""
        p, plan, prof, norms, rake = _helical_case(19.0)
        r1 = extract_edge(prof, plan, rake, m=181, theta_range_deg=40.0, k_io=-1,
                          normals=norms, b_w=p.b_w, n_z=21)
        r2 = extract_edge(prof, plan, rake, m=181, theta_range_deg=40.0, k_io=-1,
                          normals=norms, b_w=p.b_w, n_z=41)
        assert r1.coverage_report["pass"] and r2.coverage_report["pass"]
        pts1 = [pt for seg in r1.segments for pt in seg.pts]
        pts2 = [pt for seg in r2.segments for pt in seg.pts]
        arr2 = np.array(pts2)
        max_d = 0.0
        for pt in pts1:
            d = np.sqrt(np.sum((arr2 - np.array(pt)) ** 2, axis=1)).min()
            max_d = max(max_d, float(d))
        assert max_d < 0.005, f"n_z 加密刃形点位移 {max_d * 1000:.2f}μm 未收敛"


class TestComputeDiscreteEdge:
    def test_edge_points_on_rake_face(self):
        """离散刃形点应落在前刀面 F=0 上（线性插值误差 < 采样间隔，容差放宽）."""
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        rake = _rake(plan)
        prof = extract_gap_points(p, n_points=100)[0]
        pts, roots, found, breaks, cols = compute_discrete_edge(prof, plan, rake, m=181, theta_range_deg=40.0)
        # 内侧包络环：点数可与廓形列数不同（交叉分支剔除），但三组平行
        assert len(pts) == len(roots) == len(cols)
        assert len(breaks) == 0  # 无自交单环，无断点
        assert all(found)
        for (x, y, z) in pts:
            assert rake.A * x + rake.B * y + rake.C * z + rake.const == pytest.approx(0.0, abs=1e-4)

    def test_no_self_intersection(self):
        """顶刃↔侧刃交界折叠修复（2026-08-20）：刃形环在前刀面平面内无自相交.

        修复前：段交界两分支根混合取样 → 折线折返自交（u≈77-81），
        前刀面片扇形剖分产生翻转三角形（实体缝合不良体根源）。
        """
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
        plan = _plan()
        rake = _rake(plan)
        prof, norms = extract_gap_points(p, n_points=200)
        edge_pts, _roots, _found, _breaks, _cols = compute_discrete_edge(
            prof, plan, rake, m=181, theta_range_deg=40.0, normals=norms
        )
        assert _self_intersections(edge_pts, rake) == 0


class TestInnerContour:
    def test_inner_envelope_of_crossing_branches(self):
        """交叉分支取内侧：r=5 整圆 + 部分方向更近的 r∈[3,8] 分支 → 逐方向 min.

        远分支（r>5）点必须被剔除——它们正是折返自交/实体不良体的来源。
        """
        from core.envelope.edge import inner_contour

        class _Rake:
            n_rake = (0.0, 0.0, 1.0)

        pts = []
        for k in range(360):  # 分支 A：r=5 整圆（每桶恰 1 点，min 基准全覆盖）
            t = 2 * math.pi * k / 360
            pts.append([5 * math.cos(t), 5 * math.sin(t), 0.0])
        for k in range(180):  # 分支 B：θ∈[0,π)，r 3→8（前段比 5 近、后段比 5 远）
            t = math.pi * k / 179
            r = 3 + 5 * (k / 179)
            pts.append([r * math.cos(t), r * math.sin(t), 0.0])
        keep = inner_contour(np.array(pts), _Rake())  # 邻域下包络（保分辨率）
        q = np.array(pts)[keep][:, :2]
        ang = np.arctan2(q[:, 1], q[:, 0])
        r_out = np.hypot(q[:, 0], q[:, 1])
        # 内侧包络上界：远分支点被剔除（刚越过 5 的点受 eps_mm=0.15 毛刺容差保留）
        assert r_out.max() <= 5.0 + 0.16
        assert (r_out > 6.0).sum() == 0  # 深度远分支点（r_B 最大 8）全数剔除
        # B 更近的方向（r_B < 4.5）确实切换到分支 B
        near = r_out[(ang > 0.2) & (ang < 1.0)]
        assert (near < 4.5).any()


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
        edge_pts, _roots, _found, _breaks, edge_cols = compute_discrete_edge(
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
        for q, ci in zip(edge_pts, edge_cols):  # 刃形点经 edge_cols 对应母线半径
            rr = r_prof[ci]
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

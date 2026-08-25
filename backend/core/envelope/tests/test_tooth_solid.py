"""模块③ B 方案 v2 单齿闭合实体（K-3.1 预览级）测试 — 纯数学，可入 CI.

B 方案 v2（2026-08-21 用户方案）：开放轮廓 = 上链（1/2齿根-齿侧-齿顶-齿侧-1/2齿根，
按廓形列序的共轭链，折返处切分）+ 沿理论极限圆 r_limit = r_a − a 的齿根延伸到齿距线
±π/z_t + 径向偏置 1/20 分度圆直径 + 谷底圆弧闭合；后刀面与单齿实体同轮廓。
断言：r_limit 公式、链共面/列序/折返切分、延伸贴极限圆、偏置量与方向、圆弧过两端点、
轮廓简单星形、实体水密 + 体积 > 0、整环齿距线角/径重合。
"""

import math

import numpy as np
import pytest

from core.envelope.edge import solve_edge_chain
from core.envelope.process_plan import compute_process_plan
from core.envelope.rake import RakeSurface, build_plane_rake
from core.envelope.swept_cloud import extract_gap_points
from core.envelope.tooth_solid import (
    ROOT_OFFSET_RATIO_DEFAULT,
    build_tooth_loop,
    build_tooth_solid,
    build_tool_ring,
    limit_radius,
)
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


def _chain(plan, rake, n_points=100):
    p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
    prof, norms = extract_gap_points(p, n_points=n_points)
    return solve_edge_chain(prof, plan, rake, m=181, theta_range_deg=40.0, normals=norms)[0]


def _loop(plan, rake, chain, **kw):
    """便捷封装：limit_radius + build_tooth_loop（默认偏置比 1/20 + 齿顶伪点判据）."""
    return build_tooth_loop(
        chain, rake, z_t=41, r_pt=plan.r_pt,
        r_limit=limit_radius(80.0, plan.a), r_f=84.5, a=plan.a, **kw
    )


def _signed_volume(positions: list[float], indices: list[int]) -> float:
    """闭合三角网有向体积（散度定理，与实现互检）."""
    P = np.array(positions, dtype=np.float64).reshape(-1, 3)
    T = np.array(indices, dtype=np.int64).reshape(-1, 3)
    v0, v1, v2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    cx = (v1[:, 1] * v2[:, 2] - v1[:, 2] * v2[:, 1])
    cy = (v1[:, 2] * v2[:, 0] - v1[:, 0] * v2[:, 2])
    cz = (v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0])
    vol = (v0[:, 0] * cx + v0[:, 1] * cy + v0[:, 2] * cz).sum() / 6.0
    return float(vol)


def _edge_use(indices: list[int]) -> dict[frozenset[int], list[tuple[int, int]]]:
    """无向边 → 有向使用列表（水密 + 一致定向判据：每边恰 2 次且方向相反）."""
    use: dict[frozenset[int], list[tuple[int, int]]] = {}
    T = np.array(indices, dtype=np.int64).reshape(-1, 3)
    for a, b, c in T:
        for u, v in ((a, b), (b, c), (c, a)):
            use.setdefault(frozenset((int(u), int(v))), []).append((int(u), int(v)))
    return use


class TestLimitRadius:
    def test_formula(self):
        """理论极限最小刀具半径 = r_a − a（工件齿顶圆 − 中心距，精确式）."""
        assert limit_radius(80.0, 39.5537) == pytest.approx(40.4463, abs=1e-9)

    def test_nonpositive_raises(self):
        with pytest.raises(ValueError, match="必须"):
            limit_radius(30.0, 39.5537)


class TestSolveEdgeChain:
    def test_chain_coplanar_and_ordered(self):
        """列序链：全部点共面 F=0，且刀具极角先增后减（含折返）."""
        plan = _plan()
        rake = _rake(plan)
        chain = _chain(plan, rake)
        assert len(chain) > 50
        for (x, y, z) in chain:
            assert rake.A * x + rake.B * y + rake.C * z + rake.const == pytest.approx(0.0, abs=1e-4)
        th = [math.atan2(p[1], p[0]) for p in chain]
        rel = [((t - th[0] + math.pi) % (2 * math.pi)) - math.pi for t in th]
        assert max(rel) > math.radians(4.0)  # 上链展布 > 4°（算例1 ≈5.5°）
        assert rel[-1] < max(rel) - math.radians(0.5)  # 末端已折返回落


class TestBuildToothLoop:
    def test_all_points_on_rake_face(self):
        """闭合轮廓全部点共面于前刀面."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        for (x, y, z) in loop.pts:
            assert rake.A * x + rake.B * y + rake.C * z + rake.const == pytest.approx(0.0, abs=1e-4)

    def test_legs_straight_lines(self):
        """v7 齿根腿全直线：偏置段同极角（严格径向直线，P 在极限圆/Q 在谷底半径）
        + 延伸段共线（弦直线，折返点 → 齿距线极限圆点）."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        hi, lo = loop.arc_end_idx
        # n_ext=n_off=4 布局：... fold, e1, e2, P, o1, o2, Q_R(hi), arc, Q_L(lo), o1, o2, P, e1, e2
        radR = loop.pts[hi - 3: hi + 1]      # P_R + 偏置内部 + Q_R
        radL = loop.pts[lo: lo + 4]          # Q_L + 偏置内部 + P_L
        for seg in (radR, radL):
            ths = [math.atan2(q[1], q[0]) for q in seg]
            assert max(ths) - min(ths) < 1e-9, "偏置段同极角 = 严格径向直线"
            rr = [math.hypot(q[0], q[1]) for q in seg]
            assert min(rr) == pytest.approx(loop.root_radius, abs=1e-9)
            assert max(rr) == pytest.approx(loop.r_limit, abs=1e-9)

        def dir_ang(q0, q1):
            return math.atan2(q1[1] - q0[1], q1[0] - q0[0])

        extR = loop.pts[hi - 6: hi - 2]      # fold + e1 + e2 + P_R
        a0 = dir_ang(extR[0], extR[1])
        for j in range(1, len(extR) - 1):  # 共线：弦直线
            assert dir_ang(extR[j], extR[j + 1]) == pytest.approx(a0, abs=1e-9)
        assert math.hypot(*extR[-1][:2]) == pytest.approx(loop.r_limit, abs=1e-9)

    def test_offset_and_root_radius(self):
        """偏置量 = ratio × 分度圆直径（默认 1/20），谷底半径 = r_limit − 偏置量（精确）."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        d = ROOT_OFFSET_RATIO_DEFAULT * 2.0 * plan.r_pt
        assert loop.offset_mm == pytest.approx(d, abs=1e-9)
        assert loop.root_radius == pytest.approx(loop.r_limit - d, abs=1e-9)
        # 轮廓最小半径 = 谷底（低于极限圆，深谷）
        r_min = min(math.hypot(p[0], p[1]) for p in loop.pts)
        assert r_min < loop.r_limit - d + 1e-3

    def test_valley_arc_endpoints(self):
        """谷底圆弧两端点 = 直腿内端（arc_end_idx 处圆柱半径精确 = root_radius）."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        for idx in loop.arc_end_idx:
            p = loop.pts[idx]
            assert math.hypot(p[0], p[1]) == pytest.approx(loop.root_radius, abs=1e-9)

    def test_valley_arc_direction(self):
        """v6 弧向：凸侧背离轴（弧在弦外靠材料侧，模仿轴心齿底圆）."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        hi, lo = loop.arc_end_idx
        r_mid = math.hypot(*loop.pts[(hi + lo) // 2][:2])
        assert r_mid > loop.root_radius + 0.1

    def test_simple_polygon_and_cap_complete(self):
        """闭环为简单多边形（v3：不要求星形——深谷轮廓对形心非星形）+ 耳切完整."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        P = np.array(loop.pts, dtype=np.float64)
        nv = np.array(rake.n_rake, dtype=np.float64)
        nv = nv / np.linalg.norm(nv)
        e1 = np.cross(nv, [0.0, 0.0, 1.0])
        e1 = e1 / np.linalg.norm(e1)
        e2 = np.cross(nv, e1)
        qx = P[:, 0] * e1[0] + P[:, 1] * e1[1] + P[:, 2] * e1[2]
        qy = P[:, 0] * e2[0] + P[:, 1] * e2[1] + P[:, 2] * e2[2]
        q = list(zip(qx.tolist(), qy.tolist()))
        n = len(q)

        def _cross(o, x, y):
            return (x[0] - o[0]) * (y[1] - o[1]) - (x[1] - o[1]) * (y[0] - o[0])

        def _inter(a, b, cc, d2):
            d1v, d2v = _cross(cc, d2, a), _cross(cc, d2, b)
            d3v, d4v = _cross(a, b, cc), _cross(a, b, d2)
            return ((d1v > 0) != (d2v > 0)) and ((d3v > 0) != (d4v > 0))

        si = sum(
            1
            for i in range(n)
            for j in range(i + 2, n)
            if _inter(q[i], q[(i + 1) % n], q[j], q[(j + 1) % n])
            and not (i == 0 and j == n - 1)
        )
        assert si == 0
        # 耳切剖分完整（n−2 三角）且绕向统一 CCW（相对 2D 基，法向 +n̂）
        assert len(loop.cap_indices) == 3 * (n - 2)
        area2 = sum(q[i][0] * q[(i + 1) % n][1] - q[(i + 1) % n][0] * q[i][1] for i in range(n))
        cap_area2 = 0.0
        for t in range(0, len(loop.cap_indices), 3):
            a, b, c = q[loop.cap_indices[t]], q[loop.cap_indices[t + 1]], q[loop.cap_indices[t + 2]]
            cap_area2 += (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        assert cap_area2 == pytest.approx(area2, abs=1e-9)

    def test_arch_spread_within_pitch(self):
        """上链展布 ≈ 5.7°（算例1 锚点，n_points=100 列序链）且严格小于齿距 8.78°."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        assert loop.arch_spread_deg == pytest.approx(5.7, abs=0.3)
        assert loop.arch_spread_deg < math.degrees(2.0 * math.pi / 41)

    @staticmethod
    def _upper_cleaned(chain):
        """与实现同构的上链提取：齿顶超限伪点 + 极角回退坏点（贪心递增）剔除."""
        th0 = math.atan2(chain[0][1], chain[0][0])
        rel = [((math.atan2(p[1], p[0]) - th0 + math.pi) % (2 * math.pi)) - math.pi for p in chain]
        i_fold = max(range(len(rel)), key=rel.__getitem__)
        r_top = 84.5 - 39.5537 + 0.01  # r_f − a + ε（与实现判据一致）
        for i in range(i_fold + 1):
            if math.hypot(chain[i][0], chain[i][1]) > r_top:
                rel[i] = -math.pi
        upper = [chain[0]]
        rel_kept = rel[0]
        for i in range(1, i_fold + 1):
            if rel[i] > rel_kept:
                upper.append(chain[i])
                rel_kept = rel[i]
        return upper

    def test_contains_upper_chain(self):
        """上链点全部保留在闭合轮廓中（延伸/偏置只增不减）."""
        plan = _plan()
        rake = _rake(plan)
        chain = _chain(plan, rake)
        loop = _loop(plan, rake, chain)
        upper = self._upper_cleaned(chain)
        assert len(loop.pts) > len(upper)
        set_u = {(round(p[0], 6), round(p[1], 6), round(p[2], 6)) for p in upper}
        set_l = {(round(p[0], 6), round(p[1], 6), round(p[2], 6)) for p in loop.pts}
        assert set_u <= set_l

    def test_constructed_flags(self):
        """constructed 标记：上链点全 False、构造段全 True.

        /edge 图层附加齿底构造段线依赖该标记（完整刃口 = 共轭上链 + 构造段）。
        """
        plan = _plan()
        rake = _rake(plan)
        chain = _chain(plan, rake)
        loop = _loop(plan, rake, chain)
        flags = loop.constructed
        assert len(flags) == len(loop.pts)
        assert any(flags) and not all(flags)
        set_u = {(round(p[0], 6), round(p[1], 6), round(p[2], 6)) for p in self._upper_cleaned(chain)}
        for p, f in zip(loop.pts, flags):
            if (round(p[0], 6), round(p[1], 6), round(p[2], 6)) in set_u:
                assert f is False
        # 构造段点数 = 总数 − 上链数（上链点全 False、其余全 True）
        assert sum(1 for f in flags if f) == len(flags) - len(set_u)

    def test_upper_chain_monotone(self):
        """清理后上链刀具极角严格递增（zigzag 坏点剔除，2026-08-21 用户反馈）."""
        plan = _plan()
        rake = _rake(plan)
        chain = _chain(plan, rake)
        upper = self._upper_cleaned(chain)
        th0 = math.atan2(chain[0][1], chain[0][0])
        rel = [((math.atan2(p[1], p[0]) - th0 + math.pi) % (2 * math.pi)) - math.pi for p in upper]
        assert all(b > a for a, b in zip(rel, rel[1:]))

    def test_tip_pseudo_points_trimmed(self):
        """齿顶超限伪点剔除：上链半径 ≤ r_f−a+10μm（凸角修复，2026-08-21 用户反馈）."""
        plan = _plan()
        rake = _rake(plan)
        chain = _chain(plan, rake)
        upper = self._upper_cleaned(chain)
        r_top = 84.5 - plan.a + 0.01
        rs = [math.hypot(p[0], p[1]) for p in upper]
        assert max(rs) <= r_top
        # 平顶段精确贴极限圆（真支 r_f−a，伪支超 +24μm 起被剔）
        assert max(rs) == pytest.approx(84.5 - plan.a, abs=2e-3)
        # 伪点确在原始链中存在（超限 +24μm 以上），证明剔除非空转
        raw_over = [math.hypot(p[0], p[1]) for p in chain if math.hypot(p[0], p[1]) > r_top + 0.02]
        assert raw_over, "原始链应含超限伪点（否则判据失效）"

    def test_wide_chain_raises(self):
        """上链展布 ≥ 齿距（相邻刀齿重叠）→ 显式报错（合成带折返的宽链）."""
        plan = _plan()
        rake = _rake(plan)
        wide = [
            [42.0 * math.cos(math.radians(t)), 42.0 * math.sin(math.radians(t)), -1.0]
            for t in list(range(-7, 8)) + list(range(6, -8, -2))  # 上行 14° 后折返
        ]
        with pytest.raises(ValueError, match="齿距"):
            build_tooth_loop(wide, rake, z_t=41, r_pt=plan.r_pt, r_limit=39.9)

    def test_no_fold_raises(self):
        """无折返链（极角单调到尾）→ 显式报错."""
        plan = _plan()
        rake = _rake(plan)
        mono = [
            [42.0 * math.cos(math.radians(t)), 42.0 * math.sin(math.radians(t)), -1.0]
            for t in range(0, 20)
        ]
        with pytest.raises(ValueError, match="折返"):
            build_tooth_loop(mono, rake, z_t=41, r_pt=plan.r_pt, r_limit=39.9)

    def test_degenerate_C_raises(self):
        """前刀面法向 Z 分量 C≈0（γ→90°）→ 极限圆延伸退化，显式报错."""
        plan = _plan()
        degenerate = RakeSurface(A=1.0, B=0.0, C=1e-12, const=-42.0, p_ref=(42.0, 0.0, 0.0))
        with pytest.raises(ValueError, match="退化"):
            build_tooth_loop(_chain(plan, _rake(plan)), degenerate, z_t=41, r_pt=plan.r_pt, r_limit=39.9)

    def test_zt_one_raises(self):
        plan = _plan()
        rake = _rake(plan)
        with pytest.raises(ValueError, match="z_t"):
            build_tooth_loop(_chain(plan, rake), rake, z_t=1, r_pt=plan.r_pt, r_limit=39.9)

    def test_pitch_z_reported(self):
        """pitch_z_mm = 极限圆椭圆弧在 ±π/z_t 两端的高差（阵列固有螺旋错位，算例1 ≈1.6mm）."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        assert 0.0 < loop.pitch_z_mm < 3.0


class TestBuildToothSolid:
    def _solid(self, n_L: int = 2):
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        return build_tooth_solid(
            loop, rake, m_n=2.0, beta_t_deg=15.0, z_t=41, L=0.4, n_L=n_L
        )

    def test_vertex_layout(self):
        solid = self._solid(n_L=2)
        n_vert = len(solid.mesh_positions) // 3
        # v5：前帽独立副本 + (n_L+1) 截面环 + 后帽独立副本（法向硬边分离）
        assert n_vert == (2 + 3) * solid.n_loop
        assert solid.n_sections == 3

    def test_manifold_closed(self):
        """水密 + 一致定向：按位置 weld 后每条无向边恰被 2 三角引用且方向相反.

        硬边分离后帽/ribbon 不再共享**索引**（位置仍重合），故 weld 到几何点计数.
        """
        solid = self._solid(n_L=2)
        P = solid.mesh_positions
        weld: dict[tuple[float, float, float], int] = {}
        wid: list[int] = []
        for i in range(0, len(P), 3):
            key = (round(P[i], 6), round(P[i + 1], 6), round(P[i + 2], 6))
            if key not in weld:
                weld[key] = len(weld)
            wid.append(weld[key])
        use: dict[frozenset[int], list[tuple[int, int]]] = {}
        for t in range(0, len(solid.mesh_indices), 3):
            a, b, c = (wid[solid.mesh_indices[t + k]] for k in range(3))
            for u, v in ((a, b), (b, c), (c, a)):
                use.setdefault(frozenset((u, v)), []).append((u, v))
        assert len(use) > 0
        for edge, dirs in use.items():
            assert len(dirs) == 2, f"边 {edge} 使用 {len(dirs)} 次（应 2）"
            assert dirs[0] == dirs[1][::-1], f"边 {edge} 方向未相反（定向不一致）"

    def test_cap_normals_hard_edge(self):
        """前帽 n 顶点法向均匀一致（共面帽硬边）→ 平滑着色下耳切对角线不可见."""
        solid = self._solid(n_L=2)
        n = solid.n_loop
        N = np.array(solid.mesh_normals, dtype=np.float64).reshape(-1, 3)
        front = N[:n]
        assert np.allclose(front, front[0], atol=1e-12)
        # ribbon 在截面 0 的顶点法向相对帽法向倾斜（硬边分离生效，非全网格平均）
        dots = N[n : 2 * n] @ front[0]
        assert np.any(dots < 1.0 - 1e-6)

    def test_signed_volume_positive(self):
        solid = self._solid(n_L=2)
        assert solid.volume_mm3 > 0.0
        assert solid.volume_mm3 == pytest.approx(
            _signed_volume(solid.mesh_positions, solid.mesh_indices), abs=1e-6
        )
        # 量级：截面积 ≈ 齿形 + 齿根带（> v1 的 13.4mm²）× 扫掠高上界
        assert solid.volume_mm3 > 13.4 * 0.4 * 0.5
        assert solid.volume_mm3 < 60.0 * 2.0 * 0.4 * 2

    def test_normals_unit_length(self):
        solid = self._solid(n_L=2)
        N = np.array(solid.mesh_normals, dtype=np.float64).reshape(-1, 3)
        lens = np.sqrt(N[:, 0] ** 2 + N[:, 1] ** 2 + N[:, 2] ** 2)
        assert np.allclose(lens, 1.0, atol=1e-6)

    def test_ribbon_indices_lateral(self):
        """ribbon（后刀面用）= 侧面三角：mesh_indices 的真子集且索引全部合法."""
        solid = self._solid(n_L=2)
        n_vert = len(solid.mesh_positions) // 3
        assert len(solid.ribbon_indices) > 0
        assert len(solid.ribbon_indices) < len(solid.mesh_indices)
        for v in solid.ribbon_indices:
            assert 0 <= v < n_vert
        set_full = set(solid.mesh_indices)
        assert set(solid.ribbon_indices) <= set_full


class TestBuildToolRing:
    def test_vertex_count_scaled(self):
        """整环顶点 = z_t × 单齿（无填缝带）."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        solid = build_tooth_solid(loop, rake, m_n=2.0, beta_t_deg=15.0, z_t=41, L=0.4, n_L=2)
        ring = build_tool_ring(solid, z_t=41)
        n_tooth = len(solid.mesh_positions) // 3
        assert len(ring.positions) // 3 == 41 * n_tooth
        assert ring.layer_id == "toolRing"

    def test_pitch_boundary_consistency(self):
        """v7 恢复齿距线相位闭合：齿 0 的 +π/z_t 齿距线点（P_R，极限圆上）与齿 1 的
        −π/z_t 点（P_L）同截面极角/半径精确相等（z 差 ≤ pitch_z 螺旋错位）→ 阵列无缝."""
        plan = _plan()
        rake = _rake(plan)
        loop = _loop(plan, rake, _chain(plan, rake))
        z_t = 41
        solid = build_tooth_solid(loop, rake, m_n=2.0, beta_t_deg=15.0, z_t=z_t, L=0.4, n_L=2)
        ring = build_tool_ring(solid, z_t=z_t)
        P = np.array(ring.positions, dtype=np.float64).reshape(-1, 3)
        n_tooth = len(solid.mesh_positions) // 3
        N = solid.n_loop
        r_limit = loop.r_limit
        sec0 = P[0:N]
        ext_pts = [p for p in sec0 if abs(math.hypot(p[0], p[1]) - r_limit) < 1e-6]
        ths = [math.atan2(p[1], p[0]) for p in ext_pts]
        pr = ext_pts[int(np.argmax(ths))]   # 齿 0 的 +π/z_t 齿距线点
        sec1 = P[n_tooth: n_tooth + N]
        ext1 = [p for p in sec1 if abs(math.hypot(p[0], p[1]) - r_limit) < 1e-6]
        ths1 = [math.atan2(p[1], p[0]) for p in ext1]
        pl1 = ext1[int(np.argmin(ths1))]    # 齿 1 的 −π/z_t 齿距线点
        assert math.atan2(pr[1], pr[0]) == pytest.approx(math.atan2(pl1[1], pl1[0]), abs=1e-12)
        assert math.hypot(pr[0], pr[1]) == pytest.approx(math.hypot(pl1[0], pl1[1]), abs=1e-12)
        assert abs(pr[2] - pl1[2]) <= loop.pitch_z_mm + 1e-9


class TestHelicalSolid:
    """斜齿单齿/整环实体（2026-08-25 第二批）：B 方案 v2 管线同构接线.

    斜齿链走数值求交（compute_helical_edge K-2.8b，b_w 必传）+ 闭合环 precut
    （顶缝桥 + 底刃 1/2×2 构造）+ 螺旋导程扫掠。断言：水密流形（每边恰 2 次
    反向使用）、散度体积 >0（与实现互检）、截面数 = n_L+1、半径带 sanity。
    """

    def _helical_case(self, beta_w: float):
        if beta_w > 10.0:  # 19° Tsai 文献参数
            p = GearParams(m_n=1.25, z_w=38, b_w=12.0, k_io=-1, beta_w_deg=beta_w, j_w=1)
            beta_t, z_t = 2.0, 21
        else:
            p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, beta_w_deg=beta_w, j_w=1)
            beta_t, z_t = 15.0, 41
        plan = compute_process_plan(
            z_w=p.z_w, z_t=z_t, m_n=p.m_n, beta_w_deg=beta_w, beta_t_deg=beta_t,
            j_w=1, j_t=-1, k_io=-1,
        )
        prof, norms = extract_gap_points(p, n_points=50)
        rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=beta_t, r_pt=plan.r_pt)
        return p, plan, prof, norms, rake, beta_t, z_t

    @pytest.mark.parametrize("beta_w", [5.0, 19.0])
    def test_helical_solid_watertight_positive_volume(self, beta_w: float):
        from core.envelope.tooth_solid import build_single_tooth_solid

        p, plan, prof, norms, rake, beta_t, z_t = self._helical_case(beta_w)
        solid = build_single_tooth_solid(
            prof, plan, rake, r_a=p.tip_radius(), beta_t_deg=beta_t, z_t=z_t,
            m_n=p.m_n, L=20.0, n_L=8, m=181, r_f=p.root_radius(),
            normals=norms, b_w=p.b_w, n_z=21,
        )
        n_v = len(solid.mesh_positions) // 3
        assert n_v > 100
        assert solid.n_sections == 9  # n_L + 1（前帽 + 截面 + 后帽布局下截面数）
        # 水密 + 一致定向（帽独立顶点 → 按位置 weld 后计数，与直齿 test_manifold_closed 同法）
        P = solid.mesh_positions
        weld: dict[tuple[float, float, float], int] = {}
        wid: list[int] = []
        for i in range(0, len(P), 3):
            key = (round(P[i], 6), round(P[i + 1], 6), round(P[i + 2], 6))
            if key not in weld:
                weld[key] = len(weld)
            wid.append(weld[key])
        use: dict[frozenset[int], list[tuple[int, int]]] = {}
        for t in range(0, len(solid.mesh_indices), 3):
            a, b, c = (wid[solid.mesh_indices[t + k]] for k in range(3))
            for u, v in ((a, b), (b, c), (c, a)):
                use.setdefault(frozenset((u, v)), []).append((u, v))
        for dirs in use.values():
            assert len(dirs) == 2, "边使用次数 ≠ 2（不水密）"
            assert dirs[0] == dirs[1][::-1], "边方向未相反（定向不一致）"
        # 体积 > 0（实现字段与独立散度计算互检）
        vol_ext = _signed_volume(solid.mesh_positions, solid.mesh_indices)
        assert solid.volume_mm3 > 0.0 and vol_ext > 0.0
        assert solid.volume_mm3 == pytest.approx(vol_ext, rel=1e-9)
        # 半径带 sanity：谷底 < 齿顶 < r_pt + 3×齿高（粗筛护栏同界）
        rs = [math.hypot(solid.mesh_positions[i], solid.mesh_positions[i + 1])
              for i in range(0, len(solid.mesh_positions), 3)]
        h = p.root_radius() - p.tip_radius()
        assert min(rs) > 0.0
        assert max(rs) < plan.r_pt + 3.0 * h

    def test_helical_tool_ring_scaled(self):
        from core.envelope.tooth_solid import build_single_tooth_solid

        p, plan, prof, normals, rake, beta_t, z_t = self._helical_case(5.0)
        solid = build_single_tooth_solid(
            prof, plan, rake, r_a=p.tip_radius(), beta_t_deg=beta_t, z_t=z_t,
            m_n=p.m_n, L=20.0, n_L=8, m=181, r_f=p.root_radius(),
            normals=normals, b_w=p.b_w, n_z=21,
        )
        ring = build_tool_ring(solid, z_t=z_t)
        n_per = len(solid.mesh_positions) // 3
        assert len(ring.positions) // 3 == n_per * z_t

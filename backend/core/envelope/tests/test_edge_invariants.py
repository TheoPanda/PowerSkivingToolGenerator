"""斜齿刃形几何不变量护栏（2026-08-25 设立）.

背景：斜齿刃形曾因「方向选根只取下降穿越」系统性缩窄（齿根弧共轭是上升穿越，
被整段丢弃——β5 展布 5.69°→3.16°、β10→0.4°），靠用户目检发现、三轮排查定位，
成本极高。本组测试把「刃形形状的物理不变量」数值化，让此类缺陷在交付前变红：

1. 路径连续性：β→0⁺ 的斜齿路径必须逼近直齿路径（同一物理、两条代码路径）；
2. 齿根共轭到达：链底半径必须落到齿顶圆柱共轭带（r_w_min − a 邻域）；
3. live 密度闭环：n=200（前端默认）下闭合环可构造且展布合理——测试密度 n=50
   曾掩盖 19° 的密度敏感缺陷。

约定：本组全部 n=200（对齐 live），比常规测试慢（每用例 ~10s），值得。
"""

import math

import pytest

from core.envelope.edge import solve_edge_chain
from core.envelope.process_plan import compute_process_plan
from core.envelope.rake import build_plane_rake
from core.envelope.swept_cloud import extract_gap_points
from core.envelope.tooth_solid import build_tooth_loop, limit_radius
from core.workpiece.models import GearParams


def _case(beta_w: float):
    """算例1 家族（m2 z82 b20 / z_t41 β_t15 γ5），n=200（live 密度）."""
    p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1, beta_w_deg=beta_w, j_w=1)
    plan = compute_process_plan(
        z_w=82, z_t=41, m_n=2.0, beta_w_deg=beta_w, beta_t_deg=15.0, j_w=1, j_t=-1, k_io=-1,
    )
    prof, norms = extract_gap_points(p, n_points=200)
    rake = build_plane_rake(gamma_deg=5.0, beta_t_deg=15.0, r_pt=plan.r_pt)
    pts, _, cols, br = solve_edge_chain(
        prof, plan, rake, m=181, theta_range_deg=40.0, normals=norms,
        b_w=(20.0 if beta_w > 1e-9 else 0.0), n_z=21,
    )
    return p, plan, rake, pts, cols, br


def _spread_deg(pts) -> float:
    th = [math.atan2(q[1], q[0]) for q in pts]
    return math.degrees(max(th) - min(th))


class TestEdgeInvariants:
    def test_spur_path_continuity(self):
        """β=0.1°（斜齿路径）≈ β=0°（直齿路径）：展布差 <0.3°、链底差 <0.5mm.

        两条代码路径解同一物理——不连续即有一侧系统性错（方向选根缺陷时代
        β0.1 展布 5.42° vs 直齿 5.70°，差 0.28° 恰在本阈边缘；丢齿根共轭修复
        后 5.687° vs 5.696°，差 0.01°）。
        """
        _, plan0, _, pts0, cols0, _ = _case(0.0)
        _, plan1, _, pts1, cols1, _ = _case(0.1)
        s0, s1 = _spread_deg(pts0), _spread_deg(pts1)
        assert abs(s1 - s0) < 0.3, f"路径不连续：直齿 {s0:.3f}° vs β0.1 {s1:.3f}°"
        r0 = min(math.hypot(q[0], q[1]) for q in pts0)
        r1 = min(math.hypot(q[0], q[1]) for q in pts1)
        assert abs(r1 - r0) < 0.5, f"链底半径不连续：{r0:.3f} vs {r1:.3f}"
        # 列域同达折返（直齿 199 列全、斜齿折返切割后 [0,~144]）
        assert max(cols1) >= 143, f"斜齿链止于列 {max(cols1)}（折返 col≈144 前）"

    def test_rootland_conjugated_beta5(self):
        """β5° 链底须达齿顶圆柱共轭带（r_w_min − a 邻域）.

        丢上升根缺陷时代链底 42.08（抬高 1.6mm，齿根被构造长坡腿替代）；
        修复后 40.59 ≈ 80.31 − a(β5)=40.44。判据：min r ≤ (r_w_min − a) + 0.6。
        """
        p, plan, _, pts, _, _ = _case(5.0)
        r_lo = p.tip_radius()  # 工件齿顶圆（内齿轮槽开口边界）
        r_expect = r_lo - plan.a
        r_min = min(math.hypot(q[0], q[1]) for q in pts)
        assert r_min <= r_expect + 0.6, (
            f"链底 {r_min:.3f} 未达齿根共轭带（{r_expect:.3f}+0.6）——齿根共轭丢失"
        )

    def test_beta5_loop_at_live_density(self):
        """β5° n=200（live）：闭合环可构造、展布 ≥4.5°（直齿 5.696° 的 −21% 内）.

        n=50 测试密度曾掩盖密度敏感缺陷（19°@n200 混支自交即此类）。
        """
        p, plan, rake, pts, cols, br = _case(5.0)
        loop = build_tooth_loop(
            pts, rake, z_t=41, r_pt=plan.r_pt,
            r_limit=limit_radius(p.tip_radius(), plan.a),
            r_f=p.root_radius(), a=plan.a, precut=True, upper_constructed=br,
        )
        assert loop.arch_spread_deg >= 4.5, f"live 密度展布 {loop.arch_spread_deg:.3f}° 缩窄"
        assert len(loop.pts) > len(pts), "环应含构造段（延伸/偏置/谷底弧）"

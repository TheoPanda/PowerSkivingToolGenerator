"""模块② ProcessPlan（K-1.4~K-1.8）测试 — 纯数学，可入 CI.

算例1（标准渐开线内直齿轮）做 K-1.4~1.8 全量硬回归；
算例2（三圆弧内齿轮）只验节圆无关的量（Σ/i/同步比/r_pw）——
其 r_pt=13.5876 为「反推节圆」，与标准渐开线 K-1.6（含 cosβ_t）不自洽。
"""

import math

import pytest

from core.envelope.process_plan import compute_process_plan


class TestExample1:
    """算例1（[23] 内直齿轮，标准渐开线）— K-1.4~K-1.8 硬参考回归"""

    def test_ex1_install_and_motion(self):
        # 工件 z_w=82（内直齿轮 k_io=−1），刀具 z_t=41、β_t=15°、j_t=−1（左旋）
        plan = compute_process_plan(
            z_w=82, z_t=41, m_n=2.0,
            beta_w_deg=0.0, beta_t_deg=15.0,
            j_w=1, j_t=-1, k_io=-1,
        )
        assert plan.sigma_deg == pytest.approx(15.0, abs=1e-6)
        assert plan.r_pw == pytest.approx(82.0, abs=1e-9)
        # 精确 r_pt = 41/cos15° = 42.4463；文献表值 d₁=84.91（精确 84.8926，舍入差 0.017）
        # 故 r₁=42.455、a=82−42.455=39.545，与精确 39.5537 差 0.0087（ADR-019：文献为参考基准）
        assert plan.r_pt == pytest.approx(42.455, abs=0.01)
        assert plan.a == pytest.approx(39.545, abs=0.01)
        assert plan.i == pytest.approx(2.0, abs=1e-9)        # −k_io·z_w/z_t = +2（内齿轮）
        assert plan.omega_ratio == pytest.approx(2.0, abs=1e-9)


class TestExample2:
    """算例2（[21] 三圆弧内齿轮）— 节圆无关量验证"""

    def test_ex2_sigma_i_ratio(self):
        plan = compute_process_plan(
            z_w=102, z_t=68, m_n=0.399635,
            beta_w_deg=0.0, beta_t_deg=15.0,
            j_w=1, j_t=-1, k_io=-1,
        )
        assert plan.sigma_deg == pytest.approx(15.0, abs=1e-6)
        # 内齿轮 i=+1.5（设计书第3章 §3.3 标 −1.5 系笔误，与第4章伪代码/算例3 自洽）
        assert plan.i == pytest.approx(1.5, abs=1e-9)
        assert plan.omega_ratio == pytest.approx(1.5, abs=1e-9)
        assert plan.r_pw == pytest.approx(20.3814, abs=1e-4)


class TestHelicalWorkpiece:
    """斜齿工件（β_w≠0）— K-1.4~K-1.6 有符号 Σ / 螺旋面节圆（2026-08-15 产形面支持）"""

    def test_helical_internal_install(self):
        # 文献 Tsai 2023 内斜齿轮：β_w=19°（右旋 j_w=1）、刀具 β_t=2°（左旋 j_t=−1）
        beta_w = math.radians(19.0)
        beta_t = math.radians(2.0)
        plan = compute_process_plan(
            z_w=38, z_t=21, m_n=1.25,
            beta_w_deg=19.0, beta_t_deg=2.0,
            j_w=1, j_t=-1, k_io=-1,
        )
        # Σ = j_w·β_w − j_t·β_t = 19° − (−2°) = 21°（内齿轮旋向相反 → 相加）
        assert plan.sigma_deg == pytest.approx(21.0, abs=1e-6)
        assert plan.beta_w_deg == 19.0
        assert plan.j_w == 1
        # r_pw = m_t·z_w/2，m_t = m_n/cosβ_w；r_pt = r_pw·z_t·cosβ_w/(z_w·cosβ_t)（K-1.6）
        m_t = 1.25 / math.cos(beta_w)
        r_pw = m_t * 38 / 2.0
        r_pt = r_pw * 21 * math.cos(beta_w) / (38 * math.cos(beta_t))
        assert plan.r_pw == pytest.approx(r_pw, rel=1e-12)
        assert plan.r_pt == pytest.approx(r_pt, rel=1e-12)
        assert plan.a == pytest.approx(r_pw - r_pt, rel=1e-12)
        # 同步比/传动比与螺旋角无关（滚动项）
        assert plan.omega_ratio == pytest.approx(38.0 / 21.0, abs=1e-9)
        assert plan.i == pytest.approx(38.0 / 21.0, abs=1e-9)

    def test_spur_still_zero_sigma_when_beta_t_zero(self):
        """直齿 β_w=0 且 β_t=0 → Σ=0 仍拒绝（退化保护，零回归）."""
        with pytest.raises(ValueError, match="Σ=0"):
            compute_process_plan(
                z_w=82, z_t=41, m_n=2.0,
                beta_w_deg=0.0, beta_t_deg=0.0,
                j_w=1, j_t=1, k_io=-1,
            )


class TestFailureModes:
    """失效模式"""

    def test_zero_sigma_rejected(self):
        with pytest.raises(ValueError, match="Σ=0"):
            compute_process_plan(
                z_w=82, z_t=41, m_n=2.0,
                beta_w_deg=0.0, beta_t_deg=0.0,
                j_w=1, j_t=1, k_io=-1,
            )

    def test_nonpositive_a_rejected(self):
        # 内齿轮 z_t=82 > z_w=41 → r_pt > r_pw → a < 0
        with pytest.raises(ValueError, match="中心距"):
            compute_process_plan(
                z_w=41, z_t=82, m_n=2.0,
                beta_w_deg=0.0, beta_t_deg=15.0,
                j_w=1, j_t=-1, k_io=-1,
            )

    def test_invalid_k_io(self):
        with pytest.raises(ValueError, match="k_io"):
            compute_process_plan(
                z_w=82, z_t=41, m_n=2.0,
                beta_w_deg=0.0, beta_t_deg=15.0,
                j_w=1, j_t=-1, k_io=0,
            )

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


class TestFailureModes:
    """失效模式"""

    def test_helical_workpiece_rejected(self):
        with pytest.raises(ValueError, match="斜齿"):
            compute_process_plan(
                z_w=82, z_t=41, m_n=2.0,
                beta_w_deg=10.0, beta_t_deg=15.0,
                j_w=1, j_t=-1, k_io=-1,
            )

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

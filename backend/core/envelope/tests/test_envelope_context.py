"""模块② 包络上下文装配（assemble_envelope_context）测试 — 纯数学，可入 CI.

验证 EnvelopeContext 把「compute_process_plan + extract_gap_points + build_plane_rake」
三深模块正确装配（正确顺序 + 正确参数），并保持纯数据边界（无 FastAPI/pydantic）。
"""

import math

from core.envelope.envelope_context import ToolSpec, assemble_envelope_context
from core.envelope.process_plan import compute_process_plan
from core.envelope.rake import build_plane_rake
from core.workpiece.models import GearParams


def _internal_case(n: int = 50):
    """内齿轮算例1（z_w=82, z_t=41, 直齿 β_w=0, 刀具 β_t=15° 左旋 → Σ=15°）."""
    p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=-1)
    tool = ToolSpec(z_t=41, beta_t_deg=15.0, j_t=-1, gamma_0_deg=5.0)
    return p, tool, n


class TestAssembleEnvelopeContext:
    def test_plan_matches_direct_compute(self):
        """装配出的 ProcessPlan 与直接调 compute_process_plan 逐字段一致."""
        p, tool, n = _internal_case()
        ctx = assemble_envelope_context(p, tool, n=n)
        plan = compute_process_plan(
            z_w=p.z_w, z_t=tool.z_t, m_n=p.m_n,
            beta_w_deg=p.beta_w_deg, beta_t_deg=tool.beta_t_deg,
            j_w=p.j_w, j_t=tool.j_t, k_io=p.k_io,
        )
        assert ctx.plan == plan  # frozen dataclass，确定性输出 → 值相等

    def test_pts_norms_length_and_unit(self):
        """齿廓点与法向等长、非空、法向为单位向量."""
        p, tool, n = _internal_case()
        ctx = assemble_envelope_context(p, tool, n=n)
        assert len(ctx.pts) == n
        assert len(ctx.norms) == len(ctx.pts)
        for nx, ny in ctx.norms:
            assert abs(math.hypot(nx, ny) - 1.0) < 1e-9

    def test_rake_matches_direct_build(self):
        """装配出的前刀面与直接调 build_plane_rake 逐字段一致."""
        p, tool, n = _internal_case()
        ctx = assemble_envelope_context(p, tool, n=n)
        rake = build_plane_rake(tool.gamma_0_deg, tool.beta_t_deg, ctx.plan.r_pt)
        assert ctx.rake == rake

    def test_default_n_is_200(self):
        """不传 n 时默认采样点数 200（rake 端点无需离散化时依赖此默认）."""
        p, tool, _ = _internal_case()
        ctx = assemble_envelope_context(p, tool)
        assert len(ctx.pts) == 200

    def test_helical_plan_fields(self):
        """斜齿工件（β_w=19° 右旋）：plan 携带 beta_w_deg/j_w，Σ 自洽，pts 非空."""
        p = GearParams(m_n=1.25, z_w=38, b_w=12.0, k_io=-1, beta_w_deg=19.0, j_w=1)
        tool = ToolSpec(z_t=21, beta_t_deg=2.0, j_t=-1, gamma_0_deg=5.0)
        ctx = assemble_envelope_context(p, tool, n=30)
        assert ctx.plan.beta_w_deg == 19.0
        assert ctx.plan.j_w == 1
        assert abs(ctx.plan.sigma_deg - 21.0) < 1e-9  # Σ = j_w·β_w − j_t·β_t = 19 − (−2)
        assert len(ctx.pts) == 30

    def test_external_gear_plan_sign(self):
        """外齿轮（k_io=+1）不阻塞装配，传动比 i 为负（含内外啮合方向）."""
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=1)
        tool = ToolSpec(z_t=41, beta_t_deg=15.0, j_t=-1)
        ctx = assemble_envelope_context(p, tool, n=10)
        assert ctx.plan.i < 0  # i = −k_io·z_w/z_t = −2


class TestCapability:
    """能力矩阵（supports_*）单一权威：β_w + k_io 派生."""

    def test_internal_spur_supports_all(self):
        """内齿轮直齿：刃形/后刀面/单齿/解析路线均可用."""
        p, tool, n = _internal_case()
        ctx = assemble_envelope_context(p, tool, n=n)
        assert ctx.supports_edge is True
        assert ctx.supports_flank is True
        assert ctx.supports_single_tooth is True
        assert ctx.supports_analytic is True

    def test_helical_all_unlocked(self):
        """内斜齿轮：刃形族全解锁（K-2.8b 数值求交 + 第二批实体建模，2026-08-25）；仅解析限直齿."""
        p = GearParams(m_n=1.25, z_w=38, b_w=12.0, k_io=-1, beta_w_deg=19.0, j_w=1)
        tool = ToolSpec(z_t=21, beta_t_deg=2.0, j_t=-1)
        ctx = assemble_envelope_context(p, tool, n=30)
        assert ctx.supports_edge is True
        assert ctx.supports_flank is True
        assert ctx.supports_single_tooth is True
        assert ctx.supports_tool_ring is True
        assert ctx.supports_analytic is False

    def test_external_gear_no_edge(self):
        """外齿轮（k_io=+1）：刃形符号 T14 未销项 → 不可用（即使直齿）."""
        p = GearParams(m_n=2.0, z_w=82, b_w=20.0, k_io=1)
        tool = ToolSpec(z_t=41, beta_t_deg=15.0, j_t=-1)
        ctx = assemble_envelope_context(p, tool, n=10)
        assert ctx.supports_edge is False

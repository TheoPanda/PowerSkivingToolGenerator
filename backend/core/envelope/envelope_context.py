"""模块② 包络计算上下文 — 把「请求 → 领域装配」收进一个深模块（纯数学，无 FastAPI/pydantic）.

8 个包络端点（swept_cloud/edge/conjugate/conjugate_gear/rake/flank/single_tooth/analytic）
历史上各自重复同一段装配样板：

    plan = compute_process_plan(z_w, z_t, m_n, beta_w_deg, beta_t_deg, j_w, j_t, k_io)
    pts, norms = extract_gap_points(p, n)
    rake = build_plane_rake(gamma_0, beta_t, plan.r_pt)

这段「工件参数 → ProcessPlan → 齿廓点+法向 → 前刀面」是领域计算装配，不是 HTTP 样板。
本模块把它收进单一接口 assemble_envelope_context：调用方传纯数据（GearParams + ToolSpec），
内部按正确顺序、正确参数调用三个深模块（compute_process_plan / extract_gap_points /
build_plane_rake），返回 EnvelopeContext。router 从「8 份样板」退化为「1 行装配」的薄适配器。

纯数据（Q1）：不 import fastapi/pydantic，GearParams/ToolSpec 均为 dataclass，保持
ADR-001「几何计算全后端、纯数学可入 CI」的边界（router.py 是唯一 HTTP 边界）。
不依赖 OCCT。
"""

from dataclasses import dataclass

from core.envelope.process_plan import ProcessPlan, compute_process_plan
from core.envelope.rake import RakeSurface, build_plane_rake
from core.envelope.swept_cloud import extract_gap_points
from core.workpiece.models import GearParams


@dataclass(frozen=True)
class ToolSpec:
    """刀具参数纯数据载体（与 router 的 pydantic ToolParams 对偶，与 GearParams 对偶）.

    assemble 只用 z_t/beta_t_deg/j_t（plan）+ gamma_0_deg（rake）；alpha_0_deg 供
    flank/single_tooth 端点自取（重磨径向分量 K-2.18），assemble 不参与。
    """

    z_t: int
    beta_t_deg: float
    j_t: int = 1
    gamma_0_deg: float = 5.0
    alpha_0_deg: float = 8.0


@dataclass(frozen=True)
class EnvelopeContext:
    """包络计算上下文 = 三个深模块（ProcessPlan + 齿廓点/法向 + 前刀面）的装配产物.

    坐标约定：plan 为坐标无关标量；pts/norms 为工件端面齿槽廓形（坐标 W 端面）；
    rake 为前刀面隐式方程（坐标 T）。

    capability 字段（supports_edge / supports_flank / supports_single_tooth /
    supports_tool_ring / supports_analytic）是「哪些派生几何可用」的单一权威：
    由工件侧约束派生。外齿轮 k_io=+1（刃形符号 T14 未销项）使刃形族全部不可用；
    斜齿 β_w≠0 全族已支持（2026-08-24 刃形数值求交 K-2.8b + 2026-08-25 第二批
    实体建模：B 方案 v2 螺旋导程法扫掠/前后帽管线与齿侧螺旋无关、同构适用）；
    仅解析路线（消元法依赖齿面对 z_w 仿射）仍限直齿。
    前端 runEnvelope 消费它们决定调哪些端点，不再镜像本地 isHelical 判断；
    compute 层 raise 保留为防御性断言。
    """

    plan: ProcessPlan
    pts: list[tuple[float, float]]
    norms: list[tuple[float, float]]
    rake: RakeSurface
    supports_edge: bool
    supports_flank: bool
    supports_single_tooth: bool
    supports_tool_ring: bool
    supports_analytic: bool  # 解析路线（消元法，仅直齿；斜齿走数值求交 K-2.8b）


def assemble_envelope_context(p: GearParams, tool: ToolSpec, n: int = 200) -> EnvelopeContext:
    """把「工件参数 + 刀具参数」装配成包络计算上下文（唯一权威）.

    单一入口收拢 8 个端点共享的「compute_process_plan + extract_gap_points +
    build_plane_rake」样板。新增 ProcessPlan 字段只需改这一处，不再 8 处。

    Args:
        p: 工件齿轮参数（GearParams，含 z_w/m_n/beta_w_deg/j_w/k_io）
        tool: 刀具参数（ToolSpec，含 z_t/beta_t_deg/j_t/gamma_0_deg）
        n: 齿廓采样点数（默认 200；rake 端点无需离散化时用默认）

    Returns:
        EnvelopeContext（plan / pts / norms / rake）

    Raises:
        ValueError: 参数非法（由三个深模块各自抛出）
    """
    plan = compute_process_plan(
        z_w=p.z_w, z_t=tool.z_t, m_n=p.m_n,
        beta_w_deg=p.beta_w_deg, beta_t_deg=tool.beta_t_deg,
        j_w=p.j_w, j_t=tool.j_t, k_io=p.k_io,
    )
    pts, norms = extract_gap_points(p, n)
    rake = build_plane_rake(tool.gamma_0_deg, tool.beta_t_deg, plan.r_pt)
    # 能力矩阵（单一权威）：外齿轮禁刃形族；斜齿全族已支持（刃形 K-2.8b 数值求交
    # + 第二批实体建模同构管线），仅解析路线（消元法）限直齿（见类 docstring）。
    is_helical = abs(plan.beta_w_deg) > 1e-12
    internal = (p.k_io == -1)
    return EnvelopeContext(
        plan=plan, pts=pts, norms=norms, rake=rake,
        supports_edge=internal,
        supports_flank=internal,
        supports_single_tooth=internal,
        supports_tool_ring=internal,
        supports_analytic=(not is_helical) and internal,
    )

"""模块② 包络计算路由.

真实离散包络 swept_cloud（扫掠点云 K-2.9）/ edge（刃形 K-2.11~2.13）等端点。
"""

import math
import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.common.gltf_export import GeometrySpec, export_geometry_glb_base64
from core.common.mesh import compute_vertex_normals
from core.envelope.edge import extract_edge, solve_edge_chain
from core.envelope.swept_cloud import WIREFRAME_COLOR, generate_envelope_cloud
from core.envelope.envelope_context import ToolSpec, assemble_envelope_context
from core.envelope.rake import normal_arrow, plane_patch
from core.envelope.single_tooth import build_single_tooth
from core.envelope.tool_body import build_tool_body, resolve_tool_body_params
from core.envelope.tooth_solid import (
    build_single_tooth_solid,
    build_tooth_loop,
    build_tool_ring,
    helical_lead_mm,
    limit_radius,
)
from core.envelope.analytic import compute_analytic_edge, cross_check
from core.envelope.conjugate import compute_conjugate_surface
from core.envelope.conjugate_gear import compute_conjugate_gear
from core.workpiece.router import GearParamsRequest

router = APIRouter(prefix="/api/envelope", tags=["envelope"])


# ── 子 PRD-2 离散包络端点 ─────────────────────────────────────────────


class ToolParams(BaseModel):
    """刀具参数（组B 子集）— swept_cloud / edge 共用."""

    z_t: int = Field(..., ge=1, description="刀具齿数")
    beta_t_deg: float = Field(..., ge=0.0, description="刀具螺旋角 [°]")
    j_t: int = Field(1, description="刀具旋向 +1/−1")
    gamma_0_deg: float = Field(5.0, description="设计前角 γ₀ [°]（K-2.1 前刀面输入）")
    alpha_0_deg: float = Field(8.0, description="顶刃后角 α₀ [°]（K-2.18 径向重磨分量）")


def _tool_spec(t: ToolParams) -> ToolSpec:
    """pydantic ToolParams → 领域纯数据 ToolSpec（pydantic 拆包留在 router，Q1）."""
    return ToolSpec(
        z_t=t.z_t, beta_t_deg=t.beta_t_deg, j_t=t.j_t,
        gamma_0_deg=t.gamma_0_deg, alpha_0_deg=t.alpha_0_deg,
    )


class DiscretizationParams(BaseModel):
    """离散参数（后端默认，可覆盖）."""

    n: int = Field(200, ge=2)
    m: int = Field(181, ge=2)
    theta_range_deg: float = Field(40.0, gt=0)
    n_z: int = Field(21, ge=2, description="产形面轴向层数（conjugate 端点用）")


class EnvelopeRequest(BaseModel):
    """离散包络请求体（swept_cloud / edge 共用）."""

    workpiece: GearParamsRequest
    tool: ToolParams
    discretization: DiscretizationParams = DiscretizationParams()
    include_anim: bool = Field(False, description="是否返回逐帧动画数据（conjugate 端点）")
    m_anim: int = Field(72, ge=4, description="动画帧数（include_anim=True 时有效）")
    anim_theta_range_deg: float = Field(360.0, gt=0, description="动画角度范围 [°]（默认 ±360°）")


@router.post("/capability")
def envelope_capability(req: EnvelopeRequest) -> dict:
    """能力查询：哪些派生几何可用（β_w + k_io 派生），前端替代本地 isHelical.

    单一权威：supports_* 由 assemble_envelope_context 从 plan + k_io 派生，
    与 compute 层 raise 同源（raise 保留为防御性断言）。
    """
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool))
        return {
            "capability": {
                "supports_edge": ctx.supports_edge,
                "supports_flank": ctx.supports_flank,
                "supports_single_tooth": ctx.supports_single_tooth,
                "supports_tool_ring": ctx.supports_tool_ring,
                "supports_analytic": ctx.supports_analytic,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


@router.post("/swept_cloud")
def envelope_swept_cloud(req: EnvelopeRequest) -> dict:
    """K-2.9 扫掠点云端点：工件齿槽点云经运动包络 → 多 primitive GLB（面+点+线框）+ motion 元数据."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool), n=req.discretization.n)
        cloud = generate_envelope_cloud(
            ctx.pts, ctx.plan, m=req.discretization.m,
            theta_range_deg=req.discretization.theta_range_deg,
        )
        n = len(ctx.pts)
        m = req.discretization.m
        n_vertices = m * n

        # 线框常量灰顶点色（与 positions 等长，中性深灰 #1f2937）
        gr, gg, gb = WIREFRAME_COLOR
        wire_colors = [gr, gg, gb] * n_vertices

        geos = [
            GeometrySpec(
                kind="mesh",
                positions=cloud.mesh_positions,
                indices=cloud.mesh_indices,
                normals=cloud.mesh_normals,
                colors=cloud.mesh_colors,
                layer_id="swept_cloud",
            ),
            GeometrySpec(
                kind="points",
                positions=cloud.mesh_positions,
                colors=cloud.mesh_colors,
                layer_id="swept_cloud.points",
            ),
            GeometrySpec(
                kind="lines",
                positions=cloud.mesh_positions,
                indices=cloud.wireframe_indices,
                colors=wire_colors,
                layer_id="swept_cloud.wireframe",
            ),
        ]
        glb = export_geometry_glb_base64(geos)
        motion = {
            "n": n,
            "m": m,
            "theta_range_deg": req.discretization.theta_range_deg,
            "surface_indices_per_row": (n - 1) * 6,
            "points_vertices_per_row": n,
            "wireframe_indices_per_row": 12 * (n - 1),
        }
        return {
            "layer": {"id": "swept_cloud", "glb_base64": glb},
            "coord_frame": "T",
            "motion": motion,
            "install": {"a": ctx.plan.a, "sigma_deg": ctx.plan.sigma_deg},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


@router.post("/edge")
def envelope_edge(req: EnvelopeRequest) -> dict:
    """K-2.8 刃形端点：产形面 ∩ 前刀面（共轭法）→ 覆盖 + ffα → 刃形 GLB."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool), n=req.discretization.n)
        edge = extract_edge(
            ctx.pts, ctx.plan, ctx.rake, m=req.discretization.m,
            theta_range_deg=req.discretization.theta_range_deg, k_io=p.k_io, normals=ctx.norms,
            b_w=p.b_w, n_z=req.discretization.n_z,  # 斜齿数值求交路线（K-2.8b）用
        )

        # 每个刃形段 → 一个 LINE_STRIP GeometrySpec（完整闭合环失败时的降级形态）
        geos = [
            GeometrySpec(
                kind="line",
                positions=[c for pt in seg.pts for c in pt],
                layer_id="edge",
            )
            for seg in edge.segments
        ]

        # B 方案 v2 完整刃形闭合环：共轭上链（白）+ 齿底构造段（橙：齿根延伸/
        # 径向偏置/谷底圆弧）一条 LINE_STRIP，尾点回绕首点闭合。成功时替换共轭
        # 分段线（同一刃形避免双线重合）；构造段非共轭（齿底无共轭曲面），用逐
        # 顶点色区分。失败仅降级为共轭分段（刃形主契约是共轭诊断）。
        closed_loop = False
        try:
            is_helical = abs(p.beta_w_deg) > 1e-12
            chain_pts, _, _, bridge_mask = solve_edge_chain(
                ctx.pts, ctx.plan, ctx.rake,
                m=req.discretization.m,
                theta_range_deg=req.discretization.theta_range_deg,
                normals=ctx.norms,
                b_w=p.b_w, n_z=req.discretization.n_z,  # 斜齿数值求交链（K-2.8b）用
            )
            r_limit = limit_radius(p.tip_radius(), ctx.plan.a)
            loop = build_tooth_loop(
                chain_pts, ctx.rake, z_t=req.tool.z_t, r_pt=ctx.plan.r_pt, r_limit=r_limit,
                r_f=p.root_radius(), a=ctx.plan.a,
                precut=is_helical,  # 斜齿链已是上链（含顶缝桥点，构造标记传入）
                upper_constructed=bridge_mask if is_helical else None,
            )
            ring_pts = list(loop.pts) + [loop.pts[0]]
            colors: list[float] = []
            for flag in list(loop.constructed) + [loop.constructed[0]]:
                colors += [0.96, 0.55, 0.13] if flag else [1.0, 1.0, 1.0]
            geos = [
                GeometrySpec(
                    kind="line",
                    positions=[c for pt in ring_pts for c in pt],
                    colors=colors,
                    layer_id="edge",
                )
            ]
            closed_loop = True
        except ValueError as e:
            print(f"[edge] 完整刃形闭合环未生成（降级为共轭分段线）：{e}")
        glb = export_geometry_glb_base64(geos) if geos else ""

        return {
            "layer": {"id": "edge", "glb_base64": glb},
            "coord_frame": "T",
            "coverage_report": edge.coverage_report,
            "ffa_um": edge.ffa_um,
            "residual_stats": edge.residual_stats,  # 斜齿双残差（直齿 None）
            "segments_meta": [
                {"count": len(seg.pts), "continuity": seg.continuity}
                for seg in edge.segments
            ],
            "closed_loop": closed_loop,
            "install": {"a": ctx.plan.a, "sigma_deg": ctx.plan.sigma_deg},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


# ── 子 PRD-5 产形面（共轭面）端点 ───────────────────────────────────


@router.post("/conjugate")
def envelope_conjugate(req: EnvelopeRequest) -> dict:
    """K-2.6 产形面端点：数值啮合方程（n·v=0）→ 共轭面三角网 GLB（坐标 T）."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool), n=req.discretization.n)
        # 斜齿接触位更广的下限（120°）已下沉到 compute_conjugate_surface 内部
        surf = compute_conjugate_surface(
            ctx.pts, ctx.plan, b_w=p.b_w, k_io=p.k_io,
            n_z=req.discretization.n_z, m=req.discretization.m,
            theta_range_deg=req.discretization.theta_range_deg, normals=ctx.norms,
            include_anim=req.include_anim, m_anim=req.m_anim,
            anim_theta_range_deg=req.anim_theta_range_deg,
        )
        geo = GeometrySpec(
            kind="mesh", positions=surf.mesh_positions,
            indices=surf.mesh_indices, normals=surf.mesh_normals, layer_id="conjugate",
        )
        glb = export_geometry_glb_base64([geo])
        resp: dict = {
            "layer": {"id": "conjugate", "glb_base64": glb},
            "coord_frame": "T",
            "coverage_report": surf.coverage,
            "install": {"a": ctx.plan.a, "sigma_deg": ctx.plan.sigma_deg},
        }
        if req.include_anim and surf.anim_frames:
            resp["anim"] = {
                "frames": [
                    {"phi_t_deg": f.phi_t_deg, "positions": f.positions}
                    for f in surf.anim_frames
                ],
                "indices": surf.anim_indices,
                "mesh_indices": surf.anim_mesh_indices,
                "n_vertices": len(surf.anim_indices),
                "theta_range_deg": float(
                    max(req.discretization.theta_range_deg, 120.0)
                    if abs(p.beta_w_deg) > 1e-12
                    else req.discretization.theta_range_deg
                ),
                # K-0.5 链合成参数（ω_t/ω_w = z_w/z_t 恒正）：前端据 Rot_z(−φ_t)·Rot_x(−Σ)·
                # Tran_x(−a)·Rot_z(φ_t/ω) 实时合成任意 φ 的扫掠位置（帧数据不再限制滑条范围）
                "omega_ratio": float(ctx.plan.omega_ratio),
                # 截面切片元数据：顶点行主序 iz·n + iu（iz = indices//n_profile），
                # 供前端「沿齿向拖动选廓线平面」（单层廓线扫掠可视化）
                "n_profile": len(ctx.pts),
                "layer_zs": [
                    -p.b_w / 2.0 + p.b_w * i / max(1, req.discretization.n_z - 1)
                    for i in range(req.discretization.n_z)
                ],
            }
        return resp
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


@router.post("/tooth_flank")
def envelope_tooth_flank(req: EnvelopeRequest) -> dict:
    """内齿轮齿面端点：参与求解的工件齿面网格（坐标 W）→ 离散点 + 法向箭头 GLB.

    与 /conjugate 同款求解（同离散参数）多取参与掩码（最终 found，含全部修剪），
    点全部显示（参与=洋红紫 #C05AB0、被修剪=暗灰），法向箭头统一暗蓝 #1A3E78
    （沿网格抽稀 ~132 根，默认 200×21 → 步距 17×2 → 12×11；修剪信息由点色承载）。
    W 系图层：前端免 T→W 安装变换。
    """
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool), n=req.discretization.n)
        surf = compute_conjugate_surface(
            ctx.pts, ctx.plan, b_w=p.b_w, k_io=p.k_io,
            n_z=req.discretization.n_z, m=req.discretization.m,
            theta_range_deg=req.discretization.theta_range_deg, normals=ctx.norms,
            include_tooth_grid=True,
        )
        n = len(ctx.pts)
        n_z = req.discretization.n_z

        # 逐点色：参与=洋红紫 #C05AB0、被修剪（齿顶/齿根圆弧段、尖角邻点、伪根）=暗灰；
        # 法向箭头统一暗蓝 #1A3E78（与点色区分开，修剪信息不重复承载）
        magenta = (0xC0 / 255.0, 0x5A / 255.0, 0xB0 / 255.0)
        dim_gray = (0.45, 0.45, 0.45)
        dark_blue = (0x1A / 255.0, 0x3E / 255.0, 0x78 / 255.0)
        colors_pts: list[float] = []
        for flag in surf.tooth_participating:
            colors_pts += list(magenta) if flag else list(dim_gray)

        # 法向箭头（轴 + 头部 2 笔 chevron，4 顶点 3 线段/箭头）：沿网格两轴抽稀
        s_u = max(1, round(n / 12))
        s_z = max(1, round(n_z / 12))
        rs = [math.hypot(pt[0], pt[1]) for pt in ctx.pts]
        arrow_len = 0.2 * (max(rs) - min(rs))  # ≈ 0.2 齿高（与 conjugate.py r_lo/r_hi 同法）
        head_len = 0.35 * arrow_len
        cos_a = math.cos(math.radians(25.0))
        sin_a = math.sin(math.radians(25.0))
        arrow_pos: list[float] = []
        arrow_col: list[float] = []
        arrow_idx: list[int] = []
        n_arrows = 0
        for iz in range(0, n_z, s_z):
            for iu in range(0, n, s_u):
                i = iz * n + iu
                px = surf.tooth_positions[3 * i]
                py = surf.tooth_positions[3 * i + 1]
                pz = surf.tooth_positions[3 * i + 2]
                nx = surf.tooth_normals[3 * i]
                ny = surf.tooth_normals[3 * i + 1]
                nz = surf.tooth_normals[3 * i + 2]
                norm = math.sqrt(nx * nx + ny * ny + nz * nz)
                if norm < 1e-12:
                    continue  # 防御：退化法矢跳过
                nx, ny, nz = nx / norm, ny / norm, nz / norm
                # 垂直于 n̂ 的辅助方向 u（chevron 张角平面；取与坐标轴叉积）
                if abs(nx) < 0.9:
                    ux, uy, uz = 0.0, nz, -ny
                else:
                    ux, uy, uz = -nz, 0.0, nx
                ul = math.sqrt(ux * ux + uy * uy + uz * uz)
                ux, uy, uz = ux / ul, uy / ul, uz / ul
                # 轴 P→T + 头部两笔（从 T 向后张开 25°）
                tx = px + arrow_len * nx
                ty = py + arrow_len * ny
                tz = pz + arrow_len * nz
                bx = -cos_a * nx
                by = -cos_a * ny
                bz = -cos_a * nz
                h1 = (tx + head_len * (bx + sin_a * ux), ty + head_len * (by + sin_a * uy), tz + head_len * (bz + sin_a * uz))
                h2 = (tx + head_len * (bx - sin_a * ux), ty + head_len * (by - sin_a * uy), tz + head_len * (bz - sin_a * uz))
                arrow_pos += [px, py, pz, tx, ty, tz, *h1, *h2]
                arrow_col += list(dark_blue) * 4
                arrow_idx += [4 * n_arrows, 4 * n_arrows + 1, 4 * n_arrows + 1, 4 * n_arrows + 2, 4 * n_arrows + 1, 4 * n_arrows + 3]
                n_arrows += 1

        geos = [
            GeometrySpec(kind="points", positions=surf.tooth_positions, colors=colors_pts, layer_id="tooth_flank.pts"),
        ]
        if n_arrows > 0:
            geos.append(GeometrySpec(kind="lines", positions=arrow_pos, indices=arrow_idx, colors=arrow_col, layer_id="tooth_flank.normals"))
        glb = export_geometry_glb_base64(geos)
        return {
            "layer": {"id": "toothFlank", "glb_base64": glb},
            "coord_frame": "W",
            "coverage_report": surf.coverage,
            "grid": {"n": n, "n_z": n_z, "arrow_count": n_arrows},
            "install": {"a": ctx.plan.a, "sigma_deg": ctx.plan.sigma_deg},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


@router.post("/conjugate_gear")
def envelope_conjugate_gear(req: EnvelopeRequest) -> dict:
    """K-2.6 等效产形齿轮端点：单齿槽产形面阵列 z_t 份 + 齿顶/齿根回转面 → GLB（坐标 T）."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool), n=req.discretization.n)
        surf = compute_conjugate_gear(
            ctx.pts, ctx.plan, b_w=p.b_w, k_io=p.k_io, z_t=req.tool.z_t, z_w=p.z_w,
            n_z=req.discretization.n_z, m=req.discretization.m,
            theta_range_deg=req.discretization.theta_range_deg, normals=ctx.norms,
        )
        geo = GeometrySpec(
            kind="mesh", positions=surf.mesh_positions,
            indices=surf.mesh_indices, normals=surf.mesh_normals, colors=surf.mesh_colors,
            layer_id="conjugateGear",
        )
        glb = export_geometry_glb_base64([geo])
        return {
            "layer": {"id": "conjugateGear", "glb_base64": glb},
            "coord_frame": "T",
            "coverage_report": surf.coverage,
            "interference_stats": surf.interference_stats,
            "install": {"a": ctx.plan.a, "sigma_deg": ctx.plan.sigma_deg},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


# ── 子 PRD-3 前刀面端点 ─────────────────────────────────────────────


class RakeRequest(BaseModel):
    """前刀面请求体（rake 端点）."""

    workpiece: GearParamsRequest
    tool: ToolParams
    rake_type: str = Field("plane", description="前刀面形式（v1 仅 plane）")


@router.post("/rake")
def envelope_rake(req: RakeRequest) -> dict:
    """K-2.1 前刀面端点：γ₀/β_t/r_pt → 平面前刀面 + 法矢箭头 GLB."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    if req.rake_type != "plane":
        raise HTTPException(status_code=400, detail={"error": f"rake_type={req.rake_type} 未实现（v1 仅 plane）", "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool))
        geos = [plane_patch(ctx.rake), normal_arrow(ctx.rake)]
        glb = export_geometry_glb_base64(geos)
        return {
            "layer": {"id": "rake", "glb_base64": glb},
            "coord_frame": "T",
            "plane": {"A": ctx.rake.A, "B": ctx.rake.B, "C": ctx.rake.C, "const": ctx.rake.const},
            "p_ref": list(ctx.rake.p_ref),
            "n_rake": list(ctx.rake.n_rake),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


# ── 子 PRD-4 后刀面 + 单齿预览端点 ─────────────────────────────────


class ResharpenParams(BaseModel):
    """重磨参数（K-2.18 输入）.

    L 同时是刀齿轴向长度（后刀面螺旋扫掠总长 = 可重磨材料库存）：默认 20mm ≈
    工件齿宽量级——L 过小（旧默认 2mm）实体轴向厚仅 ~4mm vs 外径 90mm，呈薄片。
    """

    L: float = Field(20.0, gt=0, description="刀齿轴向长度（总重磨量）[mm]")
    n_L: int = Field(16, ge=1, description="等分数（后刀面扫掠截面数；间距过粗呈折面棱线）")


class HubParams(BaseModel):
    """B 方案 v6 齿根参数（模块③ K-3.1 预览级）."""

    root_offset_ratio: float = Field(
        0.05, gt=0, description="齿根径向偏置 / 分度圆直径（默认 1/20，用户选定）"
    )
    n_arc: int = Field(17, ge=3, description="谷底圆弧采样点数")
    n_ext: int = Field(4, ge=2, description="1/2 齿根延伸弦直线细分点数（每侧）")
    n_off: int = Field(4, ge=2, description="径向偏置直线采样点数")


class ToolBodyParamsRequest(BaseModel):
    """K-3.2 刀体结构参数（ADR-021 表驱动；None 字段 = 手册对档表自动带出）.

    mounting 用 str + 运行时枚举校验（非 pydantic Literal）——刻意取舍：非法值统一
    走业务 400 {error, code} 口径（与其他刀体硬校验一致、前端就地展示），不混入 422。
    """

    mounting: str = Field(
        "bore", description="装夹形式：bore 光内孔 / bore_keyway 内孔+端面键槽（法兰/带柄预留枚举位）"
    )
    d_bore: float | None = Field(None, gt=0, description="内孔直径 [mm]；None=对档默认（向下取档首值）")
    keyway_b: float | None = Field(None, gt=0, description="键槽宽 [mm]；None=随档×模数段带出（专家覆盖）")
    keyway_t1: float | None = Field(None, gt=0, description="键槽深 [mm]；None=GB/T 6132 最近档（W16）")
    B_body: float | None = Field(None, gt=0, description="刀体厚度 [mm]；None=档内 ≥L 最小标准值（非标软警）")


class FlankRequest(BaseModel):
    """后刀面/单齿请求体."""

    workpiece: GearParamsRequest
    tool: ToolParams
    resharpening: ResharpenParams = ResharpenParams()
    discretization: DiscretizationParams = DiscretizationParams()
    hub: HubParams = HubParams()
    tool_body: ToolBodyParamsRequest = ToolBodyParamsRequest()
    tool_type: str = Field("cylindrical", description="刀型：cylindrical 圆柱 / conical 圆锥（圆锥二期）")
    flank_method: str = Field("helical_lead", description="后刀面算法：helical_lead 螺旋导程法 / axial_offset 轴向偏移法（二期）")


@router.post("/flank")
def envelope_flank(req: FlankRequest) -> dict:
    """K-2.18/2.19 后刀面端点：闭合轮廓螺旋扫掠 ribbon（B 方案 v2，用户指定同轮廓）."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool), n=req.discretization.n)
        if req.tool_type == "cylindrical" and req.flank_method == "helical_lead":
            solid = build_single_tooth_solid(
                ctx.pts, ctx.plan, ctx.rake, r_a=p.tip_radius(),
                beta_t_deg=req.tool.beta_t_deg, z_t=req.tool.z_t, m_n=p.m_n,
                L=req.resharpening.L, n_L=req.resharpening.n_L,
                root_offset_ratio=req.hub.root_offset_ratio,
                n_arc=req.hub.n_arc, n_ext=req.hub.n_ext, n_off=req.hub.n_off,
                m=req.discretization.m, r_f=p.root_radius(),
                theta_range_deg=req.discretization.theta_range_deg, normals=ctx.norms,
                b_w=p.b_w, n_z=req.discretization.n_z,  # 斜齿数值求交链（K-2.8b）
            )
            # 导程单一权威源（tooth_solid.helical_lead_mm，与整环错位共用）；
            # β_t=0 → Ltp→∞（纯轴向扫掠）：JSON 不可序列化 inf，回 null
            _lead = helical_lead_mm(p.m_n, req.tool.z_t, req.tool.beta_t_deg)
            lead_pitch = None if math.isinf(_lead) else _lead
            source = "螺旋导程法（K-2.15/16，闭合轮廓 ribbon，B 方案 v2）"
        else:
            raise ValueError(
                f"tool_type={req.tool_type}/flank_method={req.flank_method} 未实现"
                "（圆锥刀变位系数族法 K-2.14 / 轴向偏移法 K-2.17 二期）"
            )
        geo = GeometrySpec(
            kind="mesh", positions=solid.mesh_positions,
            indices=solid.ribbon_indices, layer_id="flank",
        )
        geo.normals = compute_vertex_normals(solid.mesh_positions, solid.ribbon_indices)
        glb = export_geometry_glb_base64([geo])
        return {
            "layer": {"id": "flank", "glb_base64": glb},
            "coord_frame": "T",
            "source": source,
            "flank_method": req.flank_method,
            "lead_pitch": lead_pitch,
            "resharpen_schedule": [
                {"i": i + 1, "dL": req.resharpening.L * (i + 1) / req.resharpening.n_L,
                 "da": 0.0, "a_i": ctx.plan.a}
                for i in range(req.resharpening.n_L)
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


@router.post("/single_tooth")
def envelope_single_tooth(req: FlankRequest) -> dict:
    """K-3.1 单齿预览端点（B 方案 v2）：开放轮廓 + 偏置 + 圆弧闭合实体 GLB + 元数据."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool), n=req.discretization.n)
        if req.tool_type == "cylindrical" and req.flank_method == "helical_lead":
            geos, meta = build_single_tooth(
                ctx.pts, ctx.plan, r_a=p.tip_radius(), r_f=p.root_radius(),
                gamma_0_deg=req.tool.gamma_0_deg, beta_t_deg=req.tool.beta_t_deg,
                z_t=req.tool.z_t, m_n=p.m_n, L=req.resharpening.L, n_L=req.resharpening.n_L,
                k_io=p.k_io, root_offset_ratio=req.hub.root_offset_ratio,
                n_arc=req.hub.n_arc, n_ext=req.hub.n_ext, n_off=req.hub.n_off,
                m=req.discretization.m,
                theta_range_deg=req.discretization.theta_range_deg, normals=ctx.norms,
                b_w=p.b_w, n_z=req.discretization.n_z,  # 斜齿数值求交链（K-2.8b）
            )
        else:
            raise ValueError(
                f"tool_type={req.tool_type}/flank_method={req.flank_method} 未实现"
                "（圆锥刀变位系数族法 K-2.14 / 轴向偏移法 K-2.17 二期）"
            )
        glb = export_geometry_glb_base64(geos)
        return {
            "layer": {"id": "singleTooth", "glb_base64": glb},
            "coord_frame": "T",
            "source": "模块③ B 方案 v8（开放轮廓 + 圆柱求差底弧实体）",
            "meta": meta,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


@router.post("/tool_ring")
def envelope_tool_ring(req: FlankRequest) -> dict:
    """K-3.1+K-3.2 整环刀具端点（B 方案 v2）：齿圈周向阵列 + 刀体，一次管线两几何.

    齿圈：单齿实体绕 Z **同相位周向阵列** z_t 份，无轴向错位（2026-08-27 勘误：
    #34 的逐齿 ΔZ=i·p_z·j_t 实测证伪已回退，缘由见 build_tool_ring docstring）。
    刀体（K-3.2，ADR-021）：外缘=谷底圆柱（派生只读），表驱动缺省 = bore 光内孔
    + 对档默认孔径 + 档内 ≥L 最小标准厚度；硬校验失败（孔缘含键槽底越谷底圆、
    B<L、非系列孔径）→ 400。预览级三角网伪实体（正式级 OCCT 布尔/STEP 挂账，
    body_description 即 CAD-neutral 描述包，原样重建零信息丢失）。
    """
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool), n=req.discretization.n)
        if req.tool_type == "cylindrical" and req.flank_method == "helical_lead":
            solid = build_single_tooth_solid(
                ctx.pts, ctx.plan, ctx.rake, r_a=p.tip_radius(),
                beta_t_deg=req.tool.beta_t_deg, z_t=req.tool.z_t, m_n=p.m_n,
                L=req.resharpening.L, n_L=req.resharpening.n_L,
                root_offset_ratio=req.hub.root_offset_ratio,
                n_arc=req.hub.n_arc, n_ext=req.hub.n_ext, n_off=req.hub.n_off,
                m=req.discretization.m, r_f=p.root_radius(),
                theta_range_deg=req.discretization.theta_range_deg, normals=ctx.norms,
                b_w=p.b_w, n_z=req.discretization.n_z,  # 斜齿数值求交链（K-2.8b）
            )
            geo = build_tool_ring(solid, z_t=req.tool.z_t)
        else:
            raise ValueError(
                f"tool_type={req.tool_type}/flank_method={req.flank_method} 未实现"
                "（圆锥刀变位系数族法 K-2.14 / 轴向偏移法 K-2.17 二期）"
            )
        # K-3.2 刀体（v4 圆柱基体）：外径 = 求差圆 r_limit（与齿圈内圆求差的同一圆柱，
        # 干涉物理上限）；校验在 GLB 导出前 → 原子（无半响应）
        r_cut = solid.loop.root_radius  # v8 求差后 root_radius = r_limit
        resolved = resolve_tool_body_params(
            mounting=req.tool_body.mounting, d_pt=2.0 * ctx.plan.r_pt, m_n=p.m_n,
            L=req.resharpening.L, r_cut=r_cut,
            d_bore=req.tool_body.d_bore, keyway_b=req.tool_body.keyway_b,
            keyway_t1=req.tool_body.keyway_t1, B=req.tool_body.B_body,
        )
        body_geo, body_desc = build_tool_body(
            ctx.rake, r_cut=r_cut, resolved=resolved,
            theta_c=solid.loop.theta_c,  # 前端面取基准窗口相位中心
        )
        glb = export_geometry_glb_base64([geo])
        body_glb = export_geometry_glb_base64([body_geo])
        return {
            "layer": {"id": "toolRing", "glb_base64": glb},
            "body_layer": {"id": "toolBody", "glb_base64": body_glb},
            "body_description": body_desc,
            "coord_frame": "T",
            "source": "模块③ B 方案 v2（整环阵列，齿距线相位闭合）",
            "meta": {
                "r_limit_mm": solid.loop.r_limit,
                "root_radius_mm": solid.loop.root_radius,
                "root_offset_mm": solid.loop.offset_mm,
                "arch_spread_deg": solid.loop.arch_spread_deg,
                "pitch_z_mm": solid.loop.pitch_z_mm,
                "loop_points": solid.n_loop,
                "n_sections": solid.n_sections,
                "volume_mm3": solid.volume_mm3,
                "z_t": req.tool.z_t,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


# ── 子 PRD-5 解析路线端点 ─────────────────────────────────────────────


@router.post("/analytic")
def envelope_analytic(req: EnvelopeRequest) -> dict:
    """K-2.8 解析刃形端点 + 双路线互检：逐点二分 h(φ)=0（产形面 ∩ 前刀面消元）→ 解析刃形 GLB."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        ctx = assemble_envelope_context(p, _tool_spec(req.tool), n=req.discretization.n)
        edge_pts = compute_analytic_edge(ctx.pts, ctx.plan, ctx.rake, theta_range_deg=req.discretization.theta_range_deg, normals=ctx.norms)
        if not edge_pts:
            raise ValueError("刃形为空（外齿轮前刀面符号 T14 未销项）：请使用内齿轮（k_io=−1）")
        # 双路线互检：解析（二分精化）vs 离散（扫掠采样），同一工件
        discrete_edge = extract_edge(
            ctx.pts, ctx.plan, ctx.rake, m=req.discretization.m,
            theta_range_deg=req.discretization.theta_range_deg, k_io=p.k_io, normals=ctx.norms,
        )
        discrete_pts = [pt for seg in discrete_edge.segments for pt in seg.pts]
        cross = cross_check(edge_pts, discrete_pts)
        geos = [GeometrySpec(kind="line", positions=[c for pt in edge_pts for c in pt], layer_id="edge")]
        glb = export_geometry_glb_base64(geos)
        return {
            "layer": {"id": "edge", "glb_base64": glb},
            "coord_frame": "T",
            "source": "解析（K-2.8）",
            "point_count": len(edge_pts),
            "cross_check": cross,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})

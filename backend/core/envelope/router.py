"""模块② 包络计算路由.

子 PRD-1 交付占位演示端点（demo）；子 PRD-2 交付真实离散包络
swept_cloud（扫掠点云 K-2.9）/ edge（刃形 K-2.11~2.13）端点。
"""

import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.common.gltf_export import GeometrySpec, export_geometry_glb_base64
from core.envelope.edge import extract_edge
from core.envelope.swept_cloud import WIREFRAME_COLOR, extract_gap_points, generate_envelope_cloud
from core.envelope.process_plan import compute_process_plan
from core.envelope.rake import build_plane_rake, normal_arrow, plane_patch
from core.workpiece.router import GearParamsRequest

router = APIRouter(prefix="/api/envelope", tags=["envelope"])


def _demo_geometries() -> list[GeometrySpec]:
    """占位假图层（与真实包络几何同构，仅形状为占位；GLB 坐标为刀具动系 T，Z 轴为轴向）."""
    # 扫掠点云占位：一片半透明品牌蓝（x-z 平面展开）
    swept_cloud = GeometrySpec(
        kind="mesh",
        positions=[
            -15.0, 0.0, -15.0,
            15.0, 0.0, -15.0,
            15.0, 0.0, 15.0,
            -15.0, 0.0, 15.0,
        ],
        indices=[0, 1, 2, 0, 2, 3],
        normals=[0.0, 1.0, 0.0] * 4,
        layer_id="swept_cloud",
    )
    # 前刀面占位：一片半透明琥珀橙（扫掠点云上方）
    rake = GeometrySpec(
        kind="mesh",
        positions=[
            -10.0, 1.0, -10.0,
            10.0, 1.0, -10.0,
            10.0, 1.0, 10.0,
            -10.0, 1.0, 10.0,
        ],
        indices=[0, 1, 2, 0, 2, 3],
        normals=[0.0, 1.0, 0.0] * 4,
        layer_id="rake",
    )
    # 刃形占位：一条折线（珊瑚红高亮）
    edge = GeometrySpec(
        kind="line",
        positions=[
            -15.0, 0.5, -15.0,
            -5.0, 0.5, -8.0,
            5.0, 0.5, 3.0,
            15.0, 0.5, 12.0,
        ],
        layer_id="edge",
    )
    # 后刀面占位：一片半透明翡翠绿（扫掠点云下方）
    flank = GeometrySpec(
        kind="mesh",
        positions=[
            -12.0, -1.0, -12.0,
            12.0, -1.0, -12.0,
            12.0, -1.0, 12.0,
            -12.0, -1.0, 12.0,
        ],
        indices=[0, 1, 2, 0, 2, 3],
        normals=[0.0, 1.0, 0.0] * 4,
        layer_id="flank",
    )
    return [swept_cloud, rake, edge, flank]


@router.post("/demo")
def envelope_demo() -> dict:
    """返回占位假图层的 GLB（扫掠点云/刃形/后刀面），供前端多图层能力演示."""
    layers = [
        {"id": geo.layer_id, "glb_base64": export_geometry_glb_base64([geo])}
        for geo in _demo_geometries()
    ]
    return {"layers": layers}


# ── 子 PRD-2 离散包络端点 ─────────────────────────────────────────────


class ToolParams(BaseModel):
    """刀具参数（组B 子集）— swept_cloud / edge 共用."""

    z_t: int = Field(..., ge=1, description="刀具齿数")
    beta_t_deg: float = Field(..., ge=0.0, description="刀具螺旋角 [°]")
    j_t: int = Field(1, description="刀具旋向 +1/−1")
    gamma_0_deg: float = Field(5.0, description="设计前角 [°]（保留位，MVP 忽略）")
    alpha_0_deg: float = Field(8.0, description="后角 [°]（保留位，MVP 忽略）")


class DiscretizationParams(BaseModel):
    """离散参数（后端默认，可覆盖）."""

    n: int = Field(200, ge=2)
    m: int = Field(181, ge=2)
    NR: int = Field(200, ge=2)
    theta_range_deg: float = Field(20.0, gt=0)


class EnvelopeRequest(BaseModel):
    """离散包络请求体（swept_cloud / edge 共用）."""

    workpiece: GearParamsRequest
    tool: ToolParams
    discretization: DiscretizationParams = DiscretizationParams()


@router.post("/swept_cloud")
def envelope_swept_cloud(req: EnvelopeRequest) -> dict:
    """K-2.9 扫掠点云端点：工件齿槽点云经运动包络 → 多 primitive GLB（面+点+线框）+ motion 元数据."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        plan = compute_process_plan(
            z_w=p.z_w, z_t=req.tool.z_t, m_n=p.m_n,
            beta_w_deg=p.beta_w_deg, beta_t_deg=req.tool.beta_t_deg,
            j_w=p.j_w, j_t=req.tool.j_t, k_io=p.k_io,
        )
        pts = extract_gap_points(p, req.discretization.n)
        cloud = generate_envelope_cloud(
            pts, plan, m=req.discretization.m,
            theta_range_deg=req.discretization.theta_range_deg,
        )
        n = len(pts)
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
            "install": {"a": plan.a, "sigma_deg": plan.sigma_deg},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})


@router.post("/edge")
def envelope_edge(req: EnvelopeRequest) -> dict:
    """K-2.11~2.13 刃形端点：点云投影 → 内边界提取 → 覆盖 + ffα → 刃形 GLB."""
    try:
        p = req.workpiece.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    try:
        plan = compute_process_plan(
            z_w=p.z_w, z_t=req.tool.z_t, m_n=p.m_n,
            beta_w_deg=p.beta_w_deg, beta_t_deg=req.tool.beta_t_deg,
            j_w=p.j_w, j_t=req.tool.j_t, k_io=p.k_io,
        )
        pts = extract_gap_points(p, req.discretization.n)
        cloud = generate_envelope_cloud(
            pts, plan, m=req.discretization.m,
            theta_range_deg=req.discretization.theta_range_deg,
        )
        edge = extract_edge(cloud.cloud, pts, plan, NR=req.discretization.NR)

        # 每个刃形段 → 一个 LINE_STRIP GeometrySpec
        geos = [
            GeometrySpec(
                kind="line",
                positions=[c for pt in seg.pts for c in pt],
                layer_id="edge",
            )
            for seg in edge.segments
        ]
        glb = export_geometry_glb_base64(geos) if geos else ""

        return {
            "layer": {"id": "edge", "glb_base64": glb},
            "coord_frame": "T",
            "coverage_report": edge.coverage_report,
            "ffa_um": edge.ffa_um,
            "segments_meta": [
                {"count": len(seg.pts), "continuity": seg.continuity}
                for seg in edge.segments
            ],
            "install": {"a": plan.a, "sigma_deg": plan.sigma_deg},
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
        plan = compute_process_plan(
            z_w=p.z_w, z_t=req.tool.z_t, m_n=p.m_n,
            beta_w_deg=p.beta_w_deg, beta_t_deg=req.tool.beta_t_deg,
            j_w=p.j_w, j_t=req.tool.j_t, k_io=p.k_io,
        )
        surf = build_plane_rake(req.tool.gamma_0_deg, req.tool.beta_t_deg, plan.r_pt)
        geos = [plane_patch(surf), normal_arrow(surf)]
        glb = export_geometry_glb_base64(geos)
        return {
            "layer": {"id": "rake", "glb_base64": glb},
            "coord_frame": "T",
            "plane": {"A": surf.A, "B": surf.B, "C": surf.C, "const": surf.const},
            "p_ref": list(surf.p_ref),
            "n_rake": list(surf.n_rake),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})

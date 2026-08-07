"""Module ① OCCT 齿轮构建器 — 设计书 §4.1.

依赖: pythonocc-core (OCP), numpy.

构建管线:
  GearParams → profile.py (单一权威齿廓)
           → OCCT wire → face → Prism/ThruSections 3D 实体
           → GearModel (solid + 渲染用 faces/wires)

GearModel 是项目唯一的齿轮几何表示。exporter 只消费 GearModel, 不自行构建几何。
"""

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_Transform,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GC import GC_MakeArcOfCircle
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp  # type: ignore[import-untyped]
from OCP.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Wire  # type: ignore[import-untyped]
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID  # type: ignore[import-untyped]
from OCP.TopLoc import TopLoc_Location
from OCP.gp import (
    gp_Ax1,
    gp_Ax2,
    gp_Circ,
    gp_Dir,
    gp_Pnt,
    gp_Trsf,
    gp_Vec,
    gp,
)

from core.workpiece.models import GearParams
from core.workpiece.profile import (
    Arc,
    Polyline,
    gear_profile_segments,
    single_tooth_segments,
)


@dataclass
class GearModel:
    """唯一的齿轮几何表示 — builder 产出, exporter 消费.

    solid: OCCT 实体 (权威 CAD 模型)
    cap_face: 端面 Face (原生 TopoDS_Face, 可直接传给 Triangulation_s)
    boundary_wire: 齿圈外廓 Wire (2D, 在 XY 平面)
    b_w: 齿宽 [mm]
    z_w: 齿数 [用于斜齿轮单齿 mesh 阵列]
    helical_sections: 斜齿轮截面参数 [(z, theta_rad), ...]; None 表示直齿轮
    """

    solid: TopoDS_Shape
    cap_face: TopoDS_Face
    boundary_wire: TopoDS_Wire
    b_w: float
    z_w: int = 0
    helical_sections: Optional[list[tuple[float, float]]] = None


def _add_segments_to_wire(wire_builder, segments, z: float = 0.0) -> None:
    """profile 段 → OCCT edge 的统一映射."""
    for seg in segments:
        if isinstance(seg, Polyline):
            for a, b in zip(seg.points, seg.points[1:]):
                wire_builder.Add(BRepBuilderAPI_MakeEdge(
                    gp_Pnt(a[0], a[1], z), gp_Pnt(b[0], b[1], z)).Edge())
        else:
            circ = gp_Circ(
                gp_Ax2(gp_Pnt(seg.center[0], seg.center[1], z), gp_Dir(0, 0, 1)),
                seg.radius,
            )
            if seg.clockwise:
                arc = GC_MakeArcOfCircle(circ, seg.a1, seg.a0, True)
            else:
                arc = GC_MakeArcOfCircle(circ, seg.a0, seg.a1, True)
            if arc.IsDone():
                wire_builder.Add(BRepBuilderAPI_MakeEdge(arc.Value()).Edge())


def build_full_tooth_wire(
    p: GearParams, n_involute: int = 80, theta_offset: float = 0.0, z: float = 0.0,
) -> TopoDS_Wire:
    """构建完整单齿廓形 wire — 供斜齿轮 ThruSections 截面使用."""
    wire_builder = BRepBuilderAPI_MakeWire()
    _add_segments_to_wire(
        wire_builder,
        single_tooth_segments(p, n_involute, theta_offset),
        z,
    )
    if not wire_builder.IsDone():
        raise RuntimeError("完整齿廓 wire 构建失败")
    wire = wire_builder.Wire()
    if not wire.Closed():
        raise RuntimeError("完整齿廓 wire 不闭合")
    return wire


def _build_full_gear_2d_wire(p: GearParams, n_involute: int = 80) -> TopoDS_Wire:
    """构建完整齿圈 2D 廓形 — 所有 z_w 个齿用一个闭合 wire."""
    wire_builder = BRepBuilderAPI_MakeWire()
    _add_segments_to_wire(wire_builder, gear_profile_segments(p, n_involute))
    if not wire_builder.IsDone():
        raise RuntimeError("全齿圈 2D wire 构建失败")
    wire = wire_builder.Wire()
    if not wire.Closed():
        raise RuntimeError("全齿圈 2D wire 不闭合")
    return wire


# ═══════════════════════════════════════════════════════════════════════
# 唯一公开入口
# ═══════════════════════════════════════════════════════════════════════

def build_gear_model(p: GearParams, n_slices: int = 6) -> GearModel:
    """构建齿轮的 OCCT 实体 + 渲染用几何信息.

    这是模块① 的唯一公开入口。返回的 GearModel 包含:
      - solid: OCCT 实体 (STEP 导出/分析用)
      - cap_face: 端面 Face (exporter 用 Triangulation_s 提取三角形)
      - boundary_wire: 齿圈外廓 (exporter 用边界点构建侧壁)
      - helical_sections: 斜齿轮各截面 (z, theta) 参数

    Args:
        p: 工件齿轮参数
        n_slices: 斜齿轮 Z 向截面数 (直齿轮忽略)

    Returns:
        GearModel
    """
    if abs(p.beta_w_deg) < 1e-9:
        return _build_spur_model(p)
    else:
        return _build_helical_model(p, n_slices)


def _build_spur_model(p: GearParams) -> GearModel:
    """直齿轮: 全齿圈 2D wire → face → Prism."""
    full_wire = _build_full_gear_2d_wire(p)
    cap_face = BRepBuilderAPI_MakeFace(full_wire).Face()
    prism_vec = gp_Vec(0.0, 0.0, p.b_w)
    solid = BRepPrimAPI_MakePrism(cap_face, prism_vec, True).Shape()
    return GearModel(
        solid=solid,
        cap_face=cap_face,
        boundary_wire=full_wire,
        b_w=p.b_w,
    )


def _build_helical_model(p: GearParams, n_slices: int) -> GearModel:
    """斜齿轮: ThruSections 单齿 → 阵列 → fuse."""
    z_w = p.z_w
    pitch_angle = 2.0 * math.pi / z_w
    b_w = p.b_w
    beta_w = math.radians(p.beta_w_deg)
    j_w = p.j_w
    r_pw = p.pitch_radius()

    # 各截面 wire (原生构建, 无需 downcast)
    section_wires: list[TopoDS_Wire] = []
    sections: list[tuple[float, float]] = []
    for i_slice in range(n_slices + 1):
        z_val = b_w * i_slice / n_slices
        theta = j_w * z_val * math.tan(beta_w) / r_pw
        w = build_full_tooth_wire(p, theta_offset=theta, z=z_val)
        section_wires.append(w)
        sections.append((z_val, theta))

    # ThruSections
    thru = BRepOffsetAPI_ThruSections(False, False, 1e-6)
    for w in section_wires:
        thru.AddWire(w)
    thru.Build()
    if not thru.IsDone():
        raise RuntimeError("ThruSections 放样失败")
    single_tooth = thru.Shape()

    # 阵列 — Compound 替代 Boolean fuse (O(n²) → O(1), 瞬时)
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    compound = TopoDS_Compound()
    builder_comp = BRep_Builder()
    builder_comp.MakeCompound(compound)
    builder_comp.Add(compound, single_tooth)
    for i in range(1, z_w):
        trsf = gp_Trsf()
        trsf.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), pitch_angle * i)
        rotated = BRepBuilderAPI_Transform(single_tooth, trsf, True).Shape()
        builder_comp.Add(compound, rotated)

    # cap_face: 端面单齿 face (θ=0) — 阵列后可得全齿轮廓
    cap_wire = build_full_tooth_wire(p, theta_offset=0.0, z=0.0)
    cap_face = BRepBuilderAPI_MakeFace(cap_wire).Face()

    # boundary_wire: 全齿轮廓 (θ=0, z=0) — 侧壁参考
    boundary_wire = _build_full_gear_2d_wire(p)

    return GearModel(
        solid=compound,
        cap_face=cap_face,
        boundary_wire=boundary_wire,
        b_w=b_w,
        z_w=z_w,
        helical_sections=sections,
    )


# ═══════════════════════════════════════════════════════════════════════
# 向后兼容 + 辅助函数
# ═══════════════════════════════════════════════════════════════════════

def build_gear(p: GearParams, n_slices: int = 6) -> TopoDS_Shape:
    """向后兼容: 直接返回 solid."""
    return build_gear_model(p, n_slices).solid


def compute_bounding_box_diameter(shape: TopoDS_Shape) -> float:
    """从形状估算齿顶圆直径."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    try:
        BRepGProp.VolumeProperties_s(shape, props)
        bbox = props.BoundingBox()
        if not bbox.IsVoid():
            cmin, cmax = bbox.CornerMin(), bbox.CornerMax()
            dx = cmax.X() - cmin.X()
            dy = cmax.Y() - cmin.Y()
            if dx > 0 and dy > 0:
                return math.sqrt(dx * dx + dy * dy)
    except Exception:
        pass

    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.BRep import BRep_Tool

    max_r = 0.0
    explorer = TopExp_Explorer(shape, TopAbs_VERTEX, TopAbs_VERTEX)
    while explorer.More():
        try:
            p = BRep_Tool.Pnt_s(explorer.Current())  # type: ignore[call-arg]
            r = math.sqrt(p.X() ** 2 + p.Y() ** 2)
            if r > max_r:
                max_r = r
        except Exception:
            pass
        explorer.Next()
    return 2.0 * max_r


def compute_min_radial_distance(shape: TopoDS_Shape) -> float:
    """计算形状到 Z 轴的最小径向距离 (近似齿根圆)."""
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.BRep import BRep_Tool

    min_r = float("inf")
    explorer = TopExp_Explorer(shape, TopAbs_VERTEX, TopAbs_VERTEX)
    while explorer.More():
        v = explorer.Current()
        p = BRep_Tool.Pnt(v)
        r = math.sqrt(p.X() ** 2 + p.Y() ** 2)
        if r > 0.001 and r < min_r:
            min_r = r
        explorer.Next()
    return min_r


def count_teeth_from_shape(shape: TopoDS_Shape) -> int:
    """从形状估算齿数 (基于面片数)."""
    n_faces = 0
    explorer = TopExp_Explorer(shape, TopAbs_FACE, TopAbs_FACE)
    while explorer.More():
        n_faces += 1
        explorer.Next()
    return n_faces // 7

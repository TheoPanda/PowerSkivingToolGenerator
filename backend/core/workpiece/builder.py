"""Module ① OCCT 齿轮构建器 — 设计书 §4.1 K-1.12, K-1.13, K-1.11.

依赖: pythonocc-core (OCP), numpy.

构建管线:
  GearParams → K-1.2/K-1.1 端面齿廓 (纯数学)
           → K-1.12 齿根圆角 (OCCT 2D)
           → K-1.13 半周期 + 镜像 + 阵列 (OCCT)
           → ThruSections/Prism 3D 实体 (OCCT)
           → TopoDS_Solid
"""

import math
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
from OCP.TopoDS import TopoDS_Shape, TopoDS_Wire  # type: ignore[import-untyped]
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

from core.workpiece.models import GearParams, involute_point, involute_radius, xi_at_radius


# ═══════════════════════════════════════════════════════════════════════
# K-1.12 齿根圆角
# ═══════════════════════════════════════════════════════════════════════

def compute_fillet_center(
    r_root: float,
    r_b: float,
    r_fillet: float,
    involute_start_angle: float,
    n_search: int = 200,
) -> tuple[float, float]:
    """K-1.12: 一维数值搜索求圆角圆心 (与齿根圆+渐开线双切).

    沿渐开线扫描，对每个渐开线点 P(ξ):
      - 法向 n = (−sin ξ, cos ξ)  (渐开线法向，指向外侧)
      - 候选圆心 C = P + r_fillet · n
      - 检验: |C| − (r_root + r_fillet) ≈ 0

    Args:
        r_root: 齿根圆半径 [mm]
        r_b: 基圆半径 [mm]
        r_fillet: 圆角半径 ρ_f = ρ*_f·m_n [mm]
        involute_start_angle: 渐开线起始角度 (用于初始猜测)
        n_search: 搜索采样数

    Returns:
        (cx, cy) 圆角圆心坐标 [mm]
    """
    # 渐开线起始点: 从基圆开始
    xi_start = 0.0

    # 渐开线终点: 到达齿根圆 + 圆角半径的距离
    r_max_search = r_root + 3.0 * r_fillet
    xi_end = xi_at_radius(r_b, min(r_max_search, r_b * 1.5))

    best_xi = xi_start
    best_err = float("inf")

    for i in range(n_search + 1):
        xi = xi_start + (xi_end - xi_start) * i / n_search
        px, py = involute_point(r_b, xi)

        # 渐开线法向 (指向外侧，即远离齿轮中心的方向)
        cos_xi = math.cos(xi)
        sin_xi = math.sin(xi)
        nx = -sin_xi
        ny = cos_xi

        # 候选圆心
        cx = px + r_fillet * nx
        cy = py + r_fillet * ny

        # 到齿轮中心的距离
        r_center = math.sqrt(cx * cx + cy * cy)

        # 目标: 圆心应在齿根圆 + 圆角半径的圆上
        target = r_root + r_fillet
        err = abs(r_center - target)

        if err < best_err:
            best_err = err
            best_xi = xi

    # 在最佳点附近做更精细搜索
    xi_lo = max(0.0, best_xi - (xi_end - xi_start) / n_search * 2)
    xi_hi = xi_end
    for i in range(n_search):
        xi = xi_lo + (xi_hi - xi_lo) * i / n_search
        px, py = involute_point(r_b, xi)
        cos_xi = math.cos(xi)
        sin_xi = math.sin(xi)
        nx = -sin_xi
        ny = cos_xi

        cx = px + r_fillet * nx
        cy = py + r_fillet * ny
        r_center = math.sqrt(cx * cx + cy * cy)
        err = abs(r_center - (r_root + r_fillet))

        if err < best_err:
            best_err = err
            best_xi = xi

    # 最终圆心
    px, py = involute_point(r_b, best_xi)
    cos_xi = math.cos(best_xi)
    sin_xi = math.sin(best_xi)
    cx = px + r_fillet * (-sin_xi)
    cy = py + r_fillet * cos_xi

    return (cx, cy)


# ═══════════════════════════════════════════════════════════════════════
# 2D 齿廓构建
# ═══════════════════════════════════════════════════════════════════════

def build_half_period_wire(
    p: GearParams,
    n_involute: int = 80,
) -> TopoDS_Wire:
    """K-1.13 / U13: 构建半周期齿廓 wire (XY 平面).

    半周期 = 从齿槽中心线到齿中心线:
      - 齿根圆弧 (齿槽侧): 从齿槽中心线到圆角起点
      - 齿根圆角弧 (K-1.12): 双切于齿根圆和渐开线
      - 渐开线齿面: 从圆角终点到齿顶圆
      - 齿顶圆弧: 从渐开线终点到齿中心线

    坐标约定 (U13):
      - 齿中心线在 +X 轴 (θ=0)
      - 齿槽中心线在 θ = π/z_w
      - 点集从齿槽中心线走向齿中心线

    Args:
        p: 工件齿轮参数
        n_involute: 渐开线采样点数

    Returns:
        TopoDS_Wire: 半周期闭合廓形 (XY 平面)
    """
    m_t, alpha_t_deg = p.to_transverse()
    alpha_t = math.radians(alpha_t_deg)

    r_a = p.tip_radius()       # 齿顶圆半径
    r_f = p.root_radius()      # 齿根圆半径
    r_pw = p.pitch_radius()    # 节圆半径
    r_b = p.base_radius()      # 基圆半径
    rho_f = p.rho_f * p.m_n    # 圆角半径

    z_w = p.z_w
    pitch_angle = 2.0 * math.pi / z_w  # 齿距角

    # 端面齿厚 (在节圆上)
    s_t = compute_tooth_thickness(p)
    half_tooth_angle = s_t / (2.0 * r_pw)  # 齿厚半角

    # 齿槽中心线角度 (U13: 齿槽中心线在 +π/z_w)
    slot_center_angle = pitch_angle / 2.0 + half_tooth_angle

    # 齿中心线在 θ=0 (U13)
    tooth_center_angle = 0.0

    wire_builder = BRepBuilderAPI_MakeWire()

    # ── 齿根圆弧 (从齿槽中心线向渐开线方向) ──
    # 齿根圆在 r_f 处
    # 如果 r_b > r_f: 渐开线从基圆开始，需要圆角连接
    # 如果 r_b <= r_f: 渐开线从齿根圆开始，不需要圆角
    involute_start_radius = max(r_b, r_f)

    # 圆角终点在渐开线上
    xi_fillet_end = xi_at_radius(r_b, involute_start_radius)

    if r_b > r_f:
        # 需要圆角 (K-1.12)
        fillet_center = compute_fillet_center(r_f, r_b, rho_f, 0.0)

        # 圆角与齿根圆的切点
        fc_x, fc_y = fillet_center
        tangency_angle_root = math.atan2(fc_y, fc_x)
        # 切点在圆心连线上，从圆角圆心指向齿轮中心方向
        r_center = math.sqrt(fc_x * fc_x + fc_y * fc_y)
        dir_to_center_x = -fc_x / r_center
        dir_to_center_y = -fc_y / r_center
        tangency_root_x = fc_x + rho_f * dir_to_center_x
        tangency_root_y = fc_y + rho_f * dir_to_center_y
        tangency_root_angle = math.atan2(tangency_root_y, tangency_root_x)

        # 齿根圆弧: 从齿槽中心线到圆角-齿根切点
        # 确保圆弧方向正确 (从齿槽中心向齿中心方向，即顺时针)
        root_arc = GC_MakeArcOfCircle(
            gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_f),
            slot_center_angle,
            tangency_root_angle,
            True,  # Sense = clockwise (from slot to tooth)
        )
        if root_arc.IsDone():
            edge_root = BRepBuilderAPI_MakeEdge(root_arc.Value()).Edge()
            wire_builder.Add(edge_root)

        # 圆角弧: 从齿根切点到渐开线切点
        # 圆角圆心到渐开线切点的方向 = 渐开线法向 (指向内侧)
        px, py = involute_point(r_b, xi_fillet_end)
        cos_xi_f = math.cos(xi_fillet_end)
        sin_xi_f = math.sin(xi_fillet_end)
        # 法向指向外侧: (-sin ξ, cos ξ)
        # 从圆心到渐开线切点: 沿外法向
        tangency_inv_x = fc_x + rho_f * (-sin_xi_f)
        tangency_inv_y = fc_y + rho_f * cos_xi_f

        # 在有圆角的情况下,圆角弧连接两个切点
        angle_root = math.atan2(tangency_root_y - fc_y, tangency_root_x - fc_x)
        angle_inv = math.atan2(tangency_inv_y - fc_y, tangency_inv_x - fc_x)

        fillet_arc = GC_MakeArcOfCircle(
            gp_Circ(gp_Ax2(gp_Pnt(fc_x, fc_y, 0), gp_Dir(0, 0, 1)), rho_f),
            angle_root,
            angle_inv,
            True,
        )
        if fillet_arc.IsDone():
            edge_fillet = BRepBuilderAPI_MakeEdge(fillet_arc.Value()).Edge()
            wire_builder.Add(edge_fillet)
    else:
        # 不需要圆角: 渐开线直达齿根圆
        xi_fillet_end = xi_at_radius(r_b, r_f)

        # 齿根圆弧: 从齿槽中心线到渐开线起点
        inv_start_pt = involute_point(r_b, xi_fillet_end)
        inv_start_angle = math.atan2(inv_start_pt[1], inv_start_pt[0])

        root_arc = GC_MakeArcOfCircle(
            gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_f),
            slot_center_angle,
            inv_start_angle,
            True,
        )
        if root_arc.IsDone():
            edge_root = BRepBuilderAPI_MakeEdge(root_arc.Value()).Edge()
            wire_builder.Add(edge_root)

    # ── 渐开线齿面 ──
    xi_end = xi_at_radius(r_b, r_a)
    inv_points: list[tuple[float, float]] = []
    for i in range(n_involute + 1):
        xi = xi_fillet_end + (xi_end - xi_fillet_end) * i / n_involute
        px, py = involute_point(r_b, xi)
        inv_points.append((px, py))

    # 用分段 BRepBuilderAPI_MakeEdge 构建多段线
    for i in range(len(inv_points) - 1):
        p1 = gp_Pnt(inv_points[i][0], inv_points[i][1], 0.0)
        p2 = gp_Pnt(inv_points[i + 1][0], inv_points[i + 1][1], 0.0)
        edge = BRepBuilderAPI_MakeEdge(p1, p2).Edge()
        wire_builder.Add(edge)

    # ── 齿顶圆弧 ──
    # 从渐开线终点到齿中心线 (θ=0)
    inv_end_pt = involute_point(r_b, xi_end)
    inv_end_angle = math.atan2(inv_end_pt[1], inv_end_pt[0])
    # inv_end_angle 应该在 (0, slot_center_angle) 之间

    tip_arc = GC_MakeArcOfCircle(
        gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_a),
        inv_end_angle,
        tooth_center_angle,
        True,  # clockwise direction from involute end to tooth centerline
    )
    if tip_arc.IsDone():
        edge_tip = BRepBuilderAPI_MakeEdge(tip_arc.Value()).Edge()
        wire_builder.Add(edge_tip)

    if not wire_builder.IsDone():
        raise RuntimeError(f"半周期 wire 构建失败: {wire_builder.Error()}")

    return wire_builder.Wire()


def build_full_tooth_wire(p: GearParams, n_involute: int = 80) -> TopoDS_Wire:
    """构建完整单齿廓形 wire (含左右齿面).

    直接构建左齿面 → 齿顶圆弧 → 右齿面 → 齿根圆弧 → 闭合。

    Args:
        p: 工件齿轮参数
        n_involute: 每侧渐开线采样点数

    Returns:
        TopoDS_Wire: 单齿完整闭合廓形
    """
    m_t, alpha_t_deg = p.to_transverse()
    alpha_t = math.radians(alpha_t_deg)

    r_a = p.tip_radius()
    r_f = p.root_radius()
    r_pw = p.pitch_radius()
    r_b = p.base_radius()
    rho_f = p.rho_f * p.m_n
    z_w = p.z_w

    s_t = compute_tooth_thickness(p)
    half_tooth_angle = s_t / (2.0 * r_pw)  # 齿厚半角 (在节圆上)

    pitch_angle = 2.0 * math.pi / z_w
    # 齿槽中心处 (在 +X 轴两侧，偏 half_tooth_angle)
    # 齿左侧在 angle = −half_tooth_angle (从齿中心线看)
    # 齿右侧在 angle = +half_tooth_angle

    wire_builder = BRepBuilderAPI_MakeWire()

    # ── 计算渐开线端点 ──
    involute_start_radius = max(r_b, r_f)
    xi_start = xi_at_radius(r_b, involute_start_radius) if involute_start_radius > r_b else 0.0
    xi_end = xi_at_radius(r_b, r_a)

    def involute_points_from_to(xi_from: float, xi_to: float, n: int) -> list[tuple[float, float]]:
        pts: list[tuple[float, float]] = []
        for i in range(n + 1):
            xi = xi_from + (xi_to - xi_from) * i / n
            pts.append(involute_point(r_b, xi))
        return pts

    # ── 左齿面 (从齿根→齿顶) ──
    left_inv_pts = involute_points_from_to(xi_start, xi_end, n_involute)

    # 旋转到正确角度: 左齿面在 −half_tooth_angle 处
    left_angle = -half_tooth_angle
    cos_la, sin_la = math.cos(left_angle), math.sin(left_angle)

    def rotate_pt(px: float, py: float, cos_a: float, sin_a: float) -> tuple[float, float]:
        return (px * cos_a - py * sin_a, px * sin_a + py * cos_a)

    # 构建左齿面边 (从齿根→齿顶)
    for i in range(len(left_inv_pts) - 1):
        p1 = left_inv_pts[i]
        p2 = left_inv_pts[i + 1]
        rp1 = rotate_pt(p1[0], p1[1], cos_la, sin_la)
        rp2 = rotate_pt(p2[0], p2[1], cos_la, sin_la)
        edge = BRepBuilderAPI_MakeEdge(
            gp_Pnt(rp1[0], rp1[1], 0.0),
            gp_Pnt(rp2[0], rp2[1], 0.0),
        ).Edge()
        wire_builder.Add(edge)

    # ── 齿顶圆弧 (从左齿面终点 → 右齿面终点) ──
    left_tip = rotate_pt(left_inv_pts[-1][0], left_inv_pts[-1][1], cos_la, sin_la)
    left_tip_angle = math.atan2(left_tip[1], left_tip[0])

    # 右齿面终点 (在 +half_tooth_angle)
    right_inv_pts = involute_points_from_to(xi_start, xi_end, n_involute)
    right_angle = half_tooth_angle
    cos_ra, sin_ra = math.cos(right_angle), math.sin(right_angle)
    right_tip = rotate_pt(right_inv_pts[-1][0], right_inv_pts[-1][1], cos_ra, sin_ra)
    right_tip_angle = math.atan2(right_tip[1], right_tip[0])

    # 齿顶圆弧: 从右齿面终点到左齿面终点 (逆时针)
    # 确保 right_tip_angle > left_tip_angle (跨过 0° 线时调整)
    if right_tip_angle <= left_tip_angle:
        right_tip_angle += 2.0 * math.pi

    tip_arc = GC_MakeArcOfCircle(
        gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_a),
        right_tip_angle,
        left_tip_angle,
        True,  # clockwise from right to left tip
    )
    if tip_arc.IsDone():
        wire_builder.Add(BRepBuilderAPI_MakeEdge(tip_arc.Value()).Edge())

    # ── 右齿面 (从齿顶→齿根, 反向遍历) ──
    for i in range(len(right_inv_pts) - 1, 0, -1):
        p1 = right_inv_pts[i]
        p2 = right_inv_pts[i - 1]
        rp1 = rotate_pt(p1[0], p1[1], cos_ra, sin_ra)
        rp2 = rotate_pt(p2[0], p2[1], cos_ra, sin_ra)
        edge = BRepBuilderAPI_MakeEdge(
            gp_Pnt(rp1[0], rp1[1], 0.0),
            gp_Pnt(rp2[0], rp2[1], 0.0),
        ).Edge()
        wire_builder.Add(edge)

    # ── 齿根连接段 (从右齿面齿根 → 左齿面齿根) ──
    right_root = rotate_pt(right_inv_pts[0][0], right_inv_pts[0][1], cos_ra, sin_ra)
    right_root_angle = math.atan2(right_root[1], right_root[0])
    right_root_r = math.sqrt(right_root[0]**2 + right_root[1]**2)

    left_root = rotate_pt(left_inv_pts[0][0], left_inv_pts[0][1], cos_la, sin_la)
    left_root_angle = math.atan2(left_root[1], left_root[0])
    left_root_r = math.sqrt(left_root[0]**2 + left_root[1]**2)

    if r_b > r_f:
        # 渐开线从基圆 r_b 开始，需要径向连接 r_b↔r_f
        # 1) 右齿面齿根 (at r_b) → 径向到 r_f
        rf_right_x = r_f * math.cos(right_root_angle)
        rf_right_y = r_f * math.sin(right_root_angle)
        edge = BRepBuilderAPI_MakeEdge(
            gp_Pnt(right_root[0], right_root[1], 0.0),
            gp_Pnt(rf_right_x, rf_right_y, 0.0),
        ).Edge()
        wire_builder.Add(edge)

        # 2) 齿根圆弧 at r_f (从右到左)
        rf_left_x = r_f * math.cos(left_root_angle)
        rf_left_y = r_f * math.sin(left_root_angle)
        rf_left_angle = left_root_angle
        rf_right_angle = right_root_angle
        if rf_left_angle <= rf_right_angle:
            rf_left_angle += 2.0 * math.pi

        root_arc = GC_MakeArcOfCircle(
            gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_f),
            rf_left_angle,
            rf_right_angle,
            True,
        )
        if root_arc.IsDone():
            wire_builder.Add(BRepBuilderAPI_MakeEdge(root_arc.Value()).Edge())

        # 3) 径向从 r_f → 左齿面齿根 (at r_b)
        edge = BRepBuilderAPI_MakeEdge(
            gp_Pnt(rf_left_x, rf_left_y, 0.0),
            gp_Pnt(left_root[0], left_root[1], 0.0),
        ).Edge()
        wire_builder.Add(edge)
    else:
        # 渐开线直接到齿根圆，用齿根圆弧连接两端
        rf_left_angle = left_root_angle
        rf_right_angle = right_root_angle
        if rf_left_angle <= rf_right_angle:
            rf_left_angle += 2.0 * math.pi

        root_arc = GC_MakeArcOfCircle(
            gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_f),
            rf_left_angle,
            rf_right_angle,
            True,
        )
        if root_arc.IsDone():
            wire_builder.Add(BRepBuilderAPI_MakeEdge(root_arc.Value()).Edge())

    if not wire_builder.IsDone():
        raise RuntimeError(f"完整齿廓 wire 构建失败")

    wire = wire_builder.Wire()
    if not wire.Closed():
        raise RuntimeError("完整齿廓 wire 不闭合")

    return wire


# ═══════════════════════════════════════════════════════════════════════
# 3D 实体构建
# ═══════════════════════════════════════════════════════════════════════

def _build_full_gear_2d_wire(p: GearParams, n_involute: int = 80) -> TopoDS_Wire:
    """构建完整齿圈 2D 廓形——所有 z_w 个齿直接用 root arc 连接成一个闭合 wire.

    避免了 Boolean union: 单 wire → 单 face → 单次 Prism = 极快的实体构建。
    """
    m_t, alpha_t_deg = p.to_transverse()

    r_a = p.tip_radius()
    r_f = p.root_radius()
    r_b = p.base_radius()

    z_w = p.z_w
    s_t = compute_tooth_thickness(p)
    half_tooth_angle = s_t / (2.0 * p.pitch_radius())
    pitch_angle = 2.0 * math.pi / z_w

    involute_start_radius = max(r_b, r_f)
    xi_start = xi_at_radius(r_b, involute_start_radius) if involute_start_radius > r_b else 0.0
    xi_end = xi_at_radius(r_b, r_a)

    # 预计算一个齿的渐开线模板 (在 tooth_angle=0 的坐标系)
    template_inv: list[tuple[float, float]] = []
    for i in range(n_involute + 1):
        xi = xi_start + (xi_end - xi_start) * i / n_involute
        template_inv.append(involute_point(r_b, xi))

    wire_builder = BRepBuilderAPI_MakeWire()

    for i_tooth in range(z_w):
        tooth_center = i_tooth * pitch_angle
        left_angle = tooth_center - half_tooth_angle
        right_angle = tooth_center + half_tooth_angle
        next_left_angle = (i_tooth + 1) * pitch_angle - half_tooth_angle

        cos_la, sin_la = math.cos(left_angle), math.sin(left_angle)
        cos_ra, sin_ra = math.cos(right_angle), math.sin(right_angle)

        def rot(pt: tuple[float, float], ca: float, sa: float) -> tuple[float, float]:
            return (pt[0] * ca - pt[1] * sa, pt[0] * sa + pt[1] * ca)

        # ── 左齿面 (从齿根→齿顶) ──
        for j in range(len(template_inv) - 1):
            rp1 = rot(template_inv[j], cos_la, sin_la)
            rp2 = rot(template_inv[j + 1], cos_la, sin_la)
            wire_builder.Add(BRepBuilderAPI_MakeEdge(
                gp_Pnt(rp1[0], rp1[1], 0), gp_Pnt(rp2[0], rp2[1], 0)).Edge())

        # ── 齿顶圆弧 (从左齿顶 → 右齿顶) ──
        left_tip = rot(template_inv[-1], cos_la, sin_la)
        left_tip_ang = math.atan2(left_tip[1], left_tip[0])
        right_tip = rot(template_inv[-1], cos_ra, sin_ra)
        right_tip_ang = math.atan2(right_tip[1], right_tip[0])

        if left_tip_ang < right_tip_ang:
            left_tip_ang += 2.0 * math.pi

        tip_arc = GC_MakeArcOfCircle(
            gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_a),
            left_tip_ang, right_tip_ang, True)
        if tip_arc.IsDone():
            wire_builder.Add(BRepBuilderAPI_MakeEdge(tip_arc.Value()).Edge())

        # ── 右齿面 (从齿顶→齿根) ──
        for j in range(len(template_inv) - 1, 0, -1):
            rp1 = rot(template_inv[j], cos_ra, sin_ra)
            rp2 = rot(template_inv[j - 1], cos_ra, sin_ra)
            wire_builder.Add(BRepBuilderAPI_MakeEdge(
                gp_Pnt(rp1[0], rp1[1], 0), gp_Pnt(rp2[0], rp2[1], 0)).Edge())

        # ── 齿根连接 (从当前右齿根 → 下一个左齿根) ──
        right_root = rot(template_inv[0], cos_ra, sin_ra)
        right_root_ang = math.atan2(right_root[1], right_root[0])

        cos_nla = math.cos(next_left_angle)
        sin_nla = math.sin(next_left_angle)
        next_left_root = rot(template_inv[0], cos_nla, sin_nla)
        next_left_root_ang = math.atan2(next_left_root[1], next_left_root[0])

        if r_b > r_f:
            # 渐开线从 r_b 开始: 径向线 r_b→r_f + 齿根弧 + 径向线 r_f→r_b
            rf_right_ang = right_root_ang
            rf_next_ang = next_left_root_ang
            if rf_next_ang < rf_right_ang:
                rf_next_ang += 2.0 * math.pi

            # 径向: right_root → r_f
            rf_x = r_f * math.cos(right_root_ang)
            rf_y = r_f * math.sin(right_root_ang)
            wire_builder.Add(BRepBuilderAPI_MakeEdge(
                gp_Pnt(right_root[0], right_root[1], 0),
                gp_Pnt(rf_x, rf_y, 0)).Edge())

            # 齿根弧 at r_f
            rf_arc = GC_MakeArcOfCircle(
                gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_f),
                rf_next_ang, rf_right_ang, True)
            if rf_arc.IsDone():
                wire_builder.Add(BRepBuilderAPI_MakeEdge(rf_arc.Value()).Edge())

            # 径向: r_f → next_left_root
            nrf_x = r_f * math.cos(next_left_root_ang)
            nrf_y = r_f * math.sin(next_left_root_ang)
            wire_builder.Add(BRepBuilderAPI_MakeEdge(
                gp_Pnt(nrf_x, nrf_y, 0),
                gp_Pnt(next_left_root[0], next_left_root[1], 0)).Edge())
        else:
            # 渐开线直达 r_f: 直接齿根弧连接
            nla_ang = next_left_root_ang
            if nla_ang < right_root_ang:
                nla_ang += 2.0 * math.pi

            rf_arc = GC_MakeArcOfCircle(
                gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r_f),
                nla_ang, right_root_ang, True)
            if rf_arc.IsDone():
                wire_builder.Add(BRepBuilderAPI_MakeEdge(rf_arc.Value()).Edge())

    if not wire_builder.IsDone():
        raise RuntimeError(f"全齿圈 2D wire 构建失败")

    wire = wire_builder.Wire()
    if not wire.Closed():
        raise RuntimeError(f"全齿圈 2D wire 不闭合")

    return wire


def build_gear(p: GearParams, n_slices: int = 12) -> TopoDS_Shape:
    """构建完整齿圈实体 (K-1.13 半周期 + 阵列 + ThruSections/Prism).

    直齿 (β=0): 全齿圈 2D 轮廓 → 单次拉伸 (无 Boolean union, 极快)
    斜齿 (β≠0): 单齿 ThruSections → 阵列 → Boolean union

    Args:
        p: 工件齿轮参数
        n_slices: 螺旋齿轮 Z 向切片数 (β=0 时忽略)

    Returns:
        TopoDS_Shape: 齿圈实体
    """
    if abs(p.beta_w_deg) < 1e-9:
        # 直齿轮: 全齿圈 2D 轮廓 → 单次拉伸
        full_wire = _build_full_gear_2d_wire(p)
        face = BRepBuilderAPI_MakeFace(full_wire).Face()
        prism_vec = gp_Vec(0.0, 0.0, p.b_w)
        prism = BRepPrimAPI_MakePrism(face, prism_vec, True)
        return prism.Shape()
    else:
        # 斜齿轮: 单齿 ThruSections → 阵列 → Boolean union
        # ⚠️ OCP 7.9.3 限制: TopoDS_Wire downcast 不可用，暂用全齿圈 wire 放样
        raise NotImplementedError(
            "斜齿轮 ThruSections 在 OCP 7.9.3 中暂不可用 "
            "(TopoDS_Wire 的 Python downcast 不支持)。"
            "预计在 OCP 升级后恢复。"
        )
        z_w = p.z_w
        pitch_angle = 2.0 * math.pi / z_w
        b_w = p.b_w
        beta_w = math.radians(p.beta_w_deg)
        j_w = p.j_w
        r_pw = p.pitch_radius()

        tooth_wire = build_full_tooth_wire(p)

        section_wires: list[TopoDS_Wire] = []
        for i_slice in range(n_slices + 1):
            z = b_w * i_slice / n_slices
            theta = j_w * z * math.tan(beta_w) / r_pw

            trsf = gp_Trsf()
            trsf.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), theta)
            trsf.SetTranslation(gp_Vec(0, 0, z))

            rotated_shape = BRepBuilderAPI_Transform(tooth_wire, trsf, True).Shape()
            rotated_wire = TopoDS_Wire._from_address(rotated_shape._address())
            section_wires.append(rotated_wire)

        thru = BRepOffsetAPI_ThruSections(False, False, 1e-6)
        for w in section_wires:
            thru.AddWire(w)
        thru.Build()

        if not thru.IsDone():
            raise RuntimeError("ThruSections 放样失败")

        single_tooth = thru.Shape()

        # 阵列
        solids: list[TopoDS_Shape] = [single_tooth]
        for i in range(1, z_w):
            angle = pitch_angle * i
            trsf = gp_Trsf()
            trsf.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), angle)
            rotated = BRepBuilderAPI_Transform(single_tooth, trsf, True).Shape()
            solids.append(rotated)

        fused = solids[0]
        for i in range(1, len(solids)):
            fuse_op = BRepAlgoAPI_Fuse(fused, solids[i])
            if fuse_op.IsDone():
                fused = fuse_op.Shape()

        return fused


# ═══════════════════════════════════════════════════════════════════════
# K-1.11 齿厚反算
# ═══════════════════════════════════════════════════════════════════════

def compute_tooth_thickness(p: GearParams) -> float:
    """K-1.11: 计算端面节圆齿厚 s_t.

    支持三种齿厚指定方式:
      - x_w: s_t = π·m_t/2 + 2·x_w·m_n·tan(α_t)
      - W_k: 通过 back_solve_x_w_from_W_k 反推 x_w
      - M: 通过 back_solve_x_w_from_M 反推 x_w

    Args:
        p: 工件齿轮参数

    Returns:
        端面节圆齿厚 s_t [mm]
    """
    m_t, alpha_t_deg = p.to_transverse()
    alpha_t = math.radians(alpha_t_deg)

    if p.tooth_method == "x_w":
        x_w = p.x_w
    elif p.tooth_method == "W_k":
        if p.W_k is None or p.k_teeth is None:
            raise ValueError("tooth_method='W_k' 需要提供 W_k 和 k_teeth")
        x_w = back_solve_x_w_from_W_k(p, p.W_k, p.k_teeth)
    elif p.tooth_method == "M":
        if p.M is None or p.d_p is None:
            raise ValueError("tooth_method='M' 需要提供 M 和 d_p")
        x_w = back_solve_x_w_from_M(p, p.M, p.d_p)
    else:
        raise ValueError(f"未知的齿厚方式: {p.tooth_method}")

    # s_t = π·m_t/2 + 2·x_w·m_n·tan(α_t)
    s_t = math.pi * m_t / 2.0 + 2.0 * x_w * p.m_n * math.tan(alpha_t)
    return s_t


def back_solve_x_w_from_W_k(p: GearParams, W_k: float, k: int) -> float:
    """K-1.11: 从公法线长度 W_k 反推变位系数 x_w.

    公法线长度:
      W_k = m_n·cos(α_n)·[(k−0.5)·π + z_w·inv(α_t) + 2·x_w·tan(α_n)]

    其中 inv(α) = tan(α) − α.

    Args:
        p: 工件齿轮参数 (不含 x_w)
        W_k: 公法线长度 [mm]
        k: 跨齿数

    Returns:
        变位系数 x_w
    """
    _, alpha_t_deg = p.to_transverse()
    alpha_t = math.radians(alpha_t_deg)
    alpha_n = math.radians(p.alpha_n_deg)

    inv_at = math.tan(alpha_t) - alpha_t

    # W_k = m_n·cos(α_n)·[(k−0.5)·π + z_w·inv(α_t) + 2·x_w·tan(α_n)]
    # ⇒ x_w = (W_k / (m_n·cos(α_n)) − (k−0.5)·π − z_w·inv(α_t)) / (2·tan(α_n))
    base = p.m_n * math.cos(alpha_n)
    term1 = (k - 0.5) * math.pi
    term2 = p.z_w * inv_at
    x_w = (W_k / base - term1 - term2) / (2.0 * math.tan(alpha_n))

    return x_w


def back_solve_x_w_from_M(p: GearParams, M: float, d_p: float) -> float:
    """K-1.11: 从跨棒距 M 反推变位系数 x_w (端面近似).

    对于直齿轮 (β=0):
      cos(α_M) = d_b / (M − d_p)  (外齿轮, k_io=+1)
      inv(α_M) = inv(α_t) + d_p/(m_n·z_w·cos(α_n)) − π/(2·z_w) + 2·x_w·tan(α_n)/z_w

    Args:
        p: 工件齿轮参数 (不含 x_w)
        M: 跨棒距 [mm]
        d_p: 量棒直径 [mm]

    Returns:
        变位系数 x_w
    """
    m_t, alpha_t_deg = p.to_transverse()
    alpha_t = math.radians(alpha_t_deg)
    alpha_n = math.radians(p.alpha_n_deg)
    d_b = 2.0 * p.base_radius()

    if p.k_io == 1:
        # 外齿轮: M = d_b / cos(α_M) + d_p
        cos_alpha_M = d_b / (M - d_p)
    else:
        # 内齿轮: M = d_b / cos(α_M) − d_p
        cos_alpha_M = d_b / (M + d_p)

    if abs(cos_alpha_M) > 1.0:
        raise ValueError(f"量棒参数不合理: cos(α_M)={cos_alpha_M} 超出 [−1,1]")

    alpha_M = math.acos(cos_alpha_M)
    inv_alpha_M = math.tan(alpha_M) - alpha_M
    inv_alpha_t = math.tan(alpha_t) - alpha_t

    # inv(α_M) = inv(α_t) + d_p/(m_n·z_w·cos(α_n)) − π/(2·z_w) + 2·x_w·tan(α_n)/z_w
    # ⇒ x_w = z_w/(2·tan(α_n)) · [inv(α_M) − inv(α_t) − d_p/(m_n·z_w·cos(α_n)) + π/(2·z_w)]
    term = (
        inv_alpha_M
        - inv_alpha_t
        - d_p / (p.m_n * p.z_w * math.cos(alpha_n))
        + math.pi / (2.0 * p.z_w)
    )
    x_w = p.z_w / (2.0 * math.tan(alpha_n)) * term
    return x_w


# ═══════════════════════════════════════════════════════════════════════
# 辅助测量函数 (测试用)
# ═══════════════════════════════════════════════════════════════════════

def compute_bounding_box_diameter(shape: TopoDS_Shape) -> float:
    """从形状估算齿顶圆直径.

    优先用 BRepGProp 包围盒；失败则用顶点遍历。

    Args:
        shape: TopoDS_Shape (齿轮实体)

    Returns:
        近似齿顶圆直径 [mm]
    """
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

    # Fallback: vertex traversal (需要正确的 OCP vertex API)
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
    """计算形状到 Z 轴的最小径向距离 (近似齿根圆).

    遍历所有顶点，找最小 XY 平面到原点的距离。

    Args:
        shape: TopoDS_Shape

    Returns:
        最小径向距离 [mm]
    """
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.BRep import BRep_Tool

    min_r = float("inf")
    explorer = TopExp_Explorer(shape, TopAbs_VERTEX, TopAbs_VERTEX)
    while explorer.More():
        v = explorer.Current()
        p = BRep_Tool.Pnt(v)
        r = math.sqrt(p.X() ** 2 + p.Y() ** 2)
        if r > 0.001 and r < min_r:  # 排除原点
            min_r = r
        explorer.Next()

    return min_r


def count_teeth_from_shape(shape: TopoDS_Shape) -> int:
    """从形状估算齿数 (基于面片数).

    不精确，仅用于合理性检验。

    Args:
        shape: TopoDS_Shape

    Returns:
        估算齿数
    """
    n_faces = 0
    explorer = TopExp_Explorer(shape, TopAbs_FACE, TopAbs_FACE)
    while explorer.More():
        n_faces += 1
        explorer.Next()
    # 每个齿约贡献 6-8 个面 (2 侧面 + 齿顶 + 齿根 + 2 端面 + 圆角)
    return n_faces // 7


def build_2d_profile_wire(p: GearParams) -> TopoDS_Wire:
    """构建 2D 半周期齿廓 wire (测试用).

    Args:
        p: 工件齿轮参数

    Returns:
        TopoDS_Wire
    """
    return build_half_period_wire(p)

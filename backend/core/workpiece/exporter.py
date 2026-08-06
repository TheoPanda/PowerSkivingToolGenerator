"""纯 Python GLB 导出器 — 直接从渐开线数学生成齿轮 mesh.

OCP 7.9.3 限制: TopoDS 类型 downcast 不可用, BRep_Tool.Triangulation_s
和 StlAPI_Writer 均无法正常工作。改用纯 Python 三角剖分。

管线:
  GearParams → K-1.1 渐开线点集 (2D)
            → 全齿圈 2D 轮廓
            → 手动三角剖分 (2D face + 3D extrusion side walls)
            → pygltflib 写 GLB
"""

import base64
import math
import struct

from core.workpiece.models import GearParams, involute_point, xi_at_radius
from core.workpiece.builder import compute_tooth_thickness


def _build_mesh_data(
    p: GearParams,
    n_involute: int = 40,
    n_depth: int = 2,
) -> tuple[list[float], list[float], list[int]]:
    """从 GearParams 直接构建齿轮 3D mesh.

    Args:
        p: 齿轮参数
        n_involute: 每侧渐开线采样点数
        n_depth: 深度方向采样点数 (2 = only top/bottom faces)

    Returns:
        (positions, normals, indices)
    """
    z_w = p.z_w
    b_w = p.b_w
    r_a = p.tip_radius()
    r_f = p.root_radius()
    r_b = p.base_radius()
    involute_start_radius = max(r_b, r_f)

    s_t = compute_tooth_thickness(p)
    half_tooth_angle = s_t / (2.0 * p.pitch_radius())
    pitch_angle = 2.0 * math.pi / z_w

    xi_start = xi_at_radius(r_b, involute_start_radius) if involute_start_radius > r_b else 0.0
    xi_end = xi_at_radius(r_b, r_a)

    # 预计算一个齿的渐开线轮廓模板
    template_pts: list[tuple[float, float]] = []
    for i in range(n_involute + 1):
        xi = xi_start + (xi_end - xi_start) * i / n_involute
        template_pts.append(involute_point(r_b, xi))

    def rot(pt: tuple[float, float], ca: float, sa: float) -> tuple[float, float]:
        return (pt[0] * ca - pt[1] * sa, pt[0] * sa + pt[1] * ca)

    # ── 生成 2D 全齿圈轮廓点 (无序，用于三角剖分) ──
    # 方法: 生成齿圈 2D 多边形顶点 + 内部采样点
    # 用扇形三角剖分 (从圆心到每个边界点)

    # 收集所有边界点 (绕 Z 轴顺序)
    boundary_2d: list[tuple[float, float]] = []

    for i_tooth in range(z_w):
        tooth_center = i_tooth * pitch_angle
        left_angle = tooth_center - half_tooth_angle
        right_angle = tooth_center + half_tooth_angle

        cos_la = math.cos(left_angle)
        sin_la = math.sin(left_angle)
        cos_ra = math.cos(right_angle)
        sin_ra = math.sin(right_angle)

        # 左齿面 (从齿根→齿顶)
        for pt in template_pts:
            rp = rot(pt, cos_la, sin_la)
            boundary_2d.append(rp)

        # 齿顶 (从左齿顶→右齿顶): 用齿顶圆弧采样点
        left_tip = rot(template_pts[-1], cos_la, sin_la)
        left_tip_ang = math.atan2(left_tip[1], left_tip[0])
        right_tip = rot(template_pts[-1], cos_ra, sin_ra)
        right_tip_ang = math.atan2(right_tip[1], right_tip[0])

        if right_tip_ang < left_tip_ang:
            right_tip_ang += 2.0 * math.pi

        n_tip = 10
        for j in range(1, n_tip + 1):
            t = j / (n_tip + 1)
            ang = left_tip_ang - t * (left_tip_ang - right_tip_ang)
            boundary_2d.append((r_a * math.cos(ang), r_a * math.sin(ang)))

        # 右齿面 (从齿顶→齿根)
        for pt in reversed(template_pts):
            rp = rot(pt, cos_ra, sin_ra)
            boundary_2d.append(rp)

        # 齿根连接 (从右齿根→下一个左齿根)
        right_root = rot(template_pts[0], cos_ra, sin_ra)
        right_root_ang = math.atan2(right_root[1], right_root[0])

        next_tooth_center = (i_tooth + 1) * pitch_angle
        next_left_angle = next_tooth_center - half_tooth_angle
        cos_nla = math.cos(next_left_angle)
        sin_nla = math.sin(next_left_angle)
        next_left_root = rot(template_pts[0], cos_nla, sin_nla)
        next_left_root_ang = math.atan2(next_left_root[1], next_left_root[0])

        if r_b > r_f:
            # 径向 r_b→r_f
            boundary_2d.append((r_f * math.cos(right_root_ang), r_f * math.sin(right_root_ang)))
            # 齿根弧 (从 right_root_ang → next_left_root_ang, 逆时针)
            nla = next_left_root_ang
            if nla < right_root_ang:
                nla += 2.0 * math.pi
            n_rf = 5
            for j in range(1, n_rf + 1):
                t = j / (n_rf + 1)
                ang = right_root_ang + t * (nla - right_root_ang)
                boundary_2d.append((r_f * math.cos(ang), r_f * math.sin(ang)))
            boundary_2d.append((r_f * math.cos(next_left_root_ang), r_f * math.sin(next_left_root_ang)))
        else:
            nla = next_left_root_ang
            if nla < right_root_ang:
                nla += 2.0 * math.pi
            n_rf = 5
            for j in range(1, n_rf + 1):
                t = j / (n_rf + 1)
                ang = right_root_ang + t * (nla - right_root_ang)
                boundary_2d.append((r_f * math.cos(ang), r_f * math.sin(ang)))

    # ── 三角剖分 ──
    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []

    n_boundary = len(boundary_2d)
    if n_boundary < 3:
        raise RuntimeError("边界点不足")

    # 顶面 (z = 0 平面): 扇形三角剖分 (center → boundary)
    center_idx = 0
    positions.extend([0.0, 0.0, 0.0])  # 中心顶点
    normals.extend([0.0, 0.0, -1.0])   # 朝下 (Z-)

    for i, (bx, by) in enumerate(boundary_2d):
        positions.extend([bx, by, 0.0])
        normals.extend([0.0, 0.0, -1.0])

    for i in range(n_boundary):
        j = (i + 1) % n_boundary
        indices.extend([center_idx, center_idx + 1 + i, center_idx + 1 + j])

    top_vertex_count = 1 + n_boundary

    # 底面 (z = b_w 平面): 复制顶面点，翻转法向
    for i in range(top_vertex_count):
        px = positions[i * 3]
        py = positions[i * 3 + 1]
        positions.extend([px, py, b_w])
        normals.extend([0.0, 0.0, 1.0])  # 朝上 (Z+)

    bottom_start = top_vertex_count
    for i in range(n_boundary):
        j = (i + 1) % n_boundary
        # 底面三角形: 翻转绕序
        indices.extend([
            bottom_start + center_idx,
            bottom_start + 1 + j,
            bottom_start + 1 + i,
        ])

    # 侧壁 (连接顶面和底面边界)
    wall_start = len(positions) // 3
    for i in range(n_boundary):
        bx, by = boundary_2d[i]
        # 顶面边界顶点 (复用)
        positions.extend([bx, by, 0.0])
        positions.extend([bx, by, b_w])

        # 侧壁法向: 径向向外
        length = math.sqrt(bx * bx + by * by)
        if length > 1e-12:
            nx, ny = bx / length, by / length
        else:
            nx, ny = 1.0, 0.0
        normals.extend([nx, ny, 0.0])
        normals.extend([nx, ny, 0.0])

    for i in range(n_boundary):
        j = (i + 1) % n_boundary
        a = wall_start + 2 * i       # top vertex
        b = wall_start + 2 * i + 1   # bottom vertex
        c = wall_start + 2 * j       # next top vertex
        d = wall_start + 2 * j + 1   # next bottom vertex

        # 两个三角形
        indices.extend([a, b, c])
        indices.extend([b, d, c])

    return positions, normals, indices


def export_glb_bytes(
    p: GearParams,
    n_involute: int = 40,
) -> bytes:
    """从 GearParams 导出 GLB 二进制.

    Args:
        p: 齿轮参数
        n_involute: 渐开线采样点数 (越大越精确)

    Returns:
        GLB 二进制数据
    """
    positions, normals, indices = _build_mesh_data(p, n_involute)

    from pygltflib import (
        GLTF2,
        Buffer,
        BufferView,
        Accessor,
        Mesh,
        Node,
        Scene,
        Primitive,
        Attributes,
        Asset,
    )

    gltf = GLTF2()
    gltf.asset = Asset(version="2.0")

    # 打包
    positions_bytes = struct.pack(f"<{len(positions)}f", *positions)
    normals_bytes = struct.pack(f"<{len(normals)}f", *normals)

    while len(positions_bytes) % 4 != 0:
        positions_bytes += b"\x00"
    while len(normals_bytes) % 4 != 0:
        normals_bytes += b"\x00"

    use_uint16 = max(indices) < 65536 if indices else True
    if use_uint16:
        indices_bytes = struct.pack(f"<{len(indices)}H", *indices)
        index_component_type = 5123
    else:
        indices_bytes = struct.pack(f"<{len(indices)}I", *indices)
        index_component_type = 5125

    while len(indices_bytes) % 4 != 0:
        indices_bytes += b"\x00"

    buffer_data = positions_bytes + normals_bytes + indices_bytes
    buffer = Buffer(byteLength=len(buffer_data))

    pos_len = len(positions_bytes)
    norm_len = len(normals_bytes)
    idx_len = len(indices_bytes)

    pos_bv = BufferView(buffer=0, byteOffset=0, byteLength=pos_len)
    norm_bv = BufferView(buffer=0, byteOffset=pos_len, byteLength=norm_len)
    idx_bv = BufferView(buffer=0, byteOffset=pos_len + norm_len, byteLength=idx_len)

    n_vertices = len(positions) // 3
    n_idx = len(indices)

    pos_acc = Accessor(
        bufferView=0, componentType=5126, count=n_vertices, type="VEC3",
        max=[max(positions[i::3]) for i in range(3)] if n_vertices > 0 else [0, 0, 0],
        min=[min(positions[i::3]) for i in range(3)] if n_vertices > 0 else [0, 0, 0],
    )
    norm_acc = Accessor(bufferView=1, componentType=5126, count=n_vertices, type="VEC3")
    idx_acc = Accessor(bufferView=2, componentType=index_component_type, count=n_idx, type="SCALAR")

    gltf.buffers = [buffer]
    gltf.bufferViews = [pos_bv, norm_bv, idx_bv]
    gltf.accessors = [pos_acc, norm_acc, idx_acc]

    primitive = Primitive(attributes=Attributes(POSITION=0, NORMAL=1), indices=2)
    mesh = Mesh(primitives=[primitive])
    gltf.meshes = [mesh]
    gltf.nodes = [Node(mesh=0)]
    gltf.scenes = [Scene(nodes=[0])]
    gltf.scene = 0

    gltf.set_binary_blob(buffer_data)
    parts = gltf.save_to_bytes()
    return b"".join(parts)


def export_glb_base64(p: GearParams, n_involute: int = 40) -> str:
    """导出 GLB 为 base64 字符串."""
    glb_bytes = export_glb_bytes(p, n_involute)
    return base64.b64encode(glb_bytes).decode("ascii")

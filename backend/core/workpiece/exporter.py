"""GLB 导出器 — 消费 GearModel, 从 builder 提供的 faces 提取 triangles, 写 GLB.

单一职责: GearModel → OCCT tessellation → GLB bytes.
不再导入 profile.py 或自行构建任何几何体。

OCP 7.9.3 限制: 不能从 solid 提取 faces (downcast bug), 故依赖 builder 提供
原生 TopoDS_Face (来自 MakeFace) 和 boundary wire。
"""

import base64
import math
import struct

from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopLoc import TopLoc_Location
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir

from core.workpiece.builder import GearModel


def _extract_boundary_cycles(
    o_nodes: list[tuple[float, float]],
    o_triangles: list[tuple[int, int, int]],
) -> list[list[int]]:
    """从 triangulation 提取全部边界环索引 (外边界 CCW + 孔边界 CW).

    内齿轮环形 face 有两条边界 (外 rim + 内齿孔)，侧壁需各自构建。
    定向: 面积最大环 = 外边界 → CCW; 其余 (孔) → CW。侧壁法向 (dy,−dx)
    对二者均指离料 (外壁外指, 内壁指向孔心)。
    """
    edge_count: dict[tuple[int, int], int] = {}
    for a, b, c in o_triangles:
        for u, v in ((a, b), (b, c), (c, a)):
            key = (min(u, v), max(u, v))
            edge_count[key] = edge_count.get(key, 0) + 1

    boundary_edges = {k for k, c in edge_count.items() if c == 1}
    if not boundary_edges:
        return [list(range(len(o_nodes)))]

    adj: dict[int, list[int]] = {}
    for u, v in boundary_edges:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)

    cycles: list[list[int]] = []
    unvisited = set(adj.keys())
    while unvisited:
        start = unvisited.pop()
        cycle = [start]
        visited = {start}
        cur = start
        while True:
            nxt = [v for v in adj[cur] if v not in visited or (v == start and len(cycle) > 2)]
            if not nxt:
                break
            cur = nxt[0]
            if cur == start:
                break
            visited.add(cur)
            cycle.append(cur)
            unvisited.discard(cur)
        cycles.append(cycle)

    def _signed2(cyc: list[int]) -> float:
        return sum(
            o_nodes[cyc[i]][0] * o_nodes[cyc[(i + 1) % len(cyc)]][1]
            - o_nodes[cyc[(i + 1) % len(cyc)]][0] * o_nodes[cyc[i]][1]
            for i in range(len(cyc))
        )

    ranked = sorted(cycles, key=lambda c: abs(_signed2(c)), reverse=True)
    outer = ranked[0]
    if _signed2(outer) < 0:
        outer.reverse()
    result = [outer]
    for cyc in ranked[1:]:
        if _signed2(cyc) > 0:
            cyc.reverse()  # 孔 → CW
        result.append(cyc)
    return result


def _tessellate_face(face, deflection: float):
    """BRepMesh + Triangulation_s → (nodes, triangles, occt_is_ccw)."""
    mesh = BRepMesh_IncrementalMesh(face, deflection, False, deflection, False)
    mesh.Perform()
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(face, loc)
    if tri is None or tri.NbNodes() < 3:
        raise RuntimeError("端面三角剖分失败")

    n_nodes = tri.NbNodes()
    n_tris = tri.NbTriangles()
    nodes: list[tuple[float, float]] = []
    for i in range(1, n_nodes + 1):
        node = tri.Node(i)
        nodes.append((node.X(), node.Y()))
    triangles: list[tuple[int, int, int]] = []
    for i in range(1, n_tris + 1):
        t = tri.Triangle(i)
        triangles.append((t.Value(1) - 1, t.Value(2) - 1, t.Value(3) - 1))

    total_signed = 0.0
    for a, b, c in triangles:
        total_signed += (nodes[b][0] - nodes[a][0]) * (nodes[c][1] - nodes[a][1]) \
                      - (nodes[b][1] - nodes[a][1]) * (nodes[c][0] - nodes[a][0])
    return nodes, triangles, total_signed > 0


def _rotate_nodes(nodes, angle: float):
    ca, sa = math.cos(angle), math.sin(angle)
    return [(x * ca - y * sa, x * sa + y * ca) for x, y in nodes]


def _build_spur_mesh(model: GearModel, deflection: float):
    """直齿轮: 端面 + 侧壁直拉伸 (外齿轮 1 条边界; 内齿轮环形 2 条边界外壁+内齿壁)."""
    nodes, triangles, ccw = _tessellate_face(model.cap_face, deflection)
    boundaries = _extract_boundary_cycles(nodes, triangles)
    n_nodes = len(nodes)

    top_order = (lambda a, b, c: (a, c, b)) if ccw else (lambda a, b, c: (a, b, c))
    btm_order = (lambda a, b, c: (a, b, c)) if ccw else (lambda a, b, c: (a, c, b))

    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []

    for x, y in nodes:
        positions.extend([x, y, 0.0])
        normals.extend([0.0, 0.0, -1.0])
    for a, b, c in triangles:
        indices.extend(top_order(a, b, c))

    bottom_start = n_nodes
    for x, y in nodes:
        positions.extend([x, y, model.b_w])
        normals.extend([0.0, 0.0, 1.0])
    for a, b, c in triangles:
        indices.extend(btm_order(bottom_start + a, bottom_start + b, bottom_start + c))

    # 侧壁: 每条边界环各自构建 (外齿轮 1 环; 内齿轮 外 rim 环 + 内齿廓环)
    wall_start = 2 * n_nodes
    quad = 0
    for boundary in boundaries:
        for idx in range(len(boundary)):
            i = boundary[idx]
            j = boundary[(idx + 1) % len(boundary)]
            x0, y0 = nodes[i]
            x1, y1 = nodes[j]
            dx, dy = x1 - x0, y1 - y0
            length = math.hypot(dx, dy)
            nx, ny = (dy / length, -dx / length) if length > 1e-12 else (1.0, 0.0)
            a = wall_start + 4 * quad
            quad += 1
            positions.extend([x0, y0, 0.0, x1, y1, 0.0, x1, y1, model.b_w, x0, y0, model.b_w])
            normals.extend([nx, ny, 0.0] * 4)
            indices.extend([a, a + 1, a + 2])
            indices.extend([a, a + 2, a + 3])

    return positions, normals, indices


def _build_helical_unit_mesh(model: GearModel, deflection: float,
                             base_nodes, base_tris, ccw, boundaries):
    """斜齿轮「单位」mesh (外壳: 两端 cap + 多边界侧壁共享顶点, 带扭转).

    外斜齿: cap_face 为单齿 (1 边界环), 单位 = 一个齿, 由调用方阵列 z_w 次;
    内斜齿: cap_face 为全齿轮环形 (2 边界环: rim + 内齿廓), 单位 = 整齿圈, 阵列 1 次。
    侧壁每层只存全部边界环共享顶点 (smooth 法向由相邻 quad 平均)。
    内孔边界 (CW) 法向 u×w=wz·(dy,−dx) 指向孔心 (离料), 与外直齿内孔一致。
    """
    sections = model.helical_sections
    if sections is None:
        raise RuntimeError("斜齿轮缺少截面数据")
    n_slices = len(sections)
    n_nodes = len(base_nodes)
    n_b = sum(len(b) for b in boundaries)

    # 每边界环在层内的起始偏移 (层内按 boundaries 顺序连续排布)
    bstarts: list[int] = []
    cum = 0
    for b in boundaries:
        bstarts.append(cum)
        cum += len(b)

    top_order = (lambda a, b, c: (a, c, b)) if ccw else (lambda a, b, c: (a, b, c))
    btm_order = (lambda a, b, c: (a, b, c)) if ccw else (lambda a, b, c: (a, c, b))

    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []

    # ── 两端 cap 节点 (slice 0 底面法向 −Z, slice N-1 顶面法向 +Z) ──
    z_top, th_top = sections[0]
    for x, y in _rotate_nodes(base_nodes, th_top):
        positions.extend([x, y, z_top])
    normals.extend([0.0, 0.0, -1.0] * n_nodes)

    z_btm, th_btm = sections[n_slices - 1]
    for x, y in _rotate_nodes(base_nodes, th_btm):
        positions.extend([x, y, z_btm])
    normals.extend([0.0, 0.0, 1.0] * n_nodes)

    for a, b, c in base_tris:
        indices.extend(top_order(a, b, c))

    btm_start = n_nodes
    for a, b, c in base_tris:
        indices.extend(btm_order(btm_start + a, btm_start + b, btm_start + c))

    # ── 侧壁: 每层存全部边界环共享顶点, smooth 法向 ──
    wall_start = 2 * n_nodes
    layer_offsets: list[int] = []
    for k in range(n_slices):
        z, th = sections[k]
        r = _rotate_nodes(base_nodes, th)
        layer_offsets.append(wall_start + k * n_b)
        for b in boundaries:
            for i in b:
                x, y = r[i]
                positions.extend([x, y, z])
        normals.extend([0.0, 0.0, 0.0] * n_b)

    # 侧壁索引 + 法向累积 (quad 几何法向 u×w, 外边界外指/内孔指孔心)
    for bi, b in enumerate(boundaries):
        n_bnd = len(b)
        bo = bstarts[bi]
        for k in range(n_slices - 1):
            z0, th0 = sections[k]
            z1, th1 = sections[k + 1]
            r0 = _rotate_nodes(base_nodes, th0)
            r1 = _rotate_nodes(base_nodes, th1)
            o0, o1 = layer_offsets[k], layer_offsets[k + 1]
            for idx in range(n_bnd):
                i = b[idx]
                j = b[(idx + 1) % n_bnd]
                p00 = (r0[i][0], r0[i][1], z0)
                p01 = (r0[j][0], r0[j][1], z0)
                p11 = (r1[j][0], r1[j][1], z1)
                p10 = (r1[i][0], r1[i][1], z1)
                a = o0 + bo + idx
                bb = o0 + bo + (idx + 1) % n_bnd
                c = o1 + bo + (idx + 1) % n_bnd
                d = o1 + bo + idx
                indices.extend([a, bb, c])
                indices.extend([a, c, d])

                # u = 下边 (边界切线), w = 斜向上 → u×w 径向离料
                ux, uy = p01[0] - p00[0], p01[1] - p00[1]
                wz = p11[2] - p00[2]
                nx = uy * wz
                ny = -ux * wz
                nz = ux * (p11[1] - p00[1]) - uy * (p11[0] - p00[0])
                for vi in (a, bb, c, d):
                    o3 = vi * 3
                    normals[o3] += nx
                    normals[o3 + 1] += ny
                    normals[o3 + 2] += nz

    # 归一化侧壁 smooth 法向
    for v in range(wall_start, wall_start + n_slices * n_b):
        o3 = v * 3
        nx, ny, nz = normals[o3], normals[o3 + 1], normals[o3 + 2]
        ln = math.sqrt(nx * nx + ny * ny + nz * nz)
        if ln > 1e-12:
            normals[o3] = nx / ln
            normals[o3 + 1] = ny / ln
            normals[o3 + 2] = nz / ln
        else:
            normals[o3] = 1.0
            normals[o3 + 1] = 0.0
            normals[o3 + 2] = 0.0

    return positions, normals, indices


def _array_helical_unit(unit, z_w: int):
    """斜齿轮单位 mesh → 绕 Z 阵列 z_w 次 (外斜齿单齿用)."""
    pos1, nrm1, idx1 = unit
    if z_w <= 1:
        return pos1, nrm1, idx1

    pitch_angle = 2.0 * math.pi / z_w
    n_verts_per_unit = len(pos1) // 3
    n_idx_per_unit = len(idx1)

    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []

    for i in range(z_w):
        angle = pitch_angle * i
        ca, sa = math.cos(angle), math.sin(angle)

        for v in range(n_verts_per_unit):
            x = pos1[3 * v]
            y = pos1[3 * v + 1]
            z = pos1[3 * v + 2]
            positions.extend([x * ca - y * sa, x * sa + y * ca, z])

            nx = nrm1[3 * v]
            ny = nrm1[3 * v + 1]
            nz = nrm1[3 * v + 2]
            normals.extend([nx * ca - ny * sa, nx * sa + ny * ca, nz])

        offset = i * n_verts_per_unit
        for t in range(n_idx_per_unit):
            indices.append(offset + idx1[t])

    return positions, normals, indices


def _build_helical_mesh(model: GearModel, deflection: float):
    """斜齿轮 mesh: 单位 mesh → 按边界数决定阵列.

    外斜齿 (cap_face 单齿, 1 边界环) → 阵列 z_w 次 (各齿独立 solid 复合);
    内斜齿 (cap_face 全齿轮环形, ≥2 边界环: rim + 内齿廓) → 单位即整齿圈, 阵列 1 次。
    """
    base_nodes, base_tris, ccw = _tessellate_face(model.cap_face, deflection)
    boundaries = _extract_boundary_cycles(base_nodes, base_tris)
    unit = _build_helical_unit_mesh(model, deflection, base_nodes, base_tris, ccw, boundaries)
    if len(boundaries) > 1:
        return unit  # 内斜齿: 全截面单位 (双边界), 不阵列
    return _array_helical_unit(unit, model.z_w)


def _model_to_mesh(model: GearModel, deflection: float = 0.3):
    if model.helical_sections is None:
        return _build_spur_mesh(model, deflection)
    else:
        return _build_helical_mesh(model, deflection)


def export_glb_bytes(model: GearModel, deflection: float = 0.3) -> bytes:
    """从 GearModel 导出 GLB 二进制."""
    positions, normals, indices = _model_to_mesh(model, deflection)

    from pygltflib import (
        GLTF2, Buffer, BufferView, Accessor, Mesh, Node, Scene,
        Primitive, Attributes, Asset,
    )

    gltf = GLTF2()
    gltf.asset = Asset(version="2.0")

    positions_bytes = struct.pack(f"<{len(positions)}f", *positions)
    normals_bytes = struct.pack(f"<{len(normals)}f", *normals)
    while len(positions_bytes) % 4 != 0:
        positions_bytes += b"\x00"
    while len(normals_bytes) % 4 != 0:
        normals_bytes += b"\x00"

    use_uint16 = max(indices) < 65536 if indices else True
    fmt = "H" if use_uint16 else "I"
    ctype = 5123 if use_uint16 else 5125
    indices_bytes = struct.pack(f"<{len(indices)}{fmt}", *indices)
    while len(indices_bytes) % 4 != 0:
        indices_bytes += b"\x00"

    buffer_data = positions_bytes + normals_bytes + indices_bytes
    buffer = Buffer(byteLength=len(buffer_data))

    pos_len, norm_len, idx_len = len(positions_bytes), len(normals_bytes), len(indices_bytes)
    pos_bv = BufferView(buffer=0, byteOffset=0, byteLength=pos_len)
    norm_bv = BufferView(buffer=0, byteOffset=pos_len, byteLength=norm_len)
    idx_bv = BufferView(buffer=0, byteOffset=pos_len + norm_len, byteLength=idx_len)

    n_vertices = len(positions) // 3
    pos_acc = Accessor(
        bufferView=0, componentType=5126, count=n_vertices, type="VEC3",
        max=[max(positions[i::3]) for i in range(3)] if n_vertices > 0 else [0, 0, 0],
        min=[min(positions[i::3]) for i in range(3)] if n_vertices > 0 else [0, 0, 0],
    )
    norm_acc = Accessor(bufferView=1, componentType=5126, count=n_vertices, type="VEC3")
    idx_acc = Accessor(bufferView=2, componentType=ctype, count=len(indices), type="SCALAR")

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
    return b"".join(gltf.save_to_bytes())


def export_glb_base64(model: GearModel, deflection: float = 0.3) -> str:
    glb_bytes = export_glb_bytes(model, deflection)
    return base64.b64encode(glb_bytes).decode("ascii")

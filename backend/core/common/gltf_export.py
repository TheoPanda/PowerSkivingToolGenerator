"""通用几何 → GLB 导出器（非实体：曲面片 / 空间曲线 / 点云）.

单一职责：把任意几何体列表（三角网格 / 有序折线 / 点云）打包成 GLB。
区别于 workpiece/exporter.py（专供模块① 实体 GearModel）；本模块供模块②
的产形面 / 前刀面 / 刃形 / 后刀面等非实体几何可视化（子 PRD-1 能力前置）。

每个 GeometrySpec 对应 glTF 一个 mesh + 一个 node；node.name 写入 layer_id
（仅作调试标签——前端 addLayer 显式传 id 识别，不解析 node.name，ADR-018）。
"""

import base64
import struct
from dataclasses import dataclass
from typing import Sequence

# glTF 2.0 primitive mode：0=POINTS, 3=LINE_STRIP, 4=TRIANGLES
_PRIMITIVE_MODE = {"points": 0, "line": 3, "mesh": 4}


@dataclass
class GeometrySpec:
    """一个待导出的非实体几何体."""

    kind: str  # 'mesh' | 'line' | 'points'
    positions: list[float]  # 扁平 [x0,y0,z0, x1,y1,z1, ...]
    indices: list[int] | None = None  # mesh 三角形索引（line/points 忽略）
    normals: list[float] | None = None  # 可选顶点法向（扁平，与 positions 等长）
    layer_id: str | None = None  # 写入 node.name（调试标签）


def _pad4(b: bytes) -> bytes:
    """按 glTF 要求 4 字节对齐."""
    while len(b) % 4 != 0:
        b += b"\x00"
    return b


def export_geometry_glb(geometries: Sequence[GeometrySpec]) -> bytes:
    """把几何体列表打包成 GLB bytes（每项一个 mesh + 一个 node）."""
    from pygltflib import (
        GLTF2, Buffer, BufferView, Accessor, Mesh, Node, Scene,
        Primitive, Attributes, Asset,
    )

    if not geometries:
        raise ValueError("geometries 不能为空")

    gltf = GLTF2()
    gltf.asset = Asset(version="2.0")

    buffer_data = bytearray()
    buffer_views: list[BufferView] = []
    accessors: list[Accessor] = []
    meshes: list[Mesh] = []
    nodes: list[Node] = []

    for gi, geo in enumerate(geometries):
        if geo.kind not in _PRIMITIVE_MODE:
            raise ValueError(f"未知 kind: {geo.kind}")
        n_vertices = len(geo.positions) // 3
        if n_vertices == 0:
            raise ValueError(f"geometry[{gi}] positions 为空")

        # ── positions（必） ──
        pos_bytes = _pad4(struct.pack(f"<{len(geo.positions)}f", *geo.positions))
        pos_bv_index = len(buffer_views)
        buffer_views.append(BufferView(buffer=0, byteOffset=len(buffer_data), byteLength=len(pos_bytes)))
        buffer_data += pos_bytes
        accessors.append(Accessor(
            bufferView=pos_bv_index, componentType=5126, count=n_vertices, type="VEC3",
            max=[max(geo.positions[i::3]) for i in range(3)],
            min=[min(geo.positions[i::3]) for i in range(3)],
        ))
        attr_kwargs = {"POSITION": len(accessors) - 1}

        # ── normals（可选） ──
        if geo.normals is not None and len(geo.normals) > 0:
            nrm_bytes = _pad4(struct.pack(f"<{len(geo.normals)}f", *geo.normals))
            nrm_bv_index = len(buffer_views)
            buffer_views.append(BufferView(buffer=0, byteOffset=len(buffer_data), byteLength=len(nrm_bytes)))
            buffer_data += nrm_bytes
            accessors.append(Accessor(bufferView=nrm_bv_index, componentType=5126, count=n_vertices, type="VEC3"))
            attr_kwargs["NORMAL"] = len(accessors) - 1

        # ── indices（可选，mesh 用） ──
        primitive_indices: int | None = None
        if geo.indices is not None and len(geo.indices) > 0:
            use_uint16 = max(geo.indices) < 65536
            fmt = "H" if use_uint16 else "I"
            idx_bytes = _pad4(struct.pack(f"<{len(geo.indices)}{fmt}", *geo.indices))
            idx_bv_index = len(buffer_views)
            buffer_views.append(BufferView(buffer=0, byteOffset=len(buffer_data), byteLength=len(idx_bytes)))
            buffer_data += idx_bytes
            accessors.append(Accessor(
                bufferView=idx_bv_index,
                componentType=5123 if use_uint16 else 5125,
                count=len(geo.indices), type="SCALAR",
            ))
            primitive_indices = len(accessors) - 1

        primitive = Primitive(
            attributes=Attributes(**attr_kwargs),
            indices=primitive_indices,
            mode=_PRIMITIVE_MODE[geo.kind],
        )
        meshes.append(Mesh(primitives=[primitive]))
        nodes.append(Node(mesh=len(meshes) - 1, name=geo.layer_id))

    gltf.buffers = [Buffer(byteLength=len(buffer_data))]
    gltf.bufferViews = buffer_views
    gltf.accessors = accessors
    gltf.meshes = meshes
    gltf.nodes = nodes
    gltf.scenes = [Scene(nodes=list(range(len(nodes))))]
    gltf.scene = 0

    gltf.set_binary_blob(bytes(buffer_data))
    return b"".join(gltf.save_to_bytes())


def export_geometry_glb_base64(geometries: Sequence[GeometrySpec]) -> str:
    """导出 GLB 并 base64 编码（供 HTTP JSON 传输）."""
    return base64.b64encode(export_geometry_glb(geometries)).decode("ascii")

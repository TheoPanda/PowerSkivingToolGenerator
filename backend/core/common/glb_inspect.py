"""GLB 网格顶点的逆向解码（测试辅助）.

单一职责：把 gltf_export.export_geometry_glb 产出的 GLB bytes 解码回 POSITION
顶点数组，供 envelope 测试做坐标级断言（评审 Duplicated Code 收口——此前
test_envelope/test_tooth_solid 各持一份逐行相同的私有实现）。

只依赖 pygltflib + numpy（不依赖 OCCT），与子 PRD-2「纯 Python 可入 CI」一致。
"""

import numpy as np


def glb_positions(glb_bytes: bytes, mesh_index: int = 0) -> np.ndarray:
    """解出 GLB 第 mesh_index 个 mesh 的 POSITION 顶点（float32 → float64 (n,3)）."""
    from pygltflib import GLTF2

    g = GLTF2.load_from_bytes(glb_bytes)
    prim = g.meshes[mesh_index].primitives[0]
    acc = g.accessors[prim.attributes.POSITION]
    bv = g.bufferViews[acc.bufferView]
    off = bv.byteOffset or 0
    raw = g.binary_blob()[off : off + bv.byteLength]
    return np.frombuffer(raw, dtype=np.float32, count=acc.count * 3).reshape(-1, 3).astype(np.float64)

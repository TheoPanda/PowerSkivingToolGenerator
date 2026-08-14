"""gltf_export 非实体导出测试 — 纯 Python（不依赖 OCCT，可入 CI）.

验收（票 #22）：
- 曲线 primitive mode = LINE_STRIP(3)，顶点有序；
- 点云 mode = POINTS(0)；
- 曲面片 mode = TRIANGLES(4) 且带 indices；
- node.name 写入图层 id。
"""

from pygltflib import GLTF2

from core.common.gltf_export import GeometrySpec, export_geometry_glb


def _line() -> GeometrySpec:
    return GeometrySpec(
        kind="line",
        positions=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0],
        layer_id="edge",
    )


def _points() -> GeometrySpec:
    return GeometrySpec(
        kind="points",
        positions=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        layer_id="swept_cloud",
    )


def _mesh() -> GeometrySpec:
    return GeometrySpec(
        kind="mesh",
        positions=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        indices=[0, 1, 2],
        normals=[0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
        layer_id="flank",
    )


class TestExportGeometryGlb:
    def test_glb_magic(self):
        blob = export_geometry_glb([_mesh()])
        assert blob[:4] == b"glTF"

    def test_line_mode_is_line_strip(self):
        blob = export_geometry_glb([_line()])
        gltf = GLTF2.load_from_bytes(blob)
        assert gltf.meshes[0].primitives[0].mode == 3  # LINE_STRIP
        # 无 indices（折线自带顺序）
        assert gltf.meshes[0].primitives[0].indices is None

    def test_points_mode_is_points(self):
        blob = export_geometry_glb([_points()])
        gltf = GLTF2.load_from_bytes(blob)
        assert gltf.meshes[0].primitives[0].mode == 0  # POINTS

    def test_mesh_mode_is_triangles_with_indices(self):
        blob = export_geometry_glb([_mesh()])
        gltf = GLTF2.load_from_bytes(blob)
        prim = gltf.meshes[0].primitives[0]
        assert prim.mode == 4  # TRIANGLES
        assert prim.indices is not None
        assert prim.attributes.NORMAL is not None

    def test_node_name_carries_layer_id(self):
        blob = export_geometry_glb([_line(), _points(), _mesh()])
        gltf = GLTF2.load_from_bytes(blob)
        names = [n.name for n in gltf.nodes]
        assert names == ["edge", "swept_cloud", "flank"]
        assert len(gltf.scenes[0].nodes) == 3

    def test_vertex_count_preserved(self):
        blob = export_geometry_glb([_line()])
        gltf = GLTF2.load_from_bytes(blob)
        pos_acc = gltf.accessors[gltf.meshes[0].primitives[0].attributes.POSITION]
        assert pos_acc.count == 3  # 三个顶点

    def test_empty_geometries_raises(self):
        import pytest
        with pytest.raises(ValueError):
            export_geometry_glb([])

    def test_unknown_kind_raises(self):
        import pytest
        with pytest.raises(ValueError):
            export_geometry_glb([GeometrySpec(kind="bogus", positions=[0.0, 0.0, 0.0])])

    def test_colors_written_as_color_0(self):
        blob = export_geometry_glb([GeometrySpec(
            kind="mesh",
            positions=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            indices=[0, 1, 2],
            colors=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
        )])
        gltf = GLTF2.load_from_bytes(blob)
        prim = gltf.meshes[0].primitives[0]
        assert prim.attributes.COLOR_0 is not None
        color_acc = gltf.accessors[prim.attributes.COLOR_0]
        assert color_acc.count == 3  # 每顶点一个 VEC3
        assert color_acc.type == "VEC3"

    def test_lines_mode_is_lines_with_indices(self):
        blob = export_geometry_glb([GeometrySpec(
            kind="lines",
            positions=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0],
            indices=[0, 1, 2, 3],
        )])
        gltf = GLTF2.load_from_bytes(blob)
        prim = gltf.meshes[0].primitives[0]
        assert prim.mode == 1  # LINES
        assert prim.indices is not None

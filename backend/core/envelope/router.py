"""模块② 包络计算路由.

当前仅提供占位演示端点（子 PRD-1 多图层能力验证），真实包络算法
（K-2.x 前刀面/刃形/后刀面）留待子 PRD-2/3/4/5 落地。
"""

from fastapi import APIRouter

from core.common.gltf_export import GeometrySpec, export_geometry_glb_base64

router = APIRouter(prefix="/api/envelope", tags=["envelope"])


def _demo_geometries() -> list[GeometrySpec]:
    """占位假图层（与真实包络几何同构，仅形状为占位；GLB 坐标为刀具动系 T，Z 轴为轴向）."""
    # 产形面占位：一片半透明品牌蓝（x-z 平面展开）
    generatrix = GeometrySpec(
        kind="mesh",
        positions=[
            -15.0, 0.0, -15.0,
            15.0, 0.0, -15.0,
            15.0, 0.0, 15.0,
            -15.0, 0.0, 15.0,
        ],
        indices=[0, 1, 2, 0, 2, 3],
        normals=[0.0, 1.0, 0.0] * 4,
        layer_id="generatrix",
    )
    # 刃形占位：一条折线（深色高亮）
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
    # 后刀面占位：另一片硬质合金深灰（略下移）
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
    return [generatrix, edge, flank]


@router.post("/demo")
def envelope_demo() -> dict:
    """返回占位假图层的 GLB（产形面/刃形/后刀面），供前端多图层能力演示."""
    layers = [
        {"id": geo.layer_id, "glb_base64": export_geometry_glb_base64([geo])}
        for geo in _demo_geometries()
    ]
    return {"layers": layers}

"""通用三角网顶点法向 — 面积加权面法向平均（纯数学，无 OCCT）.

单一职责：给定扁平三角网（positions + indices），算出面积加权的逐顶点单位法向。
供模块②（扫掠点云 / 产形面 / 等效产形齿轮 / 后刀面）复用，未来模块③ solid /
模块④ simulation 亦可用。区别于 transforms.py（坐标变换）——本模块是网格几何工具。

向量化计算（np.cross 批量叉积 + np.add.at 累加），不触发方阵乘法崩溃
（numpy 2.5.0 + Python 3.14 规避纪律，见 core.common.transforms）。
"""

import numpy as np


def compute_vertex_normals(positions: list[float], indices: list[int]) -> list[float]:
    """三角网顶点法向（面积加权面法向平均），返回与 positions 等长的扁平法向.

    Args:
        positions: 扁平顶点 [x0,y0,z0, x1,y1,z1, ...]，n 个顶点
        indices: 三角网索引（长度 = 3×三角形数），每 3 个一组 (a,b,c)

    Returns:
        [nx0,ny0,nz0, ...] 单位法向，与 positions 等长；未被索引引用的顶点（或
        空输入）法向为 0。
    """
    n_vertices = len(positions) // 3
    if n_vertices == 0:
        return []
    pts = np.array(positions, dtype=np.float64).reshape(-1, 3)
    idx = np.array(indices, dtype=np.int64).reshape(-1, 3)  # (T, 3)
    v0 = pts[idx[:, 0]]
    v1 = pts[idx[:, 1]]
    v2 = pts[idx[:, 2]]
    face_normals = np.cross(v1 - v0, v2 - v0)  # (T, 3) 面法向（模 ∝ 2×面积）
    normals = np.zeros((n_vertices, 3), dtype=np.float64)
    np.add.at(normals, idx[:, 0], face_normals)
    np.add.at(normals, idx[:, 1], face_normals)
    np.add.at(normals, idx[:, 2], face_normals)
    lens = np.linalg.norm(normals, axis=1, keepdims=True)
    lens[lens < 1e-12] = 1.0
    normals = normals / lens
    return normals.reshape(-1).tolist()

"""通用三角网顶点法向（compute_vertex_normals）测试 — 纯数学，可入 CI."""

import math

import pytest

from core.common.mesh import compute_vertex_normals


def _flat(pts):
    """[(x,y,z), ...] → [x0,y0,z0, ...]."""
    return [v for p in pts for v in p]


class TestComputeVertexNormals:
    def test_single_triangle_normal(self):
        """单三角形：顶点法向 = 面法向（+Z，CCW 绕序），单位化."""
        positions = _flat([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        indices = [0, 1, 2]
        normals = compute_vertex_normals(positions, indices)
        assert len(normals) == 9  # 3 顶点 × 3 分量
        for i in range(3):
            n = normals[3 * i:3 * i + 3]
            assert math.hypot(n[0], n[1], n[2]) == pytest.approx(1.0)
            assert n[2] == pytest.approx(1.0)  # +Z

    def test_unit_normals_quad(self):
        """两三角四边形：所有被引用顶点法向模 ≈1."""
        positions = _flat([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]])
        indices = [0, 1, 2, 0, 2, 3]
        normals = compute_vertex_normals(positions, indices)
        for i in range(0, len(normals), 3):
            L = math.hypot(normals[i], normals[i + 1], normals[i + 2])
            assert L == pytest.approx(1.0)

    def test_empty_input_returns_empty(self):
        """空输入返回空列表（空保护）."""
        assert compute_vertex_normals([], []) == []

    def test_unreferenced_vertex_zero(self):
        """未被索引引用的顶点法向为 0（无害，与 swept_cloud 旧版语义一致）."""
        positions = _flat([[0, 0, 0], [1, 0, 0], [0, 1, 0], [9, 9, 9]])  # 顶点 3 未引用
        indices = [0, 1, 2]
        normals = compute_vertex_normals(positions, indices)
        for i in range(3):
            L = math.hypot(normals[3 * i], normals[3 * i + 1], normals[3 * i + 2])
            assert L == pytest.approx(1.0)
        assert normals[9:12] == [0.0, 0.0, 0.0]

    def test_area_weighted_average(self):
        """面积加权：共享顶点法向偏向大面积面（+Z 大面主导 −Z 小面）."""
        # 大面 (0,1,2)：叉积 +Z 面积 5；小面 (0,1,3)：叉积 −Z 面积 0.05
        positions = _flat([[0, 0, 0], [1, 0, 0], [0, 10, 0], [0, -0.1, 0]])
        indices = [0, 1, 2, 0, 1, 3]
        normals = compute_vertex_normals(positions, indices)
        n0 = normals[0:3]  # 顶点 0 法向
        assert n0[2] > 0.0  # 大面 +Z 主导

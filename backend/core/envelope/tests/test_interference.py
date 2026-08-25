"""模块②b 符号距离工具（point-in-polygon / 工程色阶 / 全周向折叠）测试 — 纯数学，可入 CI."""

import math

import numpy as np
import pytest

from core.envelope.interference import (
    _point_in_polygon,
    interference_color,
    neutral_gray_color,
    signed_distance_full_ring,
)


class TestPointInPolygon:
    def test_inside_outside(self):
        poly = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]])
        pts = np.array([[1.0, 1.0], [3.0, 3.0], [-1.0, 1.0]])
        inside = _point_in_polygon(poly, pts)
        assert inside[0] and not inside[1] and not inside[2]


class TestFullRing:
    """全周向折叠判定：解析折叠 + 内齿轮径向语义."""

    def _gear_poly(self):
        """合成内齿轮单齿槽多边形：r∈[10,12] 带内、角窗 ±5°（绕 x 轴）."""
        a0, a1 = math.radians(-5.0), math.radians(5.0)
        pts = []
        for k in range(6):
            a = a0 + (a1 - a0) * k / 5
            pts.append([10.0 * math.cos(a), 10.0 * math.sin(a)])
        for k in range(6):
            a = a1 - (a1 - a0) * k / 5
            pts.append([12.0 * math.cos(a), 12.0 * math.sin(a)])
        return np.array(pts)

    def test_slot_center_positive(self):
        poly = self._gear_poly()
        d = signed_distance_full_ring(np.array([[11.0, 0.0]]), poly, 20)
        assert d[0] > 0

    def test_tooth_body_negative(self):
        """齿体中点（槽中点 + 半齿距）→ 负（材料侵入）."""
        poly = self._gear_poly()
        pitch = 2 * math.pi / 20
        d = signed_distance_full_ring(
            np.array([[11.0 * math.cos(pitch / 2), 11.0 * math.sin(pitch / 2)]]), poly, 20
        )
        assert d[0] < 0

    def test_adjacent_slot_folds_to_positive(self):
        """相邻齿槽中心（+1 齿距）折叠后与基准槽等价 → 正."""
        poly = self._gear_poly()
        pitch = 2 * math.pi / 20
        d = signed_distance_full_ring(
            np.array([[11.0 * math.cos(pitch), 11.0 * math.sin(pitch)]]), poly, 20
        )
        assert d[0] > 0
        assert d[0] == pytest.approx(
            signed_distance_full_ring(np.array([[11.0, 0.0]]), poly, 20)[0], abs=1e-12
        )

    def test_bore_free_region_positive(self):
        """内孔自由区（r < r_a）→ 正（刀具合法通过）."""
        poly = self._gear_poly()
        d = signed_distance_full_ring(np.array([[5.0, 0.0]]), poly, 20)
        assert d[0] > 0

    def test_ring_body_negative(self):
        """环坯深处（r > r_f）→ 负（真干涉）."""
        poly = self._gear_poly()
        d = signed_distance_full_ring(np.array([[15.0, 0.0]]), poly, 20)
        assert d[0] < 0


class TestInterferenceColor:
    """工程色阶：红=干涉/橙黄=临界/绿→蓝=间隙（替代旧红白蓝）."""

    def test_saturated_colors(self):
        d = np.array([-1.0, 0.0, 1.0])
        col = interference_color(d, 1.0)
        # 干涉饱和 → 深红（r 高 g/b 低）
        assert col[0][0] > 0.8 and col[0][1] < 0.2 and col[0][2] < 0.2
        # 相切 → 绿（GO 色，g 占优）
        assert col[1][1] > 0.7 and col[1][0] < 0.2
        # 大间隙 → 蓝
        assert col[2][2] > 0.6 and col[2][0] < 0.2

    def test_no_white_band(self):
        """旧白接触带已废：任何 d 都不应接近纯白（rgb 全 >0.9）."""
        d = np.linspace(-1, 1, 101)
        col = interference_color(d, 1.0)
        white = (col[:, 0] > 0.9) & (col[:, 1] > 0.9) & (col[:, 2] > 0.9)
        assert not white.any()

    def test_clamped_range(self):
        d = np.array([-5.0, 5.0])
        col = interference_color(d, 0.5)
        assert (col >= 0.0).all() and (col <= 1.0).all()

    def test_neutral_gray(self):
        col = neutral_gray_color(3)
        assert col.shape == (3, 3)
        assert np.allclose(col[:, 0], 0.62)

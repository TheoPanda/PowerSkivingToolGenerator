"""GLB 导出器回归测试 — winding / 流形 / 体积 / 齿廓形状 / GLB 有效性.

exporter 消费 GearModel (builder 产出), 不自行构建几何。
"""

import math

import pytest

from core.workpiece.builder import build_gear_model
from core.workpiece.exporter import _model_to_mesh, export_glb_bytes
from core.workpiece.models import GearParams
from core.workpiece.profile import sample_profile_points


@pytest.fixture
def spur_41() -> GearParams:
    """r_b > r_f 分支 (齿根带径向连接线)."""
    return GearParams(m_n=2.5, z_w=41, b_w=20.0)


@pytest.fixture
def spur_60() -> GearParams:
    """r_f > r_b 分支 (渐开线直达齿根)."""
    return GearParams(m_n=2.5, z_w=60, b_w=20.0)


@pytest.fixture
def spur_82() -> GearParams:
    """用户截图参数: z=82, m_n=2."""
    return GearParams(m_n=2.0, z_w=82, b_w=20.0)


def _vert(positions: list[float], i: int) -> tuple[float, float, float]:
    return (positions[3 * i], positions[3 * i + 1], positions[3 * i + 2])


def _welded_edge_counts(
    positions: list[float], indices: list[int]
) -> dict[tuple, int]:
    welded = [
        (round(positions[3 * i], 6), round(positions[3 * i + 1], 6), round(positions[3 * i + 2], 6))
        for i in range(len(positions) // 3)
    ]
    counts: dict[tuple, int] = {}
    for t in range(len(indices) // 3):
        a, b, c = indices[3 * t : 3 * t + 3]
        for e in ((welded[a], welded[b]), (welded[b], welded[c]), (welded[c], welded[a])):
            key = (min(e), max(e))
            counts[key] = counts.get(key, 0) + 1
    return counts


def _build(p: GearParams):
    """Helper: build model + run mesh pipeline."""
    return _model_to_mesh(build_gear_model(p))


# ── Winding / 法向一致性 ─────────────────────────────────────────────

class TestWindingNormals:
    @pytest.mark.parametrize("fixture_name", ["spur_41", "spur_60"])
    def test_winding_matches_declared_normals(self, request, fixture_name):
        p = request.getfixturevalue(fixture_name)
        positions, normals, indices = _build(p)
        for t in range(len(indices) // 3):
            a, b, c = indices[3 * t : 3 * t + 3]
            pa, pb, pc = _vert(positions, a), _vert(positions, b), _vert(positions, c)
            ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
            wx, wy, wz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
            gx = uy * wz - uz * wy
            gy = uz * wx - ux * wz
            gz = ux * wy - uy * wx
            dn = [
                (normals[3 * a + k] + normals[3 * b + k] + normals[3 * c + k]) / 3.0
                for k in range(3)
            ]
            assert gx * dn[0] + gy * dn[1] + gz * dn[2] > 0, (
                f"triangle {t} winding 与声明法向反向"
            )


# ── 闭合流形 ─────────────────────────────────────────────────────────

class TestClosedManifold:
    @pytest.mark.parametrize("fixture_name", ["spur_41", "spur_60"])
    def test_every_edge_shared_by_two_triangles(self, request, fixture_name):
        p = request.getfixturevalue(fixture_name)
        positions, _, indices = _build(p)
        counts = _welded_edge_counts(positions, indices)
        bad = {e: c for e, c in counts.items() if c != 2}
        assert not bad, f"{len(bad)} 条边非流形 (示例: {next(iter(bad.items()))})"


# ── 齿廓形状 ─────────────────────────────────────────────────────────

class TestProfileShape:
    @pytest.mark.parametrize("fixture_name", ["spur_41", "spur_60", "spur_82"])
    def test_profile_mirror_symmetry(self, request, fixture_name):
        p = request.getfixturevalue(fixture_name)
        boundary = sample_profile_points(p)
        orig = {(round(x, 7), round(y, 7)) for x, y in boundary}
        refl = {(round(x, 7), round(-y, 7)) for x, y in boundary}
        missing = refl - orig
        assert not missing, f"{len(missing)}/{len(refl)} 镜像点缺失 (右齿面未镜像?)"

    @pytest.mark.parametrize("fixture_name", ["spur_41", "spur_82"])
    def test_flank_angles_at_pitch_circle(self, request, fixture_name):
        p = request.getfixturevalue(fixture_name)
        boundary = sample_profile_points(p)
        r_pw = p.pitch_radius()
        m_t, _ = p.to_transverse()
        half_tooth_angle = (math.pi * m_t / 2.0 + 2.0 * p.x_w * p.m_n * math.tan(
            math.radians(p.to_transverse()[1]))) / (2.0 * r_pw)

        pitch = 2.0 * math.pi / p.z_w
        la = ra = None
        pairs = list(zip(boundary, boundary[1:] + boundary[:1]))
        for (x0, y0), (x1, y1) in pairs:
            r0, r1 = math.hypot(x0, y0), math.hypot(x1, y1)
            if (r0 - r_pw) * (r1 - r_pw) < 0:
                t = (r_pw - r0) / (r1 - r0)
                a0, a1 = math.atan2(y0, x0), math.atan2(y1, x1)
                if a1 - a0 > math.pi:
                    a1 -= 2 * math.pi
                if a0 - a1 > math.pi:
                    a0 -= 2 * math.pi
                a = a0 + t * (a1 - a0)
                if -pitch / 2 < a < 0:
                    la = a
                elif 0 < a < pitch / 2:
                    ra = a
        assert la is not None and ra is not None, "齿面采样未跨过节圆"
        assert abs(la + half_tooth_angle) < 2e-3, f"左齿面节圆极角 {la} ≠ {-half_tooth_angle}"
        assert abs(ra - half_tooth_angle) < 2e-3, f"右齿面节圆极角 {ra} ≠ {half_tooth_angle}"


# ── K-1.12 齿根圆角 ────────────────────────────────────────────────

class TestRootFillet:
    def test_fillet_present_when_rb_gt_rf(self):
        from core.workpiece.profile import Arc, gear_profile_segments
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0)
        assert p.base_radius() > p.root_radius()
        segs = gear_profile_segments(p)
        n_fillet = sum(1 for s in segs if isinstance(s, Arc) and s.clockwise)
        assert n_fillet == 2 * p.z_w, f"圆角弧数 {n_fillet} != 2*z_w"
        boundary = sample_profile_points(p)
        for (x0, y0), (x1, y1) in zip(boundary, boundary[1:] + boundary[:1]):
            dr = abs(math.hypot(x1, y1) - math.hypot(x0, y0))
            assert dr < 0.1, f"径向台阶残留: dr={dr:.3f}"

    def test_fillet_tangent_to_root_circle(self):
        from core.workpiece.profile import solve_root_fillet
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0)
        fil = solve_root_fillet(p)
        rho = p.rho_f * p.m_n
        assert abs(math.hypot(*fil.center_t) - (p.root_radius() + rho)) < 1e-6
        assert abs(math.hypot(*fil.tang_root_t) - p.root_radius()) < 1e-9
        assert math.hypot(*fil.tang_inv_t) >= p.base_radius() - 1e-9

    def test_no_fillet_when_rb_le_rf(self):
        from core.workpiece.profile import Arc, gear_profile_segments
        p = GearParams(m_n=2.5, z_w=60, b_w=20.0)
        assert p.root_radius() > p.base_radius()
        segs = gear_profile_segments(p)
        assert not any(isinstance(s, Arc) and s.clockwise for s in segs)

    def test_radial_fallback_when_no_double_tangent(self):
        from core.workpiece.profile import Arc, gear_profile_segments
        p = GearParams(m_n=3.0, z_w=20, b_w=15.0)
        assert p.base_radius() - p.root_radius() > p.rho_f * p.m_n
        segs = gear_profile_segments(p)
        assert not any(isinstance(s, Arc) and s.clockwise for s in segs)
        boundary = sample_profile_points(p)
        orig = {(round(x, 7), round(y, 7)) for x, y in boundary}
        refl = {(round(x, 7), round(-y, 7)) for x, y in boundary}
        assert not (refl - orig), "回退路径破坏镜像对称"


# ── 体积 ─────────────────────────────────────────────────────────────

class TestVolumeAndBounds:
    @pytest.mark.parametrize("fixture_name", ["spur_41", "spur_60"])
    def test_divergence_volume_within_bounds(self, request, fixture_name):
        p = request.getfixturevalue(fixture_name)
        positions, _, indices = _build(p)
        vol = 0.0
        for t in range(len(indices) // 3):
            a, b, c = indices[3 * t : 3 * t + 3]
            pa, pb, pc = _vert(positions, a), _vert(positions, b), _vert(positions, c)
            vol += (
                pa[0] * (pb[1] * pc[2] - pb[2] * pc[1])
                + pa[1] * (pb[2] * pc[0] - pb[0] * pc[2])
                + pa[2] * (pb[0] * pc[1] - pb[1] * pc[0])
            ) / 6.0
        r_f, r_a = p.root_radius(), p.tip_radius()
        lo = math.pi * r_f ** 2 * p.b_w
        hi = math.pi * r_a ** 2 * p.b_w
        assert lo < vol < hi, f"体积 {vol:.1f} 越界 [{lo:.1f}, {hi:.1f}]"

    @pytest.mark.parametrize("fixture_name", ["spur_41", "spur_60"])
    def test_vertices_within_radial_and_axial_bounds(self, request, fixture_name):
        p = request.getfixturevalue(fixture_name)
        positions, _, _ = _build(p)
        r_f, r_a = p.root_radius(), p.tip_radius()
        for i in range(len(positions) // 3):
            x, y, z = _vert(positions, i)
            r = math.hypot(x, y)
            assert r_f - 1e-6 <= r <= r_a + 1e-6, f"vertex {i} 半径 {r} 越界"
            assert z in (0.0, p.b_w), f"vertex {i} z={z} 不在端面"


# ── GLB 输出 ─────────────────────────────────────────────────────────

class TestGlbOutput:
    def test_glb_magic_and_parse(self, spur_41):
        model = build_gear_model(spur_41)
        blob = export_glb_bytes(model)
        assert blob[:4] == b"glTF"
        from pygltflib import GLTF2
        gltf = GLTF2.load_from_bytes(blob)
        assert len(gltf.meshes) == 1
        assert gltf.meshes[0].primitives[0].indices is not None

    def test_export_performance(self, spur_41):
        import time
        model = build_gear_model(spur_41)
        t0 = time.time()
        export_glb_bytes(model)
        assert time.time() - t0 < 5.0, f"导出超时"

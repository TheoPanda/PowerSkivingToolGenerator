"""GLB 导出器回归测试 — winding / 流形 / 体积 / 齿廓形状 / GLB 有效性.

exporter 消费 GearModel (builder 产出), 不自行构建几何。
"""

import math

import pytest

from core.workpiece.builder import build_gear_model
from core.workpiece.exporter import _model_to_mesh, export_glb_bytes
from core.workpiece.models import GearParams
from core.workpiece.profile import Arc, Polyline, sample_profile_points


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


# ── 冻结基线: 默认路径零变化门禁 (票 #11 AC#1, abs=1e-12) ─────────────
# 参考齿 m=1.0, z=32, b=20, 默认 root_fillet=True: r_b > r_f, 含左右齿根圆角
# (2 个 CW 弧)。golden = tooth_segments(p, 0) 全精度 (round 12) 序列化,
# 在 T01 实现时捕获; T02/T03 改动 _tooth_open_segments 时不得使默认输出漂移。
GOLDEN_DEFAULT_TOOTH_0: list[tuple] = [
    ("arc", 0.38, 3.052798245424, 1.59407396051, 15.070393338279, -1.34169468567, True),
    ("poly", ((15.061548636265, -0.961797632185), (15.076900458514, -0.961353967058), (15.094067742586, -0.960668787402), (15.1130468105, -0.959702070639), (15.133833323149, -0.958413848333), (15.156422281079, -0.956764215894), (15.180808025395, -0.954713342278), (15.206984238796, -0.952221479663), (15.234943946756, -0.949248973117), (15.264679518822, -0.945756270254), (15.296182670063, -0.941703930861), (15.32944446263, -0.937052636519), (15.364455307472, -0.931763200189), (15.401204966163, -0.925796575786), (15.439682552875, -0.919113867723), (15.479876536475, -0.91167634043), (15.521774742755, -0.903445427842), (15.565364356795, -0.89438274286), (15.610631925455, -0.88445008678), (15.657563359992, -0.873609458688), (15.706143938815, -0.861823064819), (15.756358310362, -0.84905332788), (15.808190496109, -0.835262896334), (15.861623893707, -0.820414653645), (15.916641280245, -0.80447172748), (15.973224815641, -0.787397498863), (16.031356046157, -0.769155611296), (16.091015908044, -0.749709979819), (16.152184731309, -0.729024800028), (16.214842243609, -0.707064557043), (16.278967574262, -0.683794034423), (16.344539258395, -0.659178323029), (16.411535241197, -0.633182829826), (16.479932882309, -0.605773286636), (16.549708960327, -0.576915758825), (16.620839677426, -0.546576653939), (16.693300664104, -0.514722730267), (16.767066984049, -0.481321105353), (16.842113139117, -0.44633926443), (16.91841307443, -0.409745068801), (16.995940183591, -0.371506764139))),
    ("arc", 17.0, -0.021855078852, 0.021855078852, 0.0, 0.0, False),
    ("poly", ((16.995940183591, 0.371506764139), (16.91841307443, 0.409745068801), (16.842113139117, 0.44633926443), (16.767066984049, 0.481321105353), (16.693300664104, 0.514722730267), (16.620839677426, 0.546576653939), (16.549708960327, 0.576915758825), (16.479932882309, 0.605773286636), (16.411535241197, 0.633182829826), (16.344539258395, 0.659178323029), (16.278967574262, 0.683794034423), (16.214842243609, 0.707064557043), (16.152184731309, 0.729024800028), (16.091015908044, 0.749709979819), (16.031356046157, 0.769155611296), (15.973224815641, 0.787397498863), (15.916641280245, 0.80447172748), (15.861623893707, 0.820414653645), (15.808190496109, 0.835262896334), (15.756358310362, 0.84905332788), (15.706143938815, 0.861823064819), (15.657563359992, 0.873609458688), (15.610631925455, 0.88445008678), (15.565364356795, 0.89438274286), (15.521774742755, 0.903445427842), (15.479876536475, 0.91167634043), (15.439682552875, 0.919113867723), (15.401204966163, 0.925796575786), (15.364455307472, 0.931763200189), (15.32944446263, 0.937052636519), (15.296182670063, 0.941703930861), (15.264679518822, 0.945756270254), (15.234943946756, 0.949248973117), (15.206984238796, 0.952221479663), (15.180808025395, 0.954713342278), (15.156422281079, 0.956764215894), (15.133833323149, 0.958413848333), (15.1130468105, 0.959702070639), (15.094067742586, 0.960668787402), (15.076900458514, 0.961353967058), (15.061548636265, 0.961797632185))),
    ("arc", 0.38, -1.59407396051, -3.052798245424, 15.070393338279, 1.34169468567, True),
    ("arc", 14.75, 0.088794408166, 0.107555132683, 0.0, 0.0, False),
]


def _canon_seg(s) -> tuple:
    """段 → 全精度规范元组 (round 12)，供 golden 逐点比对."""
    if isinstance(s, Arc):
        return ("arc", round(s.radius, 12), round(s.a0, 12), round(s.a1, 12),
                round(s.center[0], 12), round(s.center[1], 12), s.clockwise)
    return ("poly", tuple((round(x, 12), round(y, 12)) for x, y in s.points))


def _seg_close(a: tuple, b: tuple, tol: float = 1e-12) -> bool:
    """两规范段在 tol 内一致 (golden 全精度 12 位, 舍入误差 ≤5e-13 < tol)."""
    if a[0] != b[0]:
        return False
    if a[0] == "arc":
        return a[6] == b[6] and all(abs(x - y) <= tol for x, y in zip(a[1:6], b[1:6]))
    pa, pb = a[1], b[1]
    return len(pa) == len(pb) and all(
        abs(x - u) <= tol and abs(y - v) <= tol for (x, y), (u, v) in zip(pa, pb)
    )


def _ang_norm(a: float) -> float:
    """归一化角到 (−π, π]."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _tangent_angle(segs: list, idx: int, at_end: bool) -> float:
    """段 idx 在端点 (at_end=True 终点 / False 起点) 的切线角 [rad]."""
    s = segs[idx]
    if isinstance(s, Polyline):
        if at_end:
            a, b = s.points[-2], s.points[-1]
        else:
            a, b = s.points[0], s.points[1]
        return math.atan2(b[1] - a[1], b[0] - a[0])
    # Arc: 切线 = 半径方向顺时针/逆时针 90°
    ang = s.a1 if at_end else s.a0
    return (ang - math.pi / 2.0) if s.clockwise else (ang + math.pi / 2.0)


def _g1_breaks(segs: list) -> tuple[bool, int | None, float | None, float | None]:
    """相邻段连接处切线角连续性 (G1, mod 2π, 容差 1e-6)."""
    for i in range(len(segs) - 1):
        t_end = _tangent_angle(segs, i, at_end=True)
        t_start = _tangent_angle(segs, i + 1, at_end=False)
        if abs(_ang_norm(t_end - t_start)) > 1e-6:
            return False, i, t_end, t_start
    return True, None, None, None


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

    def test_fillet_present_when_rb_le_rf(self):
        """r_b <= r_f (无根切高齿数): 齿面-齿根圆连接角圆角双切解仍存在 (K-1.12 扩展)."""
        from core.workpiece.profile import Arc, gear_profile_segments, sample_profile_points
        p = GearParams(m_n=2.5, z_w=60, b_w=20.0)
        assert p.root_radius() > p.base_radius()
        segs = gear_profile_segments(p)
        n_fillet = sum(1 for s in segs if isinstance(s, Arc) and s.clockwise)
        assert n_fillet == 2 * p.z_w, f"圆角弧数 {n_fillet} != 2*z_w"
        boundary = sample_profile_points(p)
        r_f, r_a = p.root_radius(), p.tip_radius()
        for x, y in boundary:
            r = math.hypot(x, y)
            assert r_f - 1e-6 <= r <= r_a + 1e-6, f"采样点半径 {r} 越界"

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

    def test_no_fillet_when_root_fillet_disabled(self):
        """root_fillet=False 强制锐齿根（无圆角弧），回退几何保持对称与连续."""
        from core.workpiece.profile import Arc, gear_profile_segments, sample_profile_points
        # r_b > r_f 且圆角本应有解，但 root_fillet=False 走无圆角回退路径
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0, root_fillet=False)
        assert p.base_radius() > p.root_radius()
        segs = gear_profile_segments(p)
        assert not any(isinstance(s, Arc) and s.clockwise for s in segs), \
            "root_fillet=False 不应包含齿根圆角弧"
        boundary = sample_profile_points(p)
        orig = {(round(x, 7), round(y, 7)) for x, y in boundary}
        refl = {(round(x, 7), round(-y, 7)) for x, y in boundary}
        assert not (refl - orig), "root_fillet=False 破坏镜像对称"
        # 无圆角走径向回退 (r_b→r_f 径向线, 固有径向台阶, 不判 dr):
        # 采样点径向范围须在 [r_f, r_a] 内 (无越界缺口)
        r_f = p.root_radius()
        r_a = p.tip_radius()
        for x, y in boundary:
            r = math.hypot(x, y)
            assert r_f - 1e-6 <= r <= r_a + 1e-6, f"点半径 {r} 越界 [{r_f}, {r_a}]"

    def test_default_path_zero_change_golden(self):
        """T01 门禁 (票 #11 AC#1): 默认参数输出与冻结基线逐点一致 (abs=1e-12).

        参考齿 m=1, z=32 (r_b > r_f, 齿根圆角分支在测, 2 个 CW 圆角弧)。
        冻结基线在 T01 实现时捕获; T02/T03 改动 _tooth_open_segments 时此测试防默认路径漂移。
        """
        from core.workpiece.profile import tooth_segments
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0)
        assert p.base_radius() > p.root_radius()
        canon = [_canon_seg(s) for s in tooth_segments(p, 0)]
        assert len(canon) == len(GOLDEN_DEFAULT_TOOTH_0), \
            f"默认路径段数漂移: {len(canon)} vs {len(GOLDEN_DEFAULT_TOOTH_0)}"
        for a, b in zip(canon, GOLDEN_DEFAULT_TOOTH_0):
            assert _seg_close(a, b), f"默认路径逐点漂移:\n  {a}\n  {b}"


# ── T02: 齿顶圆角 (tip_mode='round', ρ*_tip>0) ───────────────────────

class TestTipRound:
    """T02 齿顶圆角: 凸角双切圆角, 齿面/齿顶 G1 连续, 采样不越界."""

    def test_tip_round_g1_and_no_overshoot(self):
        """tip_mode='round' ρ*_tip=0.3: 圆角↔齿顶弧解析 G1, 齿面衔接离散容差, 采样不越界."""
        from core.workpiece.profile import Arc, tooth_segments
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0, tip_mode="round", rho_tip=0.3)
        segs = tooth_segments(p, 0)
        rho = p.rho_tip * p.m_n
        r_a = p.tip_radius()
        tip_fillets = [
            s for s in segs
            if isinstance(s, Arc) and abs(s.radius - rho) < 1e-9 and s.center != (0.0, 0.0)
        ]
        assert len(tip_fillets) >= 2, f"齿顶圆角弧应 ≥2, 实得 {len(tip_fillets)}"

        # 齿顶弧 = 半径 r_a 且圆心原点; 其两侧必须是圆角弧
        tip_arcs = [s for s in segs if isinstance(s, Arc)
                    and abs(s.radius - r_a) < 1e-9 and s.center == (0.0, 0.0)]
        assert len(tip_arcs) == 1, f"齿顶弧应 1 段, 实得 {len(tip_arcs)}"
        idx = segs.index(tip_arcs[0])

        def _arc_pt(s, at_end):
            a = s.a1 if at_end else s.a0
            return (s.center[0] + s.radius * math.cos(a),
                    s.center[1] + s.radius * math.sin(a))

        # 圆角→齿顶弧 两连接点: 解析双圆切线精确连续 (tol 1e-6)
        assert abs(_ang_norm(_tangent_angle(segs, idx - 1, True)
                             - _tangent_angle(segs, idx, False))) < 1e-6
        assert abs(_ang_norm(_tangent_angle(segs, idx, True)
                             - _tangent_angle(segs, idx + 1, False))) < 1e-6
        # 圆角终点在齿顶圆上 (半径 r_a)
        tl = _arc_pt(segs[idx - 1], True)
        tr = _arc_pt(segs[idx + 1], False)
        assert abs(math.hypot(*tl) - r_a) < 1e-9
        assert abs(math.hypot(*tr) - r_a) < 1e-9
        # 齿面→圆角 衔接: 齿面为采样 polyline, 离散化容差 (1e-2)
        assert abs(_ang_norm(_tangent_angle(segs, idx - 2, True)
                             - _tangent_angle(segs, idx - 1, False))) < 1e-2
        assert abs(_ang_norm(_tangent_angle(segs, idx + 1, True)
                             - _tangent_angle(segs, idx + 2, False))) < 1e-2
        # 采样不越界
        boundary = sample_profile_points(p)
        r_f = p.root_radius()
        for x, y in boundary:
            r = math.hypot(x, y)
            assert r_f - 1e-6 <= r <= r_a + 1e-6, f"采样点半径 {r} 越界"

    def test_tip_round_zero_change_when_none(self):
        """默认 tip_mode='none' 输出与 T01 golden 逐点一致 (零变化)."""
        from core.workpiece.profile import tooth_segments
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0)  # tip_mode 默认 none
        canon = [_canon_seg(s) for s in tooth_segments(p, 0)]
        assert len(canon) == len(GOLDEN_DEFAULT_TOOTH_0)
        for a, b in zip(canon, GOLDEN_DEFAULT_TOOTH_0):
            assert _seg_close(a, b), f"tip_mode=none 默认路径漂移:\n  {a}\n  {b}"

    def test_tip_round_oversize_converges(self):
        """ρ*_tip 过大 → 收敛到可容纳上限 (采样点仍不越界)."""
        from core.workpiece.profile import tooth_segments
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0, tip_mode="round", rho_tip=5.0)
        segs = tooth_segments(p, 0)  # 不抛错, 收敛
        assert segs
        boundary = sample_profile_points(p)
        r_f, r_a = p.root_radius(), p.tip_radius()
        for x, y in boundary:
            r = math.hypot(x, y)
            assert r_f - 1e-6 <= r <= r_a + 1e-6, f"收敛后采样点半径 {r} 越界"


# ── T03: 齿顶倒角 (tip_mode='chamfer', 45° 沿齿面量取) ───────────────

class TestTipChamfer:
    """T03 齿顶倒角: 45° 直线段, 齿面/齿顶截断, 采样不越界, 镜像对称."""

    def test_chamfer_present_45deg_no_overshoot(self):
        """tip_mode='chamfer' c=0.05 (可行值): 齿顶弧两侧为倒角直线, 与齿面切线 45°, 采样不越界."""
        from core.workpiece.profile import Arc, Polyline, tooth_segments
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0, tip_mode="chamfer", chamfer_tip=0.05)
        segs = tooth_segments(p, 0)
        r_a = p.tip_radius()
        tip_arcs = [s for s in segs if isinstance(s, Arc)
                    and abs(s.radius - r_a) < 1e-9 and s.center == (0.0, 0.0)]
        assert len(tip_arcs) == 1, f"齿顶弧应 1 段, 实得 {len(tip_arcs)}"
        idx = segs.index(tip_arcs[0])
        # 齿顶弧两侧应为倒角直线段 (Polyline 2 点)
        assert isinstance(segs[idx - 1], Polyline) and len(segs[idx - 1].points) == 2
        assert isinstance(segs[idx + 1], Polyline) and len(segs[idx + 1].points) == 2
        # 倒角线与齿面切线成 45° (齿面为采样 polyline, 离散化容差 1e-2)
        for j in (idx - 1, idx + 1):
            cham = segs[j]
            c_dir = math.atan2(cham.points[1][1] - cham.points[0][1],
                               cham.points[1][0] - cham.points[0][0])
            flank = segs[j - 1 if j < idx else j + 1]
            if j < idx:
                f_dir = math.atan2(flank.points[-1][1] - flank.points[-2][1],
                                   flank.points[-1][0] - flank.points[-2][0])
            else:
                f_dir = math.atan2(flank.points[1][1] - flank.points[0][1],
                                   flank.points[1][0] - flank.points[0][0])
            assert abs(abs(_ang_norm(c_dir - f_dir)) - math.pi / 4.0) < 1e-2, \
                f"倒角线与齿面切线夹角 {abs(_ang_norm(c_dir - f_dir)):.4f} ≠ 45°"
        # 采样不越界 + 镜像对称
        boundary = sample_profile_points(p)
        r_f = p.root_radius()
        for x, y in boundary:
            r = math.hypot(x, y)
            assert r_f - 1e-6 <= r <= r_a + 1e-6, f"采样点半径 {r} 越界"
        orig = {(round(x, 7), round(y, 7)) for x, y in boundary}
        refl = {(round(x, 7), round(-y, 7)) for x, y in boundary}
        assert not (refl - orig), "倒角破坏镜像对称"

    def test_chamfer_oversize_converges(self):
        """c 过大 → 收敛到最大可行值 (采样点仍不越界, 不抛错)."""
        from core.workpiece.profile import tooth_segments, tip_chamfer_actual_mm
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0, tip_mode="chamfer", chamfer_tip=3.0)
        actual = tip_chamfer_actual_mm(p)
        assert 0 < actual < 3.0, f"c=3.0 应收敛到 (0, 3.0), 实得 {actual}"
        segs = tooth_segments(p, 0)
        assert segs
        boundary = sample_profile_points(p)
        r_f, r_a = p.root_radius(), p.tip_radius()
        for x, y in boundary:
            r = math.hypot(x, y)
            assert r_f - 1e-6 <= r <= r_a + 1e-6, f"收敛后采样点半径 {r} 越界"

    def test_chamfer_zero_change_when_none(self):
        """默认 tip_mode='none' 输出与 golden 逐点一致 (倒角不影响默认)."""
        from core.workpiece.profile import tooth_segments
        p = GearParams(m_n=1.0, z_w=32, b_w=20.0)
        canon = [_canon_seg(s) for s in tooth_segments(p, 0)]
        assert len(canon) == len(GOLDEN_DEFAULT_TOOTH_0)
        for a, b in zip(canon, GOLDEN_DEFAULT_TOOTH_0):
            assert _seg_close(a, b), f"默认路径漂移:\n  {a}\n  {b}"


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

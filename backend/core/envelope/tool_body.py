"""模块③ K-3.2 刀体结构预览级（ADR-021，2026-08-31）— 纯数学，不依赖 OCCT.

齿圈之外的支承本体：内孔 ± 端面键槽 + 前后端面 + 外缘圆柱。几何依据（规格
docs/specs/2026-08-31-tool-body-design.md）：

  - 外缘 = 齿圈谷底圆柱 r_root（ToothLoop.root_radius，派生只读——用户填了必与
    齿圈打架，故不入参数）；
  - 前端面 = 前刀面平面**按槽位折叠**（[23]§3.3② 内圈前端面平行规则）：理想平面
    会在斜齿/大γ下与「基准齿×z_t 纯旋转」的刀具整环产生十余毫米 z 相位错位
    （2026-08-31 用户实测「光滑透明椭球」根因）——前端面 z 按基准齿窗口折叠，
    逐扇区与前刀面平行，与整环阵列同一近似等级，重磨不挡屑规则保持；
  - 纯轴向直拉伸（键槽必须笔直——装键现实约束；斜齿不做螺旋扭转，与刀齿后端的
    微小错缝预览级接受，正式级布尔自然消解）；
  - 双闭环端面（外=谷底圆、内=孔圆±键槽缺口）**极角配对 quad-strip** 剖分：环形
    区域非简单多边形，build_tooth_loop 的单闭边界耳切（_ear_clip_indices）不适用；
    内外边界对中心均星形（键槽缺口向 +X 凸入材料侧），同一极角序列采样两条边界、
    逐角连四边形，键槽 4 个角点角（±θ_k 圆-壁交点、±θ_b 壁-底交点）精确入样。

尺寸依据（表驱动，REF-7 袁哲俊《齿轮刀具设计》插齿刀标准化数据，GB/T 6081 口径）：
  - 对档：内孔**向下取档**（≤2·r_pt 的最大公称分度圆档，低于 φ40 钳制 φ40 档）——
    孔小顶多重配刀杆，孔大刀体裂，安全侧（ADR-021 ⑤）；
  - 键槽深 = GB/T 6132 / ISO 240:2016 Table 1 跨距尺寸 t = c1 − d 按最近档
    （W16 已销，两处近似留档：部分档键宽与 GB/T 6081 的 b 不一致仅取深度值；
    GB/T 6081 自身深表公开网络未获取）。

坐标标签 T。碗形 φ50 档（孔 20）不入对档——装夹范围不含碗形（ADR-021 ④）。
"""

import math
from dataclasses import dataclass

from core.common.gltf_export import GeometrySpec
from core.common.mesh import compute_vertex_normals
from core.envelope.rake import RakeSurface

# ── 手册标准数据（REF-7 表 4-12~4-16 / 4-32 小模数 JB/T 3095；厚度表 4-7）──
# 每档：公称分度圆 φ [mm]、可选内孔、键槽宽按模数段 (m_n 上界, b)、标准厚度系列。
_SEGMENTS: list[dict] = [
    {"dia": 40.0, "bores": [15.875], "b": [(0.65, 6.0), (float("inf"), 7.0)], "B": [10.0, 12.0]},
    {"dia": 63.0, "bores": [31.743], "b": [(0.65, 6.0), (float("inf"), 7.0)], "B": [10.0, 12.0]},
    {"dia": 75.0, "bores": [31.743], "b": [(float("inf"), 10.0)], "B": [15.0, 17.0, 20.0]},
    {"dia": 100.0, "bores": [31.743, 44.443], "b": [(1.6, 10.0), (float("inf"), 12.0)], "B": [18.0, 22.0, 24.0]},
    {"dia": 125.0, "bores": [31.743, 44.443, 44.45], "b": [(float("inf"), 13.0)], "B": [30.0]},
    {"dia": 160.0, "bores": [88.9], "b": [(float("inf"), 18.0)], "B": [35.0]},
    {"dia": 200.0, "bores": [101.6], "b": [(float("inf"), 20.0)], "B": [40.0]},
]

# 键槽深（孔侧）GB/T 6132 / ISO 240:2016 Table 1 最近档：t = c1 − d [mm]（W16 已销）
_KEYWAY_DEPTH: dict[float, float] = {
    15.875: 1.7, 31.743: 2.8, 44.443: 3.5, 44.45: 3.5, 88.9: 5.5, 101.6: 7.0,
}

_MOUNTINGS = ("bore", "bore_keyway")


def select_segment(d_pt: float) -> dict:
    """向下取档：≤d_pt 的最大公称分度圆档；低于最小档钳制 φ40（ADR-021 ⑤ 安全侧）.

    Raises:
        ValueError: d_pt ≤ 0
    """
    if d_pt <= 0:
        raise ValueError(f"刀具分度圆直径 d_pt={d_pt:.4f} 必须 > 0")
    seg = _SEGMENTS[0]
    for cand in _SEGMENTS:
        if cand["dia"] <= d_pt:
            seg = cand
    return seg


def default_bore(seg: dict) -> float:
    """档内默认内孔 = 系列首值（主流孔径）."""
    return float(seg["bores"][0])


def default_keyway_b(seg: dict, m_n: float) -> float:
    """键槽宽按（档 × 模数段）带出（REF-7 结构尺寸表行段）."""
    for m_up, b in seg["b"]:
        if m_n <= m_up:
            return float(b)
    return float(seg["b"][-1][1])


def default_thickness(seg: dict, L: float) -> float | None:
    """默认厚度 = 档内标准系列中 ≥L 的最小值；全档 <L 返回 None（软警，放行非标由调用方定值）."""
    for b in seg["B"]:
        if b >= L:
            return float(b)
    return None


def keyway_depth_default(d_bore: float) -> float | None:
    """键槽深按 GB/T 6132 最近档；非系列孔径返回 None（调用方报错——非系列孔径本身硬拒）."""
    return _KEYWAY_DEPTH.get(float(d_bore))


@dataclass
class ToolBodyResolved:
    """表驱动解析后的刀体参数 + 软警（ADR-021 ④⑥）."""

    mounting: str
    d_bore: float
    keyway_b: float | None  # None = 光内孔
    keyway_t1: float | None
    B: float
    segment_dia: float          # 对档公称分度圆 [mm]
    thickness_is_standard: bool
    warnings: list[str]


def resolve_tool_body_params(
    *,
    mounting: str,
    d_pt: float,
    m_n: float,
    L: float,
    r_root: float,
    d_bore: float | None = None,
    keyway_b: float | None = None,
    keyway_t1: float | None = None,
    B: float | None = None,
) -> ToolBodyResolved:
    """表驱动解析 + 软硬校验（Q8/Q10 裁决；前端下拉预过滤，此处为后端二道闸）.

    硬校验（ValueError = 400）：mounting 非法 / 非系列孔径 / 键槽半宽 ≥ 孔半径 /
    孔缘含键槽底越谷底圆 / B < L。软偏离（warnings）：厚度非当前档标准值。
    """
    if mounting not in _MOUNTINGS:
        raise ValueError(f"装夹形式 mounting={mounting!r} 不支持（可选：{'/'.join(_MOUNTINGS)}）")
    if L <= 0:
        raise ValueError(f"总重磨量 L={L:.4f} 必须 > 0")

    seg = select_segment(d_pt)
    bore = default_bore(seg) if d_bore is None else float(d_bore)
    if bore not in seg["bores"]:
        raise ValueError(
            f"内孔直径 d_bore={bore} 不在 φ{seg['dia']:.0f} 档标准系列 "
            f"{seg['bores']} 内（对档：向下取档，d_pt={d_pt:.3f}）"
        )
    if bore / 2.0 >= r_root:
        raise ValueError(f"孔缘越谷底圆：r_bore={bore / 2.0:.3f} ≥ r_root={r_root:.3f}")

    has_key = mounting == "bore_keyway"
    kw_b = kw_t = None
    if has_key:
        kw_b = default_keyway_b(seg, m_n) if keyway_b is None else float(keyway_b)
        if kw_b <= 0:
            raise ValueError(f"键槽宽 keyway_b={kw_b:.4f} 必须 > 0")
        if kw_b / 2.0 >= bore / 2.0:
            raise ValueError(f"键槽半宽 {kw_b / 2.0:.3f} ≥ 孔半径 {bore / 2.0:.3f}（键槽无壁）")
        kw_t = keyway_depth_default(bore) if keyway_t1 is None else float(keyway_t1)
        if kw_t is None or kw_t <= 0:
            raise ValueError(f"键槽深 keyway_t1 无有效值（孔径 {bore} 无 GB/T 6132 最近档）")
        if bore / 2.0 + kw_t >= r_root:
            raise ValueError(
                f"键槽底越谷底圆：r_bore+t1 = {bore / 2.0 + kw_t:.3f} ≥ r_root={r_root:.3f}"
            )

    B_std = default_thickness(seg, L)
    thickness_std = True
    if B is None:
        if B_std is None:
            raise ValueError(
                f"φ{seg['dia']:.0f} 档标准厚度系列 {seg['B']} 全部 < L={L:.3f}："
                "请显式指定非标厚度 B（软警口径）或减小 L"
            )
        body_b = B_std
    else:
        body_b = float(B)
        if body_b < L:
            raise ValueError(f"刀体厚度 B={body_b:.3f} < 总重磨量 L={L:.3f}（刀齿比刀体长，硬拒）")
        thickness_std = B_std is not None and abs(body_b - B_std) < 1e-9

    warnings: list[str] = []
    if not thickness_std:
        warnings.append(
            f"厚度 B={body_b:.1f} 非当前档 φ{seg['dia']:.0f} 标准系列 {seg['B']}（软警不阻断）"
        )
    return ToolBodyResolved(
        mounting=mounting, d_bore=bore, keyway_b=kw_b, keyway_t1=kw_t,
        B=body_b, segment_dia=float(seg["dia"]),
        thickness_is_standard=thickness_std, warnings=warnings,
    )


# ── 几何：双闭环 + 极角配对 quad-strip ──


def _keyway_half_angles(r_bore: float, kw_b: float, kw_t1: float) -> tuple[float, float]:
    """键槽角点角：(θ_k 圆-壁交点, θ_c 槽底出口角 atan(h/x1)) [rad]."""
    h = kw_b / 2.0
    return math.asin(min(1.0, h / r_bore)), math.atan2(h, r_bore + kw_t1)


def _inner_radius(theta: float, r_bore: float, kw_b: float, kw_t1: float) -> float:
    """内边界沿极角 θ 的半径：无键槽角域 = 孔圆；缺口角域 = 射线离开键槽矩形的交点.

    矩形 void = [r_bore, r_bore+t1] × [−b/2, +b/2]（+X 向）。材料从射线**离开**
    矩形处恢复：|θ|≤θ_c 经槽底 x=x1 出（r=x1/cosθ），θ_c<|θ|<θ_k 经侧壁 y=±h 出
    （r=h/|sinθ|）。口部与孔圆之间的月牙薄楔（面积 ~h³/3r_bore 级）随之并入 void
    ——预览级接受，正式级布尔为精确矩形（W16 备注）。
    """
    if kw_t1 is None:
        return r_bore
    h = kw_b / 2.0
    th_k, th_c = _keyway_half_angles(r_bore, kw_b, kw_t1)
    t = (theta + math.pi) % (2.0 * math.pi) - math.pi  # 归一 (−π, π]
    if abs(t) >= th_k:
        return r_bore
    if abs(t) <= th_c:
        return (r_bore + kw_t1) / math.cos(t)
    return h / abs(math.sin(t))


def _sample_angles(n_base: int, corners: list[float]) -> list[float]:
    """均匀基采样 + 键槽角点角精确入样，升序去重（角点处多边形与真边界重合）."""
    angles = [2.0 * math.pi * j / n_base for j in range(n_base)]
    for c in corners:
        angles.append(c % (2.0 * math.pi))
    angles.sort()
    out: list[float] = [angles[0]]
    for a in angles[1:]:
        if a - out[-1] > 1e-12:
            out.append(a)
    return out


def _rake_z(rake: RakeSurface, x: float, y: float) -> float:
    """前刀面平面上的 z：A·x+B·y+C·z+const=0."""
    return -(rake.A * x + rake.B * y + rake.const) / rake.C


def _make_phase_folder(theta_c: float, z_t: int):
    """同相位折叠：把极角折回基准齿窗口 [theta_c−π/z_t, theta_c+π/z_t).

    刀具整环 = 基准齿 ×41 **纯旋转**阵列（K-3.1 勘误口径）：旋转不改 z，故 41 个齿的
    前刀面全部停在基准齿窗口的 z 相位。刀体前端面若取理想前刀面平面（z 随全周角变化，
    斜齿下跨幅达 ±2·sinγ·r 量级），会与齿圈产生十余毫米的 z 相位错位（一侧高出齿圈、
    另一侧缩进——2026-08-31 用户实测「光滑透明椭球」根因）。折叠后刀体边缘 z 与齿圈
    谷底弧逐扇区严丝合缝，[23]§3.3②「前端面∥前刀面」按槽位扇区成立——与整环阵列
    同一近似等级。
    """
    half = math.pi / z_t

    def fold(theta: float) -> float:
        rel = (theta - theta_c + math.pi) % (2.0 * math.pi) - math.pi  # (−π, π]
        folded = (rel + half) % (2.0 * half) - half                    # [−half, half)
        return theta_c + folded

    return fold


def build_tool_body(
    rake: RakeSurface,
    *,
    r_root: float,
    resolved: ToolBodyResolved,
    theta_c: float,
    z_t: int,
    n_base: int = 256,
) -> tuple[GeometrySpec, dict]:
    """刀体网格（双闭环 quad-strip，纯轴向直拉伸）+ 解析描述包.

    前端面 z 相位按 2π/z_t 折叠回基准齿窗口（_make_phase_folder）——与刀具整环的
    同相位旋转阵列严丝合缝（理想平面会与旋转阵列的齿圈产生十余毫米 z 错位）。

    顶点布局：前外 FO / 前内 FI / 后外 RO / 后内 RI 四条环（各 n 个），前后端面、
    内外壁共用环顶点 → 构造性水密。绕向经散度体积自适应翻转（outward）。

    Returns:
        (GeometrySpec(layer_id="toolBody"), description 描述包 dict)

    Raises:
        ValueError: |rake.C|≈0（前刀面近水平，椭圆退化）/ r_root ≤ r_bore
    """
    if abs(rake.C) < 1e-9:
        raise ValueError("前刀面法向 Z 分量 C≈0（γ₀→90°），刀体前端面退化")
    r_bore = resolved.d_bore / 2.0
    if r_root <= r_bore:
        raise ValueError(f"谷底半径 r_root={r_root:.3f} ≤ 孔半径 {r_bore:.3f}")
    B = resolved.B

    has_key = resolved.keyway_t1 is not None
    corners: list[float] = []
    if has_key:
        th_k, th_c = _keyway_half_angles(r_bore, resolved.keyway_b, resolved.keyway_t1)
        # 对称角域：±θ_k（圆-壁交点）、±θ_c（槽底出口角），负角折算到 [0, 2π)
        corners = [th_k % (2.0 * math.pi), th_c % (2.0 * math.pi),
                   (-th_k) % (2.0 * math.pi), (-th_c) % (2.0 * math.pi)]
    angles = _sample_angles(n_base, corners)
    n = len(angles)

    fold = _make_phase_folder(theta_c, z_t)

    def _pt(r: float, theta: float, dz: float) -> list[float]:
        x, y = r * math.cos(theta), r * math.sin(theta)
        return [x, y, _rake_z(rake, r * math.cos(fold(theta)), r * math.sin(fold(theta))) + dz]

    r_in = [
        _inner_radius(a, r_bore, resolved.keyway_b, resolved.keyway_t1) for a in angles
    ]
    positions: list[float] = []
    for j, a in enumerate(angles):  # FO
        positions += _pt(r_root, a, 0.0)
    for j, a in enumerate(angles):  # FI
        positions += _pt(r_in[j], a, 0.0)
    for j, a in enumerate(angles):  # RO
        positions += _pt(r_root, a, -B)
    for j, a in enumerate(angles):  # RI
        positions += _pt(r_in[j], a, -B)
    fo, fi, ro, ri = 0, n, 2 * n, 3 * n

    def _j(j: int) -> int:
        return (j + 1) % n

    tris: list[int] = []
    for j in range(n):
        k = _j(j)
        tris += [fo + j, fo + k, fi + k, fo + j, fi + k, fi + j]          # 前端面
        tris += [ro + j, ri + k, ro + k, ro + j, ri + j, ri + k]          # 后端面
        tris += [fo + j, ro + j, ro + k, fo + j, ro + k, fo + k]          # 外壁（共享边反向）
        tris += [fi + j, fi + k, ri + k, fi + j, ri + k, ri + j]          # 内壁（共享边反向）

    def _signed_volume() -> float:
        vol = 0.0
        for t in range(0, len(tris), 3):
            a, b, c = tris[t], tris[t + 1], tris[t + 2]
            ax, ay, az = positions[3 * a], positions[3 * a + 1], positions[3 * a + 2]
            bx, by, bz = positions[3 * b], positions[3 * b + 1], positions[3 * b + 2]
            cx, cy, cz = positions[3 * c], positions[3 * c + 1], positions[3 * c + 2]
            vol += ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)
        return vol / 6.0

    if _signed_volume() < 0:  # 全局 outward 自适应翻转
        tris = [
            v for t in range(0, len(tris), 3) for v in (tris[t], tris[t + 2], tris[t + 1])
        ]

    description = {
        "loop": {
            "outer_radius": r_root,
            "bore_radius": r_bore,
            "keyway": None if not has_key else {
                "width": resolved.keyway_b, "depth": resolved.keyway_t1, "polar_deg": 0.0,
            },
        },
        "rake_plane": {"A": rake.A, "B": rake.B, "C": rake.C, "const": rake.const},
        "extrusion": {"axis": [0.0, 0.0, -1.0], "length": B},
        "boolean_def": {
            "union": ["tooth_ring"],
            "cut": ["bore_cylinder"] + (["keyway_box"] if has_key else []),
        },
        "grade": "preview",
        "segment_dia": resolved.segment_dia,
        "thickness_is_standard": resolved.thickness_is_standard,
        "warnings": list(resolved.warnings),
    }
    spec = GeometrySpec(
        kind="mesh", positions=positions, indices=tris,
        normals=compute_vertex_normals(positions, tris), layer_id="toolBody",
    )
    return spec, description

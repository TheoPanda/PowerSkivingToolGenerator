"""模块② 离散包络端点测试.

纯 Python + pygltflib（不依赖 OCCT），可入 CI。
"""

import base64
import math

import pytest
from fastapi.testclient import TestClient

from app import app
from core.common.glb_inspect import glb_positions


# ── 子 PRD-2 离散包络端点 ─────────────────────────────────────────────


def _swept_cloud_request(**overrides):
    """最小内齿轮包络请求（小离散参数加速测试）."""
    body = {
        "workpiece": {"m_n": 2.0, "z_w": 82, "b_w": 20.0, "k_io": -1},
        "tool": {"z_t": 41, "beta_t_deg": 15.0, "j_t": -1},
        "discretization": {"n": 50, "m": 31, "theta_range_deg": 20.0},
    }
    body.update(overrides)
    return body


def test_swept_cloud_returns_mesh_layer():
    client = TestClient(app)
    resp = client.post("/api/envelope/swept_cloud", json=_swept_cloud_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "swept_cloud"
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


def test_swept_cloud_helical_workpiece_ok():
    """斜齿工件 swept_cloud 不再拒绝（process_plan 已解除斜齿禁用；扫掠点云为端面
    廓形扫掠，中间媒介非产形面，β_w 仅经端面参数 m_t/α_t 进入）."""
    client = TestClient(app)
    req = _swept_cloud_request()
    req["workpiece"]["beta_w_deg"] = 10.0
    resp = client.post("/api/envelope/swept_cloud", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "swept_cloud"


def test_swept_cloud_returns_motion_metadata():
    client = TestClient(app)
    resp = client.post("/api/envelope/swept_cloud", json=_swept_cloud_request())
    assert resp.status_code == 200
    data = resp.json()
    motion = data["motion"]
    assert motion["n"] == 50
    assert motion["m"] == 31
    assert motion["theta_range_deg"] == 20.0
    assert motion["surface_indices_per_row"] == (50 - 1) * 6
    assert motion["points_vertices_per_row"] == 50
    assert motion["wireframe_indices_per_row"] == 12 * (50 - 1)
    # 安装参数（中心距 a + 轴交角 Σ）供前端 T→W 变换与坐标轴
    install = data["install"]
    assert install["a"] > 0
    assert abs(install["sigma_deg"]) > 0


def test_swept_cloud_glb_has_three_primitives():
    from pygltflib import GLTF2
    client = TestClient(app)
    resp = client.post("/api/envelope/swept_cloud", json=_swept_cloud_request())
    blob = base64.b64decode(resp.json()["layer"]["glb_base64"])
    gltf = GLTF2.load_from_bytes(blob)
    modes = sorted(m.primitives[0].mode for m in gltf.meshes)
    assert modes == [0, 1, 4]  # POINTS, LINES, TRIANGLES
    # 面/点/线框均带 COLOR_0 顶点色（光谱 / 光谱 / 灰）
    for m in gltf.meshes:
        assert m.primitives[0].attributes.COLOR_0 is not None


def test_edge_returns_segments_and_diagnostics():
    client = TestClient(app)
    resp = client.post("/api/envelope/edge", json=_swept_cloud_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "edge"
    assert "coverage_report" in data
    assert "ffa_um" in data
    assert "segments_meta" in data
    assert "install" in data  # 刃形同为刀具系 T，需安装参数做 T→W 变换
    assert data["install"]["a"] > 0
    assert data["coverage_report"]["total_points"] == 50  # n=50
    # B 方案 v2：完整刃形闭合环（共轭上链白 + 齿底构造段橙，单条 LINE_STRIP）
    assert data["closed_loop"] is True
    assert data["residual_stats"] is None  # 直齿无双残差（ffα 闭环把守）
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"
    from pygltflib import GLTF2
    gltf = GLTF2.load_from_bytes(blob)
    line_meshes = [m for m in gltf.meshes if m.primitives[0].mode == 3]
    assert len(line_meshes) == 1


def test_edge_helical_numerical_intersection():
    """斜齿 /edge（数值求交 K-2.8b）：200 + 双残差 <5μm + ffa null + **闭合环**.

    m=181（生产默认）：斜齿 θ 窗口自动抬到 ≥120°，φ 采样过粗（m=31 → 8°/步）
    会使 φ* 插值误差放大表面残差至数十 μm。闭合环（顶刃共轭 + 顶缝桥 + 底刃
    1/2×2 构造，2026-08-24 用户需求）：右旋 5° 单 LINE_STRIP 环 + 构造段橙线。
    """
    client = TestClient(app)
    req = _swept_cloud_request()
    req["workpiece"]["beta_w_deg"] = 5.0
    req["workpiece"]["j_w"] = 1
    req["discretization"]["m"] = 181
    resp = client.post("/api/envelope/edge", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "edge"
    assert data["coverage_report"]["pass"] is True
    assert data["ffa_um"] is None          # 斜齿不做 ffα 闭环
    assert data["closed_loop"] is True     # 顶刃+桥+底刃构造闭合（右旋）
    st = data["residual_stats"]
    assert st is not None and st["pass"] is True
    assert st["max_plane_um"] < 5.0 and st["max_surface_um"] < 5.0
    assert st["n_bridge"] > 0
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"
    from pygltflib import GLTF2
    gltf = GLTF2.load_from_bytes(blob)
    # 闭合环为单条 LINE_STRIP（尾点回绕首点）
    line_meshes = [m for m in gltf.meshes if m.primitives[0].mode == 3]
    assert len(line_meshes) == 1


# ── 子 PRD-3 前刀面端点 ─────────────────────────────────────────────


def _rake_request(**overrides):
    """最小前刀面请求（内齿轮，γ₀=5°、β_t=15°）. """
    body = {
        "workpiece": {"m_n": 2.0, "z_w": 82, "b_w": 20.0, "k_io": -1},
        "tool": {"z_t": 41, "beta_t_deg": 15.0, "j_t": -1, "gamma_0_deg": 5.0},
        "rake_type": "plane",
    }
    body.update(overrides)
    return body


def test_rake_returns_plane_and_arrow():
    client = TestClient(app)
    resp = client.post("/api/envelope/rake", json=_rake_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "rake"
    # A/B/C 只依赖 γ₀/β_t（与 r_pt 无关）→ 算例1 golden 直接适用
    plane = data["plane"]
    assert plane["A"] == pytest.approx(0.087156, abs=1e-6)
    assert plane["B"] == pytest.approx(0.257834, abs=1e-6)
    assert plane["C"] == pytest.approx(0.962250, abs=1e-6)
    # n_rake 单位法矢
    n = data["n_rake"]
    assert math.hypot(n[0], n[1], n[2]) == pytest.approx(1.0, abs=1e-12)
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


def test_rake_glb_has_two_primitives():
    from pygltflib import GLTF2
    client = TestClient(app)
    resp = client.post("/api/envelope/rake", json=_rake_request())
    blob = base64.b64decode(resp.json()["layer"]["glb_base64"])
    gltf = GLTF2.load_from_bytes(blob)
    modes = sorted(m.primitives[0].mode for m in gltf.meshes)
    assert modes == [3, 4]  # LINE_STRIP（法矢箭头）+ TRIANGLES（平面片）


def test_rake_rejects_non_plane_type():
    client = TestClient(app)
    resp = client.post("/api/envelope/rake", json=_rake_request(rake_type="cone"))
    assert resp.status_code == 400
    assert "未实现" in resp.json()["detail"]["error"]


# ── 子 PRD-4 后刀面 + 单齿预览端点 ─────────────────────────────────────


def _flank_request(**overrides):
    """最小后刀面/单齿请求（内齿轮 + 小离散参数 + 重磨）."""
    body = {
        "workpiece": {"m_n": 2.0, "z_w": 82, "b_w": 20.0, "k_io": -1},
        "tool": {"z_t": 41, "beta_t_deg": 15.0, "j_t": -1, "gamma_0_deg": 5.0, "alpha_0_deg": 8.0},
        "resharpening": {"L": 2.0, "n_L": 4},
        "discretization": {"n": 50, "m": 31, "theta_range_deg": 20.0},
    }
    body.update(overrides)
    return body


def test_flank_returns_mesh_and_schedule():
    client = TestClient(app)
    resp = client.post("/api/envelope/flank", json=_flank_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "flank"
    assert data["source"] == "螺旋导程法（K-2.15/16，闭合轮廓 ribbon，B 方案 v2）"
    assert data["flank_method"] == "helical_lead"
    # 导程 Ltp = z_t·m_n·π/sin β_t（算例1 = 995.33mm）
    assert data["lead_pitch"] == pytest.approx(
        41 * 2.0 * math.pi / math.sin(math.radians(15.0)), rel=1e-6
    )
    schedule = data["resharpen_schedule"]
    assert len(schedule) == 4
    # 螺旋导程法无中心距变动（截面恒定）：da=0、a_i 不变
    assert schedule[0]["da"] == 0.0
    assert schedule[3]["da"] == 0.0
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


def test_flank_rejects_unimplemented_tool_type():
    client = TestClient(app)
    resp = client.post("/api/envelope/flank", json=_flank_request(tool_type="conical"))
    assert resp.status_code == 400
    assert "未实现" in resp.json()["detail"]["error"]


def test_single_tooth_returns_closed_solid_glb():
    from pygltflib import GLTF2
    client = TestClient(app)
    resp = client.post("/api/envelope/single_tooth", json=_flank_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["layer"]["id"] == "singleTooth"
    assert data["source"] == "模块③ B 方案 v2（开放轮廓 + 径向偏置 + 圆弧闭合实体）"
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"
    gltf = GLTF2.load_from_bytes(blob)
    modes = sorted(m.primitives[0].mode for m in gltf.meshes)
    assert modes == [4]  # 仅 TRIANGLES（闭合流形实体，刃形线由独立 /edge 图层承担）
    # B 方案 v2 元数据：理论极限圆 + 偏置谷底
    meta = data["meta"]
    assert meta["r_limit_mm"] == pytest.approx(80.0 - 39.5537, abs=1e-3)
    assert meta["root_offset_mm"] == pytest.approx(0.05 * 2 * 42.4463, abs=1e-3)  # d_pt/20
    assert meta["root_radius_mm"] == pytest.approx(meta["r_limit_mm"] - meta["root_offset_mm"], abs=1e-6)
    assert 0.0 < meta["pitch_z_mm"] < 3.0
    assert meta["volume_mm3"] > 0.0


def test_tool_ring_returns_arrayed_glb():
    from pygltflib import GLTF2
    client = TestClient(app)
    resp = client.post("/api/envelope/tool_ring", json=_flank_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["layer"]["id"] == "toolRing"
    assert data["coord_frame"] == "T"
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"
    gltf = GLTF2.load_from_bytes(blob)
    assert gltf.meshes[0].primitives[0].mode == 4  # TRIANGLES
    assert data["meta"]["z_t"] == 41


def test_tool_ring_rejects_bad_offset_ratio():
    """偏置比守卫：pydantic 拒 ≤0 值（422）；过大偏置使谷底越轴 → 400 JSON."""
    client = TestClient(app)
    body = _flank_request()
    body["hub"] = {"root_offset_ratio": -0.01}
    resp = client.post("/api/envelope/tool_ring", json=body)
    assert resp.status_code == 422  # pydantic gt=0 校验
    body["hub"] = {"root_offset_ratio": 5.0}  # 偏置 > 极限半径 → 谷底越轴
    resp = client.post("/api/envelope/tool_ring", json=body)
    assert resp.status_code == 400


@pytest.mark.parametrize("j_t", [+1, -1])
def test_tool_ring_same_phase_no_axial_stagger(j_t: int):
    """整环 API 级回归锁（2026-08-27 勘误回退）：/tool_ring 输出为同相位周向阵列.

    #34 曾在此断言「相邻齿轴向错位已施加」——用户实测证实那会产生 p_z≈24mm 的
    齿间轴向间隙，属需求侧公式误设，已回退。本测试锁死正确口径：① meta 不再
    携带 applied_p_z_mm 键；② 整环 GLB 的 z 向跨度与单齿一致（j_t 取值对几何
    无影响——阵列不含任何平移分量）。
    """
    client = TestClient(app)
    req = _flank_request(tool={"z_t": 41, "beta_t_deg": 15.0, "j_t": j_t})
    resp = client.post("/api/envelope/tool_ring", json=req)
    assert resp.status_code == 200
    data = resp.json()
    z_t = 41
    assert "applied_p_z_mm" not in data["meta"]  # 错位概念已随回退删除

    glb = base64.b64decode(data["layer"]["glb_base64"])
    assert glb[:4] == b"glTF"
    pos = glb_positions(glb)
    n_per = len(pos) // z_t
    ring_span = float(pos[:, 2].max() - pos[:, 2].min())
    tooth_span = float(pos[:n_per][:, 2].max() - pos[:n_per][:, 2].min())
    assert ring_span == pytest.approx(tooth_span, abs=1e-2)  # 单齿宽 L≈2mm 口径内全环等跨


# ── 子 PRD-5 解析路线端点 ─────────────────────────────────────────────


def test_analytic_returns_edge_and_cross_check():
    client = TestClient(app)
    resp = client.post("/api/envelope/analytic", json=_swept_cloud_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "edge"
    assert data["source"] == "解析（K-2.8）"
    assert data["point_count"] > 0
    assert "cross_check" in data
    assert "max_delta_um" in data["cross_check"]
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


# ── 子 PRD-5 产形面（共轭面）端点 ───────────────────────────────────


def _conjugate_request(**overrides):
    """最小产形面请求（内齿轮 + 小离散参数）."""
    body = {
        "workpiece": {"m_n": 2.0, "z_w": 82, "b_w": 20.0, "k_io": -1},
        "tool": {"z_t": 41, "beta_t_deg": 15.0, "j_t": -1},
        "discretization": {"n": 50, "m": 31, "n_z": 7, "theta_range_deg": 40.0},
    }
    body.update(overrides)
    return body


def test_conjugate_returns_mesh_and_install():
    client = TestClient(app)
    resp = client.post("/api/envelope/conjugate", json=_conjugate_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "conjugate"
    assert data["coverage_report"]["pass"] is True
    assert data["coverage_report"]["found"] == data["coverage_report"]["total_points"]
    assert data["install"]["a"] > 0
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


def test_conjugate_anim_section_metadata():
    """include_anim=True 返回截面切片元数据（n_profile + layer_zs，前端沿齿向选层用）."""
    client = TestClient(app)
    body = _conjugate_request(
        include_anim=True, m_anim=8,
        discretization={"n": 50, "m": 31, "n_z": 7, "theta_range_deg": 40.0},
    )
    resp = client.post("/api/envelope/conjugate", json=body)
    assert resp.status_code == 200
    anim = resp.json()["anim"]
    assert anim["n_profile"] == 50
    # K-0.5 链合成参数：前端任意 φ 实时合成扫掠位置（ω_t/ω_w = z_w/z_t 恒正）
    assert anim["omega_ratio"] == pytest.approx(82 / 41)
    assert len(anim["layer_zs"]) == 7
    # layer_zs = linspace(-b_w/2, +b_w/2, n_z)（与 compute_conjugate_surface 内部一致）
    assert anim["layer_zs"][0] == pytest.approx(-10.0)
    assert anim["layer_zs"][-1] == pytest.approx(10.0)
    assert anim["layer_zs"][3] == pytest.approx(0.0, abs=1e-9)
    # indices 全部可由 //n_profile 映射到层号 ∈ [0, n_z)
    assert all(0 <= idx // 50 < 7 for idx in anim["indices"])


def test_tooth_flank_returns_points_layer():
    """内齿轮齿面端点：W 系坐标 + 离散点/法向箭头 GLB + 参与掩码统计."""
    client = TestClient(app)
    resp = client.post("/api/envelope/tooth_flank", json=_conjugate_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "W"  # 工件系：前端免 T→W 安装变换
    assert data["layer"]["id"] == "toothFlank"
    assert "coverage_report" in data
    assert data["install"]["a"] > 0
    grid = data["grid"]
    assert grid["n"] == 50
    assert grid["n_z"] == 7
    # 抽稀箭头 50~400 根（n=50/n_z=7 → 步距 4×1 → 13×7=91）
    assert 50 <= grid["arrow_count"] <= 400
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


def test_tooth_flank_glb_has_points_and_lines():
    """GLB 含 POINTS + LINES 两 primitive，均带 COLOR_0 顶点色（参与/修剪双色）."""
    from pygltflib import GLTF2
    client = TestClient(app)
    resp = client.post("/api/envelope/tooth_flank", json=_conjugate_request())
    blob = base64.b64decode(resp.json()["layer"]["glb_base64"])
    gltf = GLTF2.load_from_bytes(blob)
    modes = sorted(m.primitives[0].mode for m in gltf.meshes)
    assert modes == [0, 1]  # POINTS, LINES
    for m in gltf.meshes:
        assert m.primitives[0].attributes.COLOR_0 is not None


def test_flank_helical_returns_ribbon():
    """斜齿 /flank（第二批）：螺旋导程法扫掠空间刃形环 → ribbon GLB + 导程."""
    client = TestClient(app)
    req = _flank_request()
    req["workpiece"]["beta_w_deg"] = 5.0
    req["workpiece"]["j_w"] = 1
    req["discretization"]["m"] = 181
    resp = client.post("/api/envelope/flank", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["layer"]["id"] == "flank"
    assert data["lead_pitch"] is not None and data["lead_pitch"] > 0
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


def test_single_tooth_helical_returns_solid():
    """斜齿 /single_tooth（第二批）：B 方案 v2 闭合实体（precut 环）GLB + 元数据."""
    client = TestClient(app)
    req = _flank_request()
    req["workpiece"]["beta_w_deg"] = 5.0
    req["workpiece"]["j_w"] = 1
    req["discretization"]["m"] = 181
    resp = client.post("/api/envelope/single_tooth", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["layer"]["id"] == "singleTooth"
    assert data["meta"]["volume_mm3"] > 0
    assert data["meta"]["n_sections"] == req["resharpening"]["n_L"] + 1
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


def test_tool_ring_helical_returns_arrayed():
    """斜齿 /tool_ring（第二批）：单齿实体刚体阵列 z_t 份 GLB."""
    client = TestClient(app)
    req = _flank_request()
    req["workpiece"]["beta_w_deg"] = 5.0
    req["workpiece"]["j_w"] = 1
    req["discretization"]["m"] = 181
    resp = client.post("/api/envelope/tool_ring", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["layer"]["id"] == "toolRing"
    assert data["meta"]["z_t"] == req["tool"]["z_t"]
    assert data["meta"]["volume_mm3"] > 0
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"

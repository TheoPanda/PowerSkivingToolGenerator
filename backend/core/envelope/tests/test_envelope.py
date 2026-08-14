"""模块② 包络占位演示端点测试（子 PRD-1 多图层能力验证）.

纯 Python + pygltflib（不依赖 OCCT），可入 CI。
"""

import base64
import math

import pytest
from fastapi.testclient import TestClient

from app import app


def test_envelope_demo_returns_four_layers():
    client = TestClient(app)
    resp = client.post("/api/envelope/demo")
    assert resp.status_code == 200
    layers = resp.json()["layers"]
    assert len(layers) == 4
    assert {layer["id"] for layer in layers} == {"swept_cloud", "rake", "edge", "flank"}


def test_envelope_demo_glb_valid():
    client = TestClient(app)
    resp = client.post("/api/envelope/demo")
    for layer in resp.json()["layers"]:
        blob = base64.b64decode(layer["glb_base64"])
        assert blob[:4] == b"glTF", f"图层 {layer['id']} GLB magic 错误"


# ── 子 PRD-2 离散包络端点 ─────────────────────────────────────────────


def _swept_cloud_request(**overrides):
    """最小内齿轮包络请求（小离散参数加速测试）."""
    body = {
        "workpiece": {"m_n": 2.0, "z_w": 82, "b_w": 20.0, "k_io": -1},
        "tool": {"z_t": 41, "beta_t_deg": 15.0, "j_t": -1},
        "discretization": {"n": 50, "m": 31, "NR": 60, "theta_range_deg": 20.0},
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


def test_swept_cloud_helical_workpiece_rejected():
    client = TestClient(app)
    req = _swept_cloud_request()
    req["workpiece"]["beta_w_deg"] = 10.0
    resp = client.post("/api/envelope/swept_cloud", json=req)
    assert resp.status_code == 400
    assert "斜齿" in resp.json()["detail"]["error"]


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
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


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

"""模块② 包络占位演示端点测试（子 PRD-1 多图层能力验证）.

纯 Python + pygltflib（不依赖 OCCT），可入 CI。
"""

import base64

from fastapi.testclient import TestClient

from app import app


def test_envelope_demo_returns_four_layers():
    client = TestClient(app)
    resp = client.post("/api/envelope/demo")
    assert resp.status_code == 200
    layers = resp.json()["layers"]
    assert len(layers) == 4
    assert {layer["id"] for layer in layers} == {"generatrix", "rake", "edge", "flank"}


def test_envelope_demo_glb_valid():
    client = TestClient(app)
    resp = client.post("/api/envelope/demo")
    for layer in resp.json()["layers"]:
        blob = base64.b64decode(layer["glb_base64"])
        assert blob[:4] == b"glTF", f"图层 {layer['id']} GLB magic 错误"


# ── 子 PRD-2 离散包络端点 ─────────────────────────────────────────────


def _generatrix_request(**overrides):
    """最小内齿轮包络请求（小离散参数加速测试）."""
    body = {
        "workpiece": {"m_n": 2.0, "z_w": 82, "b_w": 20.0, "k_io": -1},
        "tool": {"z_t": 41, "beta_t_deg": 15.0, "j_t": -1},
        "discretization": {"n": 50, "m": 31, "NR": 60, "theta_range_deg": 20.0},
    }
    body.update(overrides)
    return body


def test_generatrix_returns_mesh_layer():
    client = TestClient(app)
    resp = client.post("/api/envelope/generatrix", json=_generatrix_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "generatrix"
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"


def test_generatrix_helical_workpiece_rejected():
    client = TestClient(app)
    req = _generatrix_request()
    req["workpiece"]["beta_w_deg"] = 10.0
    resp = client.post("/api/envelope/generatrix", json=req)
    assert resp.status_code == 400
    assert "斜齿" in resp.json()["detail"]["error"]


def test_edge_returns_segments_and_diagnostics():
    client = TestClient(app)
    resp = client.post("/api/envelope/edge", json=_generatrix_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["coord_frame"] == "T"
    assert data["layer"]["id"] == "edge"
    assert "coverage_report" in data
    assert "ffa_um" in data
    assert "segments_meta" in data
    assert data["coverage_report"]["total_points"] == 50  # n=50
    blob = base64.b64decode(data["layer"]["glb_base64"])
    assert blob[:4] == b"glTF"

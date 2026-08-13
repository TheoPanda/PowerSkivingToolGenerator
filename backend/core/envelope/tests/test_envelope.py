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

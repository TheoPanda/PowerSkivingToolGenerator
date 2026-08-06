"""HTTP contract tests for POST /api/workpiece/generate.

Uses FastAPI TestClient — no network needed.
"""

import base64
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """FastAPI TestClient (路由已在 app.py 中注册)."""
    from app import app
    return TestClient(app)


class TestWorkpieceEndpoint:
    """POST /api/workpiece/generate 契约验证."""

    def test_valid_spur_gear_returns_200(self, client):
        """合法直齿轮参数 → 200 + {result, model_glb_base64}."""
        payload = {
            "profile_type": "involute",
            "k_io": 1,
            "m_n": 2.5,
            "z_w": 41,
            "beta_w_deg": 0.0,
            "j_w": 1,
            "b_w": 20.0,
            "alpha_n_deg": 20.0,
            "h_an": 1.0,
            "c_n": 0.25,
            "x_w": 0.0,
            "rho_f": 0.38,
            "tooth_method": "x_w",
            "W_k": None,
            "k_teeth": None,
            "M": None,
            "d_p": None,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "result" in data
        assert "model_glb_base64" in data

        result = data["result"]
        assert "d_a" in result
        assert "d_f" in result
        assert "r_b" in result
        assert "r_pw" in result
        assert "m_t" in result
        assert "alpha_t_deg" in result
        assert "z_w" in result

        # z_w should match input
        assert result["z_w"] == 41

    def test_glb_is_valid_base64(self, client):
        """model_glb_base64 是有效 base64 编码."""
        payload = {
            "m_n": 2.5, "z_w": 41, "b_w": 20.0,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200

        data = response.json()
        b64 = data["model_glb_base64"]
        # 有效的 base64
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0

        # GLB magic number: 0x46546C67 = "glTF"
        magic = int.from_bytes(decoded[:4], "little")
        assert magic == 0x46546C67

    def test_missing_required_field_returns_4xx(self, client):
        """缺少必填字段 m_n → 4xx (Pydantic 422 或 app 400)."""
        payload = {
            "z_w": 41, "b_w": 20.0,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code in (400, 422)

    def test_invalid_modulus_returns_4xx(self, client):
        """m_n <= 0 → 4xx."""
        payload = {
            "m_n": -1.0, "z_w": 41, "b_w": 20.0,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code in (400, 422)

    def test_invalid_teeth_returns_4xx(self, client):
        """z_w < 1 → 4xx."""
        payload = {
            "m_n": 2.5, "z_w": 0, "b_w": 20.0,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code in (400, 422)

    def test_default_values_applied(self, client):
        """未提供可选字段时使用默认值."""
        payload = {
            "m_n": 2.5, "z_w": 41, "b_w": 20.0,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200

        data = response.json()
        # α_t should be ~20° (默认 α_n=20°, β=0 → α_t=20°)
        assert abs(data["result"]["alpha_t_deg"] - 20.0) < 0.01

    def test_helical_gear_returns_200(self, client):
        """斜齿轮 (β=0, 即直齿轮) 应返回 200.

        注意: 完整斜齿轮 (β≠0) 暂因 OCP 限制不可用。
        """
        payload = {
            "m_n": 2.5, "z_w": 41, "b_w": 20.0,
            "beta_w_deg": 0.0,  # 直齿轮 (当前唯一支持的路径)
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200

    def test_result_values_consistent(self, client):
        """计算结果自洽: d_a = m_t*z_w + 2*h_an*m_n."""
        payload = {
            "m_n": 3.0, "z_w": 30, "b_w": 15.0,
            "alpha_n_deg": 20.0, "h_an": 1.0, "c_n": 0.25, "x_w": 0.0,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        data = response.json()
        result = data["result"]

        # d_a = 3.0*30 + 2*1.0*3.0 = 96.0
        assert abs(result["d_a"] - 96.0) < 0.1
        # r_pw = 3.0*30/2 = 45.0
        assert abs(result["r_pw"] - 45.0) < 0.1
        # r_b = r_pw * cos(20°) = 45.0 * 0.9397 = 42.286
        assert abs(result["r_b"] - 42.286) < 0.05

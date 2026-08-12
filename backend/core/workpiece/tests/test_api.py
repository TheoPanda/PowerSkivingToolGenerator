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


def _fillet_arc_count(spec: dict) -> int:
    """spec.single_tooth.segments 中顺时针（齿根圆角）弧的段数."""
    segs = spec["single_tooth"]["segments"]
    return sum(1 for s in segs if s["type"] == "arc" and s.get("clockwise") is True)


def _internal_payload(**overrides) -> dict:
    """内齿轮合法载荷 (z=82, m=2, d_rim=180 > d_f=169)."""
    payload = {
        "profile_type": "involute",
        "k_io": -1,
        "m_n": 2.0,
        "z_w": 82,
        "beta_w_deg": 0.0,
        "j_w": 1,
        "b_w": 20.0,
        "alpha_n_deg": 20.0,
        "h_an": 1.0,
        "c_n": 0.25,
        "x_w": 0.0,
        "tooth_method": "x_w",
        "d_rim": 180.0,
    }
    payload.update(overrides)
    return payload


class TestInternalGearApi:
    """内齿轮 k_io=−1 — POST /api/workpiece/generate 契约 (T03)."""

    def test_internal_gear_200_with_rim(self, client):
        """内齿 + d_rim: 200; spec inputs 含 d_rim; outline.circles 含 rim_radius; result d_a<d_f."""
        response = client.post("/api/workpiece/generate", json=_internal_payload())
        assert response.status_code == 200, response.text

        data = response.json()
        assert "model_glb_base64" in data
        result = data["result"]
        assert result["d_a"] < result["d_f"], f"内齿 d_a={result['d_a']} 应 < d_f={result['d_f']}"

        spec = data["spec"]
        in_keys = {i["key"] for i in spec["params"]["inputs"]}
        assert "d_rim" in in_keys, "spec.params.inputs 应注册 d_rim"
        assert "rim_radius" in spec["outline"]["circles"], "outline.circles 应含 rim_radius"
        assert spec["outline"]["circles"]["rim_radius"] == pytest.approx(180.0 / 2.0)

    def test_internal_d_rim_below_minimum_clamped(self, client):
        """内齿 d_rim 过小 → 200, rim_radius 钳制到 (d_f+2·m_n)/2 (Q9)."""
        response = client.post(
            "/api/workpiece/generate", json=_internal_payload(d_rim=160.0)
        )
        assert response.status_code == 200, response.text
        # z=82, m=2: d_f=169, min_rim = 169+4 = 173 → rim_radius = 86.5
        assert response.json()["spec"]["outline"]["circles"]["rim_radius"] == pytest.approx(173.0 / 2.0)

    def test_internal_da_below_base_400(self, client):
        """内齿 d_a < d_b (低齿数) → 400 + 用户提示 (Q8)."""
        response = client.post(
            "/api/workpiece/generate", json=_internal_payload(z_w=20)
        )
        assert response.status_code == 400
        assert "齿顶" in response.json()["detail"]["error"]

    def test_internal_helical_200(self, client):
        """内斜齿 β_w>0 → 200 (ADR-017 已支持); result d_a<d_f + α_t>20°; spec 含 β_w; GLB 有效."""
        response = client.post(
            "/api/workpiece/generate", json=_internal_payload(beta_w_deg=15.0)
        )
        assert response.status_code == 200, response.text
        data = response.json()
        result = data["result"]
        assert result["d_a"] < result["d_f"]
        assert result["alpha_t_deg"] > 20.0, "β>0 应使 α_t 增大"
        spec = data["spec"]
        in_items = {i["key"]: i for i in spec["params"]["inputs"]}
        assert in_items["beta_w_deg"]["value"] == 15.0
        assert "rim_radius" in spec["outline"]["circles"]
        decoded = base64.b64decode(data["model_glb_base64"])
        assert int.from_bytes(decoded[:4], "little") == 0x46546C67  # glTF

    def test_internal_helical_wk_400(self, client):
        """内斜齿 tooth_method=W_k → 400 (公法线禁用, Q2)."""
        response = client.post(
            "/api/workpiece/generate",
            json=_internal_payload(beta_w_deg=15.0, tooth_method="W_k",
                                   W_k=100.0, k_teeth=3),
        )
        assert response.status_code == 400
        assert "公法线" in response.json()["detail"]["error"]

    def test_internal_helical_low_z_400(self, client):
        """内斜齿低齿数 d_a<d_b (β=15, z=29) → 400 + 用户提示 (Q8)."""
        response = client.post(
            "/api/workpiece/generate", json=_internal_payload(beta_w_deg=15.0, z_w=29)
        )
        assert response.status_code == 400
        assert "齿顶" in response.json()["detail"]["error"]

    def test_internal_wk_400(self, client):
        """内齿 tooth_method=W_k → 400 (公法线禁用, Q2)."""
        response = client.post(
            "/api/workpiece/generate",
            json=_internal_payload(tooth_method="W_k", W_k=100.0, k_teeth=3),
        )
        assert response.status_code == 400
        assert "公法线" in response.json()["detail"]["error"]

    def test_internal_default_rim_minimum(self, client):
        """内齿省略 d_rim → 缺省 = d_f + 2·m_n (rim_radius = (d_f+2m_n)/2, Q9)."""
        response = client.post(
            "/api/workpiece/generate", json=_internal_payload(d_rim=None)
        )
        assert response.status_code == 200, response.text
        data = response.json()
        min_rim = data["result"]["d_f"] + 2.0 * 2.0  # m_n=2
        assert data["spec"]["outline"]["circles"]["rim_radius"] == pytest.approx(min_rim / 2.0)


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

    def test_response_contains_spec(self, client):
        """合法参数 → 响应含非空 spec.params.outputs / spec.single_tooth.segments / spec.outline.teeth."""
        payload = {
            "m_n": 2.5, "z_w": 41, "b_w": 20.0,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "spec" in data
        spec = data["spec"]

        # params.inputs / params.outputs
        assert len(spec["params"]["inputs"]) > 0
        assert len(spec["params"]["outputs"]) > 0
        out_keys = {o["key"] for o in spec["params"]["outputs"]}
        for k in ("d_pw", "d_a", "d_f", "d_b", "m_t", "alpha_t_deg",
                  "s_t", "s_n", "p_t", "h_a", "h_f", "h",
                  "rho_f_actual", "rho_tip_actual"):
            assert k in out_keys

        # single_tooth.segments
        segs = spec["single_tooth"]["segments"]
        assert len(segs) > 0
        assert all(s in ("arc", "polyline") for s in (x["type"] for x in segs))
        assert "annotations" in spec["single_tooth"]
        assert len(spec["single_tooth"]["annotations"]) == 7

        # outline.points / outline.teeth / outline.circles
        assert len(spec["outline"]["points"]) > 0
        assert len(spec["outline"]["teeth"]) == 41  # z_w
        assert set(spec["outline"]["circles"].keys()) == {
            "tip_radius", "root_radius", "pitch_radius", "base_radius",
        }

    def test_root_fillet_false_removes_fillet_and_registers_input(self, client):
        """root_fillet=false → spec.single_tooth.segments 无顺时针圆角弧 (锐齿根), 且输入项注册."""
        payload = {
            "m_n": 2.5, "z_w": 41, "b_w": 20.0,
            "root_fillet": False,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200

        data = response.json()
        n = _fillet_arc_count(data["spec"])
        assert n == 0, f"root_fillet=false 不应有齿根圆角弧, 实得 {n}"

        in_keys = {i["key"] for i in data["spec"]["params"]["inputs"]}
        assert "root_fillet" in in_keys, "spec.params.inputs 应注册 root_fillet"

    def test_root_fillet_omitted_defaults_true(self, client):
        """省略 root_fillet → 默认 true (向后兼容, 圆角保留)."""
        payload = {
            "m_n": 2.5, "z_w": 41, "b_w": 20.0,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200

        data = response.json()
        n = _fillet_arc_count(data["spec"])
        assert n == 2, f"默认 root_fillet 应保留左右两段齿根圆角弧, 实得 {n}"

    def test_tip_mode_round_adds_fillet_and_registers_input(self, client):
        """tip_mode='round' + rho_tip>0 → spec 段含齿顶圆角弧, 输入项注册."""
        payload = {
            "m_n": 2.5, "z_w": 41, "b_w": 20.0,
            "tip_mode": "round", "rho_tip": 0.2,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200

        data = response.json()
        segs = data["spec"]["single_tooth"]["segments"]
        rho = 0.2 * 2.5
        n_fillet = sum(
            1 for s in segs
            if s["type"] == "arc" and abs(s["radius"] - rho) < 1e-9
            and s["center"] != [0.0, 0.0]
        )
        assert n_fillet >= 2, f"齿顶圆角弧应 ≥2, 实得 {n_fillet}"

        in_keys = {i["key"] for i in data["spec"]["params"]["inputs"]}
        assert "tip_mode" in in_keys, "spec.params.inputs 应注册 tip_mode"
        assert "chamfer_tip" in in_keys, "spec.params.inputs 应注册 chamfer_tip"

    def test_tip_mode_omitted_defaults_none(self, client):
        """省略 tip_mode → 默认 none (向后兼容)."""
        payload = {"m_n": 2.5, "z_w": 41, "b_w": 20.0}
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200
        assert response.json()["result"]["z_w"] == 41

    def test_tip_mode_chamfer_adds_chamfer_and_output(self, client):
        """tip_mode='chamfer' → spec 段含倒角直线, chamfer_actual 输出, 标注随模式."""
        payload = {
            "m_n": 2.5, "z_w": 41, "b_w": 20.0,
            "tip_mode": "chamfer", "chamfer_tip": 0.15,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        segs = data["spec"]["single_tooth"]["segments"]
        r_a = data["spec"]["outline"]["circles"]["tip_radius"]
        tip_arcs = [s for s in segs if s["type"] == "arc"
                    and abs(s["radius"] - r_a) < 1e-9 and s["center"] == [0.0, 0.0]]
        assert len(tip_arcs) == 1, f"齿顶弧应 1 段, 实得 {len(tip_arcs)}"
        idx = segs.index(tip_arcs[0])
        assert segs[idx - 1]["type"] == "polyline" and len(segs[idx - 1]["points"]) == 2
        assert segs[idx + 1]["type"] == "polyline" and len(segs[idx + 1]["points"]) == 2

        out_keys = {o["key"] for o in data["spec"]["params"]["outputs"]}
        assert "chamfer_actual" in out_keys, "spec.params.outputs 应含 chamfer_actual"
        ann = data["spec"]["single_tooth"]["annotations"]["tip_fillet"]
        assert ann["label"] == "齿顶倒角", f"chamfer 模式标注应为齿顶倒角, 实得 {ann['label']}"

    def test_overlapping_tooth_thickness_returns_400(self, client):
        """W_k 过大 → 齿厚≥齿距 (相邻齿重叠) → 400 校验错误, 非 500."""
        payload = {
            "m_n": 0.175, "z_w": 10, "b_w": 5.0,
            "tooth_method": "W_k", "W_k": 4.5683, "k_teeth": 2,
            "root_fillet": False,
        }
        response = client.post("/api/workpiece/generate", json=payload)
        assert response.status_code == 400, f"应 400, 实得 {response.status_code}"
        assert "相邻齿重叠" in response.json()["detail"]["error"]

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

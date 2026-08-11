"""Module ① FastAPI 路由 — POST /api/workpiece/generate.

API 规范 (backend/CLAUDE.md):
  - 错误格式: { "error": "描述", "code": 400 }
  - 模型传输: 仅 glTF/GLB
"""

import traceback
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from core.workpiece.builder import build_gear_model
from core.workpiece.exporter import export_glb_base64
from core.workpiece.models import GearParams, WorkpieceResult
from core.workpiece.spec import build_spec


router = APIRouter(prefix="/api", tags=["workpiece"])


class GearParamsRequest(BaseModel):
    """工件齿轮参数 — POST /api/workpiece/generate 请求体.

    字段名与前端 MainPanel.vue gearParams 对齐。
    """

    # 必填
    m_n: float = Field(..., gt=0, description="法向模数 [mm]")
    z_w: int = Field(..., ge=1, description="工件齿数")
    b_w: float = Field(..., gt=0, description="齿宽 [mm]")

    # 可默认
    profile_type: str = Field("involute")
    k_io: int = Field(1, ge=-1, le=1)
    beta_w_deg: float = Field(0.0, ge=0.0)
    j_w: int = Field(1)
    alpha_n_deg: float = Field(20.0, gt=0)
    h_an: float = Field(1.0)
    c_n: float = Field(0.25)
    rho_f: float = Field(0.38)
    rho_tip: float = Field(0.0, ge=0.0, description="齿顶倒圆系数 (默认 0 = 锐角齿顶, ADR-013 缺口)")
    root_fillet: bool = Field(True, description="齿根圆角开关 (默认开; False = 锐齿根, ADR-014)")
    x_w: float = Field(0.0)

    # 齿厚指定 (三选一)
    tooth_method: str = Field("x_w")
    W_k: Optional[float] = None
    k_teeth: Optional[int] = None
    M: Optional[float] = None
    d_p: Optional[float] = None

    @model_validator(mode="after")
    def check_beta_with_j(self):
        """β>0 时需要 j_w; 螺旋角 ≥ 0 (U7)."""
        if self.beta_w_deg < 0:
            raise ValueError("螺旋角 β_w 必须 ≥ 0 (U7)")
        if self.k_io not in (1, -1):
            raise ValueError("k_io 必须为 +1(外齿) 或 −1(内齿)")
        if self.j_w not in (1, -1):
            raise ValueError("j_w 必须为 +1(右旋) 或 −1(左旋)")
        if self.tooth_method not in ("x_w", "W_k", "M"):
            raise ValueError(f"齿厚方式 '{self.tooth_method}' 无效")
        return self

    def to_gear_params(self) -> GearParams:
        """转换为内部 GearParams 数据类."""
        return GearParams(
            m_n=self.m_n,
            z_w=self.z_w,
            b_w=self.b_w,
            profile_type=self.profile_type,
            k_io=self.k_io,
            beta_w_deg=self.beta_w_deg,
            j_w=self.j_w,
            alpha_n_deg=self.alpha_n_deg,
            h_an=self.h_an,
            c_n=self.c_n,
            rho_f=self.rho_f,
            rho_tip=self.rho_tip,
            root_fillet=self.root_fillet,
            x_w=self.x_w,
            tooth_method=self.tooth_method,
            W_k=self.W_k,
            k_teeth=self.k_teeth,
            M=self.M,
            d_p=self.d_p,
        )


class WorkpieceResponse(BaseModel):
    """POST /api/workpiece/generate 响应体."""
    result: dict
    model_glb_base64: str
    spec: dict  # 齿轮规格呈现 (params + single_tooth + outline), 与 GLB 同一次计算


@router.post("/workpiece/generate", response_model=WorkpieceResponse)
async def generate_workpiece(req: GearParamsRequest):
    """生成工件齿轮 GLB 模型.

    接收 GearParams → OCCT 构建 → 三角剖分 → GLB 导出 → 返回 base64 + 计算结果.
    """
    try:
        # 转换为内部参数
        p = req.to_gear_params()
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": 400})

    try:
        # 构建唯一几何模型 + 导出 GLB
        model = build_gear_model(p)
        glb_base64 = export_glb_base64(model)

        # 计算结果
        result = WorkpieceResult.from_gear_params(p)

        # 齿轮规格呈现: 用同一 GearParams 实例、同一次计算产出 spec,
        # 保证与 GLB / result 几何 ±0.0001mm 一致 (后端 spec 纯数学, 无 OCCT)。
        spec = build_spec(p)

        return {
            "result": result.to_dict(),
            "model_glb_base64": glb_base64,
            "spec": spec,
        }
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail={"error": str(e), "code": 501})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "code": 500})

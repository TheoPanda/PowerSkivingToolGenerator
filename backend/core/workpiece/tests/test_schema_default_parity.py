"""默认值单源守卫（PRD TO-4 / issue #35）— 权威源 = 后端 pydantic Field.

docs/prds/2026-08-27-tool-solid-panel-prd.md §3.1-6：刀具（及工件）参数默认值的
唯一权威是后端 pydantic Field。同一组参数历史上存在两份载体：

  - HTTP 边界   ：core.workpiece.router.GearParamsRequest、core.envelope.router.ToolParams
  - 领域纯数据：core.workpiece.models.GearParams、core.envelope.envelope_context.ToolSpec

两端各自演进时默认值会静默漂移（models.py 的 tooth_method 字段双份定义即实例，
已在 #35 删除）。本守卫用**显式映射表**逐键比对默认值（两端字段名可能不同名，
故不做同名隐式匹配），并做两侧全字段覆盖度检查——任何一侧新增/改名而映射表
未同步都会显式失败。

约定：
  - 比对的是「默认值」而非校验约束：pydantic 侧 gt/ge 属另一层语义，不入表。
  - 必填 ↔ 必填（两侧均无默认值）视为一致，用 _MISSING 哨兵表达。
  - 发现某键确实合法不一致时，不要静默放过：把它写进 allowed_unmapped 或在对应
    映射项旁注释理由，再让测试继续锁住其余键。
"""

import dataclasses
from dataclasses import fields as dataclass_fields

from pydantic.fields import FieldInfo

from core.envelope.envelope_context import ToolSpec
from core.envelope.router import ToolParams
from core.workpiece.models import GearParams
from core.workpiece.router import GearParamsRequest

_MISSING = object()  # 「无默认值（必填）」哨兵：必填 ↔ 必填 一致；必填 ↔ 有默认 不一致


def _pydantic_default(model_cls, name: str):
    info: FieldInfo = model_cls.model_fields[name]
    return _MISSING if info.is_required() else info.get_default(call_default_factory=True)


def _dataclass_default(cls, name: str):
    f = next(f for f in dataclass_fields(cls) if f.name == name)
    if f.default is not dataclasses.MISSING:
        return f.default
    if f.default_factory is not dataclasses.MISSING:  # 必填字段的 default_factory 也是 MISSING 哨兵
        return f.default_factory()
    return _MISSING


def _assert_parity(
    pydantic_cls,
    dataclass_cls,
    mapping: list[tuple[str, str]],
    *,
    label: str,
    allowed_unmapped: tuple[str, ...] = (),
) -> None:
    """默认值逐键相等断言 + 两侧全字段覆盖度检查.

    Args:
        pydantic_cls: 权威侧 BaseModel
        dataclass_cls: 从属侧 dataclass
        mapping: [(pydantic 字段名, dataclass 字段名)] 显式映射（命名可不同）
        label: 失败信息前缀（工具/工件）
        allowed_unmapped: 已知单侧独有的字段名（须注释理由，不得用于掩盖漂移）
    """
    py_names = set(pydantic_cls.model_fields)
    dc_names = {f.name for f in dataclass_fields(dataclass_cls)}
    mapped_py = {p for p, _ in mapping}
    mapped_dc = {d for _, d in mapping}

    unmapped = (py_names - mapped_py) | (dc_names - mapped_dc)
    stale = (mapped_py - py_names) | (mapped_dc - dc_names)
    unexplained = unmapped - set(allowed_unmapped)
    assert not unexplained and not stale, (
        f"{label}：映射表覆盖不全或含失效项。"
        f"未覆盖字段={sorted(unexplained)}，失效引用={sorted(stale)}。"
        "新字段必须入映射表；确属单侧独有则传入 allowed_unmapped 并注释理由"
    )

    drift: list[str] = []
    for py_key, dc_key in mapping:
        p_val, d_val = _pydantic_default(pydantic_cls, py_key), _dataclass_default(dataclass_cls, dc_key)
        if p_val != d_val:
            fmt = lambda v: "<必填>" if v is _MISSING else repr(v)  # noqa: E731
            drift.append(f"pydantic.{py_key}={fmt(p_val)} ≠ dataclass.{dc_key}={fmt(d_val)}")
    assert not drift, (
        f"{label}：默认值漂移（权威源 = pydantic Field，请改 dataclass 侧；"
        f"确属合法不一致则在测试内注释说明，不得静默放过）：{'；'.join(drift)}"
    )


# 工具参数（envelope ToolParams ↔ ToolSpec）：两端当前同名，仍显式建表——
# 任一端改名/增删字段立即在覆盖度检查里暴露，而不是等运行期才发现漏传。
_TOOL_MAP = [
    ("z_t", "z_t"),                # 两端均必填（int，≥1 / 无默认）
    ("beta_t_deg", "beta_t_deg"),  # U7：β 数值恒正，旋向在 j_t
    ("j_t", "j_t"),                # 旋向 ±1
    ("gamma_0_deg", "gamma_0_deg"),  # 设计前角 γ₀ [°]
    ("alpha_0_deg", "alpha_0_deg"),  # 顶刃后角 α₀ [°]（W2：算例2 基线）
]

# 工件参数（workpiece GearParamsRequest ↔ GearParams）：22 键一一对应。
_GEAR_MAP = [
    ("m_n", "m_n"),          # 必填
    ("z_w", "z_w"),          # 必填
    ("b_w", "b_w"),          # 必填
    ("profile_type", "profile_type"),
    ("k_io", "k_io"),        # +1 外齿 / −1 内齿
    ("beta_w_deg", "beta_w_deg"),
    ("j_w", "j_w"),
    ("alpha_n_deg", "alpha_n_deg"),
    ("h_an", "h_an"),
    ("c_n", "c_n"),
    ("rho_f", "rho_f"),
    ("rho_tip", "rho_tip"),          # ADR-013
    ("root_fillet", "root_fillet"),  # ADR-014 齿根圆角开关
    ("tip_mode", "tip_mode"),        # ADR-014
    ("chamfer_tip", "chamfer_tip"),
    ("x_w", "x_w"),
    ("tooth_method", "tooth_method"),  # 三选一 E1（#35 起仅一份定义）
    ("W_k", "W_k"),
    ("k_teeth", "k_teeth"),
    ("M", "M"),
    ("d_p", "d_p"),
    ("d_rim", "d_rim"),  # ADR-015/Q1 内齿轮齿圈外径
]


class TestSchemaDefaultParity:
    def test_tool_params_matches_tool_spec(self):
        """tool 组：pydantic ToolParams 默认 == ToolSpec 默认（重叠键含必填位）."""
        _assert_parity(ToolParams, ToolSpec, _TOOL_MAP, label="tool")

    def test_gear_params_request_matches_gear_params(self):
        """workpiece 组：GearParamsRequest 默认 == GearParams 默认."""
        _assert_parity(GearParamsRequest, GearParams, _GEAR_MAP, label="workpiece")

    def test_authority_is_pydantic_side(self):
        """方向性锚点：两位必填主参在 pydantic 侧确实是必填（防守卫被空转成直通）."""
        assert _pydantic_default(ToolParams, "z_t") is _MISSING
        assert _pydantic_default(GearParamsRequest, "m_n") is _MISSING
        # 非必填键取回真实默认值而非哨兵
        assert _pydantic_default(ToolParams, "j_t") == 1
        assert _pydantic_default(ToolParams, "alpha_0_deg") == 8.0

## Parent

[#15](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/15) — 内齿轮工件几何（k_io=−1）（spec）

## What to build

内齿轮 API 契约与规格层：
- `models.py`：`GearParams.d_rim: float | None` + `__post_init__` 校验。
- `router.py`：`GearParamsRequest.d_rim: Optional[float]` + `to_gear_params()` 透传 + k_io 校验错误 → 400。
- `spec.py`：`INPUT_ITEMS` 增 `d_rim` 行（内齿）；`outline.circles` 增 `rim_radius`；内齿 d_a/d_f 语义。

设计规格 `docs/specs/2026-08-12-internal-gear-design.md` §5。

## Acceptance criteria

- [ ] `models.py`：`d_rim` 字段，缺省 None → 内齿按 `d_f` 处理
- [ ] `router.py`：`d_rim` 透传；内齿校验失败 → 400 契约 `{error, code:400}`（`d_rim<d_f`、`d_a<d_b`、`β_w>0`、`W_k`）
- [ ] `spec.py`：`inputs` 含 `d_rim` 行（内齿）；`outline.circles.rim_radius` 存在（内齿）
- [ ] `test_api.py`：契约 + 各内齿错误用例断言 400 格式
- [ ] 响应 200 结构不变（result/model_glb_base64/spec）

## Blocked by

- [#17](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/17) — T02 环形实体 + exporter

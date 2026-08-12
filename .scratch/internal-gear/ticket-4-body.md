## Parent

[#15](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/15) — 内齿轮工件几何（k_io=−1）（spec）

## What to build

前端内齿模式 + 规格窗口内齿语义 + 全量回归：
- `useGearParams.ts`：`d_rim` 字段/载荷/默认。
- `GearParamsPanel.vue`：k_io=−1 时——显示「齿圈外径 d_rim」输入；`W_k` 灰置；「齿顶/齿根修饰」区灰置；`β_w`/旋向禁用（自动归零 + 提示）；切内齿自动重置冲突值（`W_k→x_w`、`tip_mode→none`）；`M` 模式 `d_p` 占位 `≈1.44×m_n`（外齿 `≈1.68×m_t`）。
- 规格窗口：`spec-types.ts` 契约同步 + 内齿标注语义（d_a 小径/d_f 大径/rim 圆）。

设计规格 `docs/specs/2026-08-12-internal-gear-design.md` §6。

## Acceptance criteria

- [ ] `useGearParams.ts`：`d_rim` 字段 + `toPayload` + 默认值
- [ ] `GearParamsPanel.vue`：k_io=−1 时 `d_rim` 输入显示、`W_k` 灰置、修饰区灰置、`β_w`/旋向禁用
- [ ] 自动重置：外→内切换时冲突值（W_k/β_w/tip_mode）自动重置 + 一行提示
- [ ] `d_p` 占位：内齿 `≈1.44×m_n`、外齿 `≈1.68×m_t`
- [ ] `spec-types.ts` 契约类型同步
- [ ] 前端单测：内齿模式渲染 + 自动重置
- [ ] `npm test` 全部通过 + 外齿回归保持绿

## Blocked by

- [#18](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/18) — T03 契约 + API

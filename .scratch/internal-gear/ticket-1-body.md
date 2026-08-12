## Parent

[#15](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/15) — 内齿轮工件几何（k_io=−1）（spec）

## What to build

后端几何层支持内齿轮（k_io=−1）：
- `models.py`：`tip_radius/root_radius/tip_diameter/root_diameter` 对 k_io=−1 采用 ISO 负齿数模型公式（`d_a=z·m_t−2(h_an+x)m_n` 小径、`d_f=z·m_t+2(h_an+c_n−x)m_n` 大径）；`__post_init__` 内齿校验。
- `profile.py`：内齿齿廓——齿面自齿顶（小径）至齿根（大径）、材料在外侧、齿顶/齿根弧方向翻转、锐顶+锐根（无修饰，Q3）。

范围：纯 Python 数学层（无 OCCT），可进 CI。设计规格 `docs/specs/2026-08-12-internal-gear-design.md` §4。

## Acceptance criteria

- [ ] `models.py`：k_io=−1 时 `d_a = z·m_t − 2·(h_an + x_w)·m_n`（小径）、`d_f = z·m_t + 2·(h_an + c_n − x_w)·m_n`（大径），且 `d_a < d_f`
- [ ] **全齿高不变量断言**：`(d_f − d_a)/2 = 2·h_an + c_n`，随任意 `x_w` 不漂移（回归护栏）
- [ ] `s_t = π·m_t/2 + 2·x_w·m_n·tan(α_t)` 内齿同式（+x 内齿变厚）
- [ ] `profile.py` 内齿齿廓：齿顶弧为小径、齿根弧为大径、材料外侧、锐顶锐根（无圆角/倒角段）
- [ ] `M` 内齿往返测试：`x_w → M → x_w` 收敛（`cos α_M = d_b/(M + d_p)`）
- [ ] `__post_init__` 内齿校验抛错：`d_rim < d_f`、`d_a < d_b`、`s_t ≥ π·m_t`、`β_w ≠ 0`、`tooth_method=W_k`
- [ ] 门禁：外齿轮（k_io=1）golden 测试全部保持绿

## Blocked by

无（T01 为后端几何首步）

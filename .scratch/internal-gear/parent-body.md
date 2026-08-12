## What to build

待加工齿轮板块（步骤1 参数 + 步骤2 工件 3D 生成 + 规格窗口）支持**内齿轮工件几何**（k_io=−1）：
参数 → 3D 环形实体（外边界 d_rim + 内齿孔）GLB → 规格窗口（单齿廓/整体轮廓/参数表）。
范围限定内齿轮自身几何层；车齿加工中心距/传动比语义（U9/K-1.5/K-1.6）与啮合副干涉留待模块②。

- 设计规格：`docs/specs/2026-08-12-internal-gear-design.md`（Q1–Q8 决策树 + 测试策略 + 交付阶段）
- 研究依据：`docs/research/内齿轮工件几何.md`
- ADR：**ADR-015**（ISO 21771 负齿数模型变位约定 + d_rim 参数 + v1 范围，部分销 T13）

关键决策：
- 变位 x 采纳 ISO 负齿数模型（+x 内齿变厚；`s_t=π·m_t/2+2x·m_n·tanα_t`，`d_a=z·m_t−2(h_an+x)m_n`，`d_f=z·m_t+2(h_an+c_n−x)m_n`；**全齿高不变量 `h=(d_f−d_a)/2=2h_an+c_n` 加断言**）
- `d_rim` 齿圈外径：可选，缺省 = 齿根圆 `d_f`，校验 `d_rim ≥ d_f`
- 内齿 v1 范围：仅直齿、仅 `x_w`/`M` 计量（`W_k` 禁用）、禁用齿顶/齿根修饰（锐顶+锐根）、`d_a < d_b` 阻塞 400

## Acceptance criteria

- [ ] 父 issue + T01–T04 子 ticket 全部关闭，验收标准全勾选
- [ ] 外齿轮（k_io=1）输出与现状逐点一致（golden 回归护栏，既有测试全绿）
- [ ] 内齿轮 3D GLB 为环形实体（外壁 `d_rim` + 内齿孔）
- [ ] 规格窗口内齿语义正确（d_a 小径 / d_f 大径 / rim 圆）
- [ ] ADR-015 + CONTEXT.md 记录已落盘

## Blocked by

无（父规格 issue）

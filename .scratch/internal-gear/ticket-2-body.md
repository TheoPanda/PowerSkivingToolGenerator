## Parent

[#15](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/15) — 内齿轮工件几何（k_io=−1）（spec）

## What to build

内齿轮**环形实体** 3D 构建 + 导出：
- `builder.py`：k_io=−1 时 face 为**带孔环形**（外 wire = `d_rim` 圆，内 wire = 内齿廓），`MakeFace(...).Add(内齿廓)` → `Prism`；斜齿守卫（k_io=−1 ∧ β_w>0 → 400）。
- `exporter.py`：`_extract_boundary_cycle` 返回**全部**边界环；侧壁 = **外壁（d_rim）+ 内齿壁** 双边界。

设计规格 `docs/specs/2026-08-12-internal-gear-design.md` §4.3。OCCT 集成。

## Acceptance criteria

- [ ] `builder.py`：k_io=−1 时 `MakeFace(外圈 d_rim).Add(内齿廓为孔)` 成功，Prism 得环形 solid（非实心齿盘）
- [ ] 斜齿守卫：k_io=−1 ∧ β_w>0 → 400（或 501）
- [ ] `exporter.py`：环形 face 三角剖分含**两条**边界环（外 rim + 内齿廓），侧壁分别构建
- [ ] 环形实体 mesh：闭合 / 流形；GLB 可加载
- [ ] OCCT 集成测试：环形 face 面积 ≈ 环形面积（鞋带/解析），与采样多边形一致

## Blocked by

- [#16](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/16) — T01 后端几何

# CONTEXT.md — 车齿刀工具生成器 领域词汇与决策日志

最后更新：2026-08-06（grilling session: 步骤2 工件齿轮生成与 3D 渲染）

## 领域词汇

| 术语 | 英文 | 定义 |
|------|------|------|
| 工件齿轮 | Workpiece Gear | 被车齿刀加工的齿轮，是步骤1的参数输入对象和步骤2的 3D 可视化对象 |
| 端面参数 | Transverse Parameters | 在垂直于齿轮轴的平面上定义的参数（m_t, α_t），从法向参数经 K-1.2 转换 |
| 法向参数 | Normal Parameters | 用户输入的参数（m_n, α_n, β_w），在齿面法平面上定义 |
| 半周期廓形 | Half-Period Profile | K-1.13/U13 定义：齿槽中心线→齿中心线的完整廓形（含齿根+一个齿面+齿顶），镜像+阵列得全齿圈 |
| 单齿单元 | Single-Tooth Unit | 一个齿的闭合 3D 实体（左右渐开线+齿根圆角+齿顶圆弧），是最小可阵列单元 |
| 齿圈 | Tooth Ring | z_w 个齿的完整外圈，无轴孔/键槽 |
| ThruSections | 多截面放样 | OCCT 的 BRepOffsetAPI_ThruSections，N 个 2D 截面按 Z 层叠放样成 3D 实体 |
| GLB | GLB Binary | glTF 二进制格式，本项目模型传输唯一格式 |

## 六模块流水线（设计书 §1.1）

```
模块① 工件与工艺方案 → ProcessPlan + WorkpieceSurface
模块② 反向包络 (2a前刀面/2b刃形/2c后刀面) → EdgeCurve + GeneratrixSurface + FlankSurface
模块③ 三维几何与结构 → ToolSolid
模块④ 正向仿真验证 → SimReport
模块⑤ 磨削工艺
模块⑥ 工艺文件
```

当前状态：模块① 工件齿轮 3D 模型生成（本次交付），模块②-⑥ 待后续。

## UI 步骤与模块映射

| UI 步骤 | 标签 | 对应设计书内容 | 状态 |
|---------|------|----------------|------|
| 步骤1 | 待加工齿轮 | 参数输入（Group A） | ✅ 已交付 |
| 步骤2 | 包络计算 | 当前：模块① 工件齿轮 3D 生成 + 预览 | 🚧 本次交付 |
| 步骤3 | 刀具几何体 | 模块②+③ 包络+刀具实体 | 待定 |
| 步骤4 | 仿真验证 | 模块④ | 待定 |
| 步骤5 | 工艺文件 | 模块⑥ | 待定 |

注意：步骤2 标签"包络计算"保留不变，其包络计算功能日后再开发。当前步骤2 承载的是模块① 的 3D 可视化产出。

## 架构决策记录 (ADR)

### ADR-001: 几何计算全部后端

**日期**: 2026-08-06
**决策**: 所有几何计算（渐开线廓形、OCCT 建模、剖分、GLB 导出）放在 Python 后端。前端只做 GLB 加载和 Three.js 渲染。
**理由**: 与设计书六模块架构一致；OCCT 是项目核心几何内核，前端不应重复实现渐开线公式；后续仿真/包络必须依赖 OCCT。

### ADR-002: 单齿单元 + 阵列构建齿圈

**日期**: 2026-08-06
**决策**: 2D 齿廓 → ThruSections 单齿 solid → 绕轴阵列 z_w 次 → Boolean union 成齿圈。
**理由**: 与设计书 K-1.13/U13 半周期思路一致；单齿 2D 圆角比 3D solid 圆角更可控；螺旋齿轮时单齿放样 + 阵列比全齿圈螺旋扫掠简单。

### ADR-003: 多截面放样 (ThruSections) 统一管线

**日期**: 2026-08-06
**决策**: 直齿（β_w=0）和斜齿（β_w≠0）用同一套 ThruSections 管线。每层 Z 截面用同一个端面渐开线齿廓，绕 Z 轴旋转 θ(z) = j_w·z·tan(β_w)/r_pw。β_w=0 时各层不旋转，退化为 Prism。
**理由**: 统一代码路径，β 只是参数；不引入 if-else 分叉；便于升级截面层数提高精度。

### ADR-004: 同步端点，异步留到 Module ②

**日期**: 2026-08-06
**决策**: `POST /api/workpiece/generate` 同步返回（JSON 内嵌 base64 GLB）。不引入 job queue / 轮询。
**理由**: 单齿轮建模耗时 0.5-5s，在 HTTP 超时范围内；当前只有一个端点，异步基础设施成本远超收益；Module ②（Newton-Raphson 迭代）和 Module ④（VERICUT 九步法）计算量大 10-100 倍，那时引入异步框架有真实需求。

### ADR-005: OCCT 直接 tessellate → GLB

**日期**: 2026-08-06
**决策**: BRepMesh_IncrementalMesh 剖分 → TopExp_Explorer 提取 vertex/normal/index → pygltflib 写 GLB。不走 STL 中间格式。
**理由**: 精度无损；pygltflib 纯 Python 轻量；与项目约束"模型传输仅用 glTF/GLB"对齐。

### ADR-006: K-0.x 分批，首批 K-0.1 + K-0.2 + K-0.6

**日期**: 2026-08-06
**决策**: 首批实现 Rot_x/y/z、Tran(x/y/z,d)、螺旋面参数化 S_w(u,θ)。K-0.3~K-0.8（安装变换、动系旋转、运动链、同步关系）留到 Module ②。
**理由**: Module ① 只需要坐标旋转/平移和螺旋面参数化；K-0.3~K-0.8 全部涉及刀具坐标系，当前不需要。

### ADR-007: 分层测试策略

**日期**: 2026-08-06
**决策**: K-0.x 变换库用纯 Python 单元测试（不依赖 OCCT，CI 可跑）；OCCT 构建用集成测试（需要 conda env）；testdata 回归基准在几何端点充足后接入。
**理由**: 避免"装不上 OCCT 就全红"；纯数学测试快速反馈。

### ADR-008: E1 扩展全量实施

**日期**: 2026-08-06
**决策**: 首批即实现 K-1.11（跨齿距/跨棒距反算）、K-1.12（齿根圆角）、K-1.13（半周期廓形）。
**理由**: 完整齿圈必须包含圆角和全齿廓；半周期是阵列的前置条件；反算支撑多种齿厚输入方式。

## 后端文件结构

```
backend/core/
├── __init__.py
├── common/              # K-0.x 变换库 + 坐标系
│   ├── __init__.py
│   ├── transforms.py    # K-0.1 Rot, K-0.2 Tran, K-0.6 螺旋面
│   └── tests/
├── workpiece/           # 模块①：工件齿轮
│   ├── __init__.py
│   ├── models.py        # 数据类（GearParams, WorkpieceResult）
│   ├── builder.py       # OCCT 构建（K-1.1~K-1.14）
│   ├── exporter.py      # OCCT → GLB 导出
│   └── tests/
├── envelope/            # 模块②（待建）
├── solid/               # 模块③（待建）
└── simulation/          # 模块④（待建）
```

## API 端点

### `POST /api/workpiece/generate`

请求：
```json
{
  "profile_type": "involute",
  "k_io": 1,
  "m_n": 2.5,
  "z_w": 41,
  "β_w": 0,
  "j_w": 1,
  "b_w": 20,
  "α_n": 20,
  "h_an": 1,
  "c_n": 0.25,
  "x_w": 0,
  "ρ_f": 0.38
}
```

响应：
```json
{
  "result": {
    "d_a": 107.5,
    "d_f": 96.25,
    "r_b": 48.164,
    "r_pw": 51.25,
    "m_t": 2.5,
    "α_t": 20.0,
    "z_w": 41
  },
  "model_glb_base64": "AAAA..."
}
```

## 前端组件变更

| 文件 | 变更 |
|------|------|
| `src/components/WorkpieceViewer.vue` | 新增 — 步骤2 状态面板 |
| `src/components/MainPanel.vue` | 修改 — `v-else-if="currentStep===2"` 挂载 WorkpieceViewer |
| `src/components/HelloWorld.vue` | 修改 — GLTFLoader 加载 GLB 替换 hob |
| `src/api/index.ts` | 修改 — `fetchWorkpiece()` 函数 |

## 3D 渲染策略

- 齿轮 GLB 加载后替换 hob 模型（保留场景灯光/OrbitControls/ACES 色调映射）
- GLB 含纯几何（positions + normals + indices），无顶点色/UV
- Three.js 侧 `MeshStandardMaterial({metalness:0.3, roughness:0.4})` 统一着色
- 复用现有 `panel:toggle` 事件偏移逻辑

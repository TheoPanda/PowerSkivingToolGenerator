# CONTEXT.md — 车齿刀工具生成器 领域词汇与决策日志

最后更新：2026-08-10（齿轮规格呈现窗口设计规格 + ADR-013 齿顶倒圆缺口）

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
| 齿顶倒圆 | Tip Fillet (ρ*_tip) | 齿顶与齿面之间的倒圆半径系数，ρ_tip = ρ\*_tip·m_n。**设计书参数字典未定义**，经 ADR-014 作为产品扩展落地（默认 0 = 锐角齿顶零变化）。区别于已在设计书定义的**齿根圆角 ρ\*_f** |
| 齿顶倒角 | Tip Chamfer (c*_tip) | 齿顶两角的 45° 直切（相对齿面切线 45°，尺寸沿齿面量取，c*_tip·m_n）。**设计书参数字典未定义**，经 ADR-014 产品扩展落地；超限自动收敛到最大可行值并回报 actual |

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

### ADR-012: workpiece 包职责清理 + exporter 切换 OCCT 原生 tessellation

**日期**: 2026-08-07
**决策**: 
- K-1.1 渐开线数学迁入 `profile.py`（单一权威），`models.py` 专注数据模型+齿厚
- `builder.py` 删除 `build_half_period_wire`/`compute_fillet_center` 隔离区（~270 行）
- **exporter 从 earcut 切换到 OCCT 原生 tessellation**：`builder wire → MakeFace (真正的 TopoDS_Face) → BRepMesh_IncrementalMesh → Triangulation_s → GLB`。端面三角形与 OCCT 实体完全一致。
- 侧壁由端面 triangulation 边界边挤压生成（顶点与端面共享，保证闭合流形）
- OCP 7.9.3 downcast bug 绕过：`MakeFace().Face()` 产出原生 `TopoDS_Face`，`Triangulation_s` 直接可用；不能从 solid 遍历面但是可以直接构建面
- 绕序因齿形而异（r_b>r_f 产 CW，r_f>r_b 产 CCW），通过总符号面积动态检测
- 移除 `earcut` 依赖

**理由**: 消除并行 3D 表示（之前 builder 产 OCCT 实体、exporter 产 earcut mesh，仅靠 2D 面积比对维系一致性）；渲染模型现在就是 CAD 模型的可视化视图。K-1.1 迁移 + 死代码清理解决了职责倒挂和代码腐化。

### ADR-013: 齿顶倒圆 ρ*_tip 缺口（仅规格层，默认 0 锐角）

**日期**: 2026-08-10
**决策**: 齿轮规格呈现窗口（`docs/specs/2026-08-10-gear-spec-presentation-design.md`）需标注「齿顶圆角」，但设计书第3章参数字典只定义齿根圆角系数 ρ*_f，**无齿顶倒圆系数**；当前齿形为锐角齿顶。新增 `GearParams.rho_tip`（默认 0.0）：默认 0 保持锐角（与 3D GLB 完全一致，验收主通道）；>0 时在共享 `_tooth_open_segments` 生成齿顶倒圆弧（2D/3D 同函数已就绪），但本窗口**仅规格层呈现**，3D mesh 与步骤1表单不改。记缺口项，>0 不得当已验证公式使用。
**理由**: 需求要求标注齿顶圆角而权威源未定义 → 按开发纪律「缺口未销不得当已验证公式落地」，以默认 0 落地并显式记录缺口；保持 2D/3D 一致性（默认）优先。
**状态**: ✅ 已销项（2026-08-11，ADR-014 产品扩展落地：`tip_mode` 主开关 + 齿顶圆角/倒角解析几何，默认 `none` 零变化）。

### ADR-014: 齿顶倒角/圆角产品扩展（销 ADR-013）

**日期**: 2026-08-11
**决策**: 齿顶处理以 `tip_mode: "none"|"chamfer"|"round"` 主开关落地（步骤1 面板三态分段控件「无/倒角/圆角」+ 各自系数输入）。几何在共享 `profile.py::_tooth_open_segments` 解析式实现（圆角 = 凸角双切切齿面+切齿顶圆，与 `solve_root_fillet` 对称；倒角 = 沿齿面量 c·mₙ、与齿面切线 45°、交齿顶弧），OCCT 照常建实体/剖分，2D/3D 同源。**齿顶倒角/圆角不在设计书参数字典**——公式为本项目推导、非设计书已验证，显式记录产品扩展。默认 `tip_mode='none'` 逐点零变化（golden 回归护栏）。超限自动收敛到最大可行值，`rho_tip_actual`/`chamfer_actual` 回报实际（面板信息色软提示「已取最接近请求值」）。
**理由**: 用户需求在面板提供齿顶倒角/圆角 + 齿根圆角开关；权威源未定义 → 按「缺口未销不得当已验证公式」原则，以产品扩展 + 默认零变化 + 显式 ADR 记录落地，销 ADR-013。公式推导见设计规格 `docs/specs/2026-08-11-tooth-chamfer-fillet-design.md`。

### ADR-011: K-1.12 齿根圆角 (方案 A) 条件性落地

**日期**: 2026-08-07
**决策**: `profile.solve_root_fillet` 一维搜索 + 二分精确化实现双切圆角 (切齿根圆 + 切渐开线, 凹角 CW 弧)；r_b > r_f 且双切有解时启用，无解时回退径向连接线。
**理由/数学边界**: 双切解存在当且仅当 r_f + ρ_f ≳ r_b (|P−ρ·n| 最小值 √(r_b²+ρ²))。深齿根 (如 m=3/z=20, r_b−r_f=1.94 > ρ=1.14) 方案 A 无解——真实齿根为滚刀展成摆线 = 方案 B (T13 未销项)，回退径向线是诚实占位。用户用例 m=1/z=32 (r_b−r_f=0.285 < ρ=0.38) 有解，过渡弧已渲染。
**扩展 (2026-08-11)**: 原 `r_b <= r_f` 被 `solve_root_fillet` 拒绝（"无需圆角"），导致高齿数齿轮（z=82/z=60，r_b<r_f）指定 `root_fillet` 也画不出圆角。已扩展：搜索起点改为齿面从齿根圆起始（`xi_at_radius(r_b, r_f)`），齿面-齿根圆连接角处双切圆角仍可解；门控放宽为 `root_fillet` 即可。
**扩展2 (2026-08-11, 已回退)**: 曾尝试把低齿数齿轮（z<30，深下切 r_b−r_f>ρ）半径放大到最小可行双切半径 ρ_min=(r_b²−r_f²)/(2r_f) 填死区，但**已回退**（commit 69015a0）：极端低齿数（z≲23）放大圆角在齿根圆上重叠 → 齿根弧退化 → 端面三角剖分失败 HTTP500；且回退暴露低齿数螺旋齿轮 radial fallback 的段断口 bug（z=10）。**结论**：方案 A（双切圆）几何上无法填 z≲23 死区——双切解存在需 ρ≥ρ_min，而 ρ_min 在 z≲23 已使两圆角重叠。真正解法为方案 B 摆线齿根（T13 未销项）或独立角落圆角构造（非双切）。当前 z≲31 死区保持锐齿根（诚实占位）。

### ADR-010: profile.py 单一权威轮廓实现

**日期**: 2026-08-07
**决策**: 端面齿廓数学 (K-1.1/K-1.13 + K-1.11 齿厚) 升格为独立纯数学模块 `profile.py`/`models.py`，以类型化段 (Arc CCW 短弧 + Polyline) 表示；builder (OCCT edges) 与 exporter (mesh) 均为薄消费者。K-1.11 三函数迁 models.py。
**理由**: 轮廓数学曾内联于两个表示层各一份，右齿面镜像/∓inv(α_t) 相位双份错；OCCT 齿根弧还因 GC_MakeArcOfCircle first>last 调用取到长弧 (探针结论: 该 API 恒 CCW 从 First 到 Last, sense 参数无效)。表示级测试 (闭合/体积/流形) 全绿而形状错——缺形状级测试缝。统一后由 TestProfileShape (镜像/齿厚) + TestCrossRepresentationConsistency (OCCT 面积≈鞋带面积) 把守。
**注**: 原 `build_half_period_wire` 隔离区已在 ADR-012 中移除。

### ADR-009: earcut 耳切三角剖分替代圆心扇形 (已由 ADR-012 替代)

**日期**: 2026-08-06
**决策**: ~~端面 cap 用 `earcut`~~ → 2026-08-07 切换为 OCCT 原生 BRepMesh tessellation。
**理由**: 齿廓非角度单调，圆心扇形剖分产生重叠三角形。earcut 解决了此问题，但引入与 OCCT 实体并行的第二套 3D 表示。ADR-012 将端面三角剖分统一为 OCCT BRepMesh (MakeFace → Triangulation_s)，消除双表示。

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
│   ├── models.py        # 数据模型 + K-1.2 换算 + K-1.11 齿厚反算
│   ├── profile.py       # K-1.1/K-1.12/K-1.13 端面齿廓纯数学 (单一权威)
│   ├── builder.py       # profile 段 → OCCT wires → 3D 实体
│   ├── exporter.py      # builder wire → OCCT BRepMesh → GLB (端面与 CAD 一致)
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

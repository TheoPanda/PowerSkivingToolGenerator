# 步骤2 工件齿轮 3D 生成与可视化 — 设计规格

**日期**：2026-08-06
**状态**：已批准（grill 完成，待实现）

## 1. 目标

在步骤2（UI 标签"包络计算"保留，包络计算功能日后开发）中：用户点击"生成齿轮"→ 后端 OCCT 构建工件齿轮 3D 模型（含渐开线廓形、齿根圆角、全齿圈阵列）→ 导出 GLB → 前端加载并替换背景 hob 模型 → 在 3D 视口中旋转观察。步骤2 面板同时展示计算结果摘要（d_a, d_f, r_b, r_pw 等）。

**设计书对齐**：本次实现对应设计书 Module ①（工件与工艺方案）的 3D 可视化产出——WorkpieceSurface。包络计算（Module ②）留到步骤3。

## 2. 组件与模块架构

```
后端 (Python/OCCT)
backend/core/
├── common/
│   ├── transforms.py          # K-0.1 Rot, K-0.2 Tran, K-0.6 螺旋面
│   └── tests/test_transforms.py
├── workpiece/
│   ├── models.py              # 数据类（GearParams, WorkpieceResult）
│   ├── builder.py             # OCCT 构建（K-1.1~K-1.14）
│   ├── exporter.py            # OCCT → GLB 导出
│   └── tests/
│       ├── test_workpiece.py  # 集成测试
│       └── test_api.py        # HTTP 契约测试
├── envelope/                  # Module ②（待建）
├── solid/                     # Module ③（待建）
└── simulation/                # Module ④（待建）

前端 (Vue/Three.js)
src/
├── api/index.ts               # 新增 fetchWorkpiece()
├── components/
│   ├── WorkpieceViewer.vue     # 新增 — 步骤2 状态面板
│   ├── WorkpieceViewer.test.ts # 新增
│   ├── MainPanel.vue           # 修改 — v-else-if="currentStep===2"
│   ├── MainPanel.integration.test.ts  # 扩充
│   └── HelloWorld.vue          # 修改 — GLTFLoader 加载 GLB
```

## 3. 数据流

```
GearParamsPanel (步骤1) → MainPanel reactive gearParams
    ↓ inject
WorkpieceViewer (步骤2) → fetchWorkpiece(gearParams)
    ↓ HTTP POST
backend /api/workpiece/generate
    ↓ K-1.2 → K-1.1 → K-1.12 → K-1.13 → ThruSections → 阵列 → Mesh → GLB
    ↓ HTTP response (JSON + base64 GLB)
WorkpieceViewer ← result + GLB bytes
    ↓ emit / provide
HelloWorld ← GLTFLoader → Three.js scene (替换 hob)
```

## 4. API 契约

### `POST /api/workpiece/generate`

请求：
```json
{
  "profile_type": "involute",
  "k_io": 1, "m_n": 2.5, "z_w": 41,
  "β_w": 0, "j_w": 1, "b_w": 20,
  "α_n": 20, "h_an": 1, "c_n": 0.25,
  "x_w": 0, "ρ_f": 0.38,
  "tooth_method": "x_w",
  "W_k": null, "k_teeth": null,
  "M": null, "d_p": null
}
```

响应（200）：
```json
{
  "result": {
    "d_a": 107.5, "d_f": 96.25,
    "r_b": 48.164, "r_pw": 51.25,
    "m_t": 2.5, "α_t": 20.0, "z_w": 41
  },
  "model_glb_base64": "AAAA..."
}
```

响应（400）：
```json
{ "error": "模数 m_n 必须大于 0", "code": 400 }
```

- **同步模式**：OCCT 单齿轮建模预计 0.5-5 秒，在 HTTP 超时范围内
- **异步框架留到 Module ②**（包络 Newton-Raphson 迭代）和 Module ④（VERICUT 九步法）

## 5. OCCT 构建路线

### 5.1 端面参数转换（K-1.2）

```
用户输入: m_n, α_n, β_w (法向参数)
    ↓ K-1.2
端面参数: m_t = m_n/cos(β_w),  tan(α_t) = tan(α_n)/cos(β_w)
    ↓ K-1.1 (用 m_t, α_t)
2D 渐开线齿廓: r = m_t·z_w/2,  r_b = r·cos(α_t)
```

### 5.2 单齿 2D 廓形

- K-1.1：渐开线段 x = r_b(cosξ + ξ sinξ), y = r_b(sinξ − ξ cosξ)，ξ 范围 [0, ξ_a]
- K-1.12：齿根圆角 ρ_f·m_n，双切于渐开线和齿根圆
- K-1.13/U13：半周期廓形——齿槽中心线→齿中心线（含齿根+一个齿面+齿顶）
- 镜像 + 阵列 z_w 次 → 全齿圈

### 5.3 3D 实体（ThruSections）

- 直齿（β_w=0）和斜齿（β_w≠0）统一管线
- N 层 Z 截面，每层用同一个端面渐开线齿廓
- 每层绕 Z 轴旋转 θ(z) = j_w·z·tan(β_w)/r_pw
- β_w=0 时各层旋转角为零，退化为 Prism

### 5.4 GLB 导出

`BRepMesh_IncrementalMesh` → `TopExp_Explorer` 提取顶点/法线/索引 → `pygltflib` 写 GLB 二进制

- 不走 STL 中间格式
- 纯几何（positions + normals + indices），无顶点色/UV/材质

## 6. 前端组件行为

### WorkpieceViewer.vue（步骤2 面板）

- inject `gearParams`
- "生成齿轮"按钮 → POST → spinner → 结果摘要（d_a/d_f/r_b/r_pw/m_t/α_t）
- 失败 → ElMessage 错误提示
- 步骤1 参数修改后可"重新生成"
- 齿轮 GLB 解码后传给 HelloWorld 场景

### HelloWorld.vue（3D 渲染改造）

- 新增 `GLTFLoader` import
- 接收 GLB bytes → `GLTFLoader.parse()` → 替换当前 hob 模型
- 复用：PBR 灯光、ACES 色调映射、OrbitControls、自动旋转、panel:toggle 偏移
- 材质：`MeshStandardMaterial({metalness: 0.3, roughness: 0.4})`

### MainPanel.vue

- `.step-body` 新增 `v-else-if="currentStep === 2"` 挂载 `WorkpieceViewer`
- 步骤标签"包络计算"暂不修改（五步骤统一修订时处理）

## 7. E1 扩展

全量实施：
- **K-1.12**：齿根圆角（ρ_f·m_n，双切于渐开线和齿根圆）
- **K-1.13**：半周期廓形（齿槽中心线→齿中心线，镜像+阵列）
- **K-1.11**：跨齿距 W_k + k_teeth 和跨棒距 M + d_p 反推齿厚（支持三选一输入）

## 8. 测试策略

| 层 | 文件 | 依赖 | 内容 |
|----|------|------|------|
| 后端 K-0.x | `test_transforms.py` | 无 OCCT，CI 可跑 | Rot/Tran 矩阵正确性、K-0.6 螺旋面 |
| 后端构建 | `test_workpiece.py` | conda env + OCCT | d_a/d_f/r_b 容差验证 |
| 后端 API | `test_api.py` | FastAPI TestClient | HTTP 契约 200/400 |
| 前端 API | `api.test.ts` | mock fetch | fetchWorkpiece 签名 |
| 前端组件 | `WorkpieceViewer.test.ts` | mock api + inject | 按钮/加载/摘要/错误 |
| 前端集成 | `MainPanel.integration.test.ts` | 扩充 | 步骤1→2 推进 |

## 9. 文件变更清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `backend/core/__init__.py` | 新增 | 包初始化 |
| `backend/core/common/__init__.py` | 新增 | 包初始化 |
| `backend/core/common/transforms.py` | 新增 | K-0.1, K-0.2, K-0.6 |
| `backend/core/common/tests/test_transforms.py` | 新增 | 纯数学单测 |
| `backend/core/workpiece/__init__.py` | 新增 | 包初始化 |
| `backend/core/workpiece/models.py` | 新增 | GearParams, WorkpieceResult 数据类 |
| `backend/core/workpiece/builder.py` | 新增 | OCCT 构建管线 |
| `backend/core/workpiece/exporter.py` | 新增 | OCCT → GLB |
| `backend/core/workpiece/tests/test_workpiece.py` | 新增 | 集成测试 |
| `backend/core/workpiece/tests/test_api.py` | 新增 | HTTP 契约测试 |
| `backend/app.py` | 修改 | 注册 `/api/workpiece/generate` 路由 |
| `backend/requirements.txt` | 修改 | 取消 pythonocc-core 注释 + 加 pygltflib |
| `src/api/index.ts` | 修改 | 新增 fetchWorkpiece() |
| `src/components/WorkpieceViewer.vue` | 新增 | 步骤2 面板 |
| `src/components/WorkpieceViewer.test.ts` | 新增 | 组件测试 |
| `src/components/MainPanel.vue` | 修改 | step-body 步骤2 分支 |
| `src/components/MainPanel.integration.test.ts` | 修改 | 扩充步骤2 |
| `src/components/HelloWorld.vue` | 修改 | GLTFLoader + GLB 加载 |

## 10. 不做的

- 不实现包络计算（Module ②）
- 不实现刀具几何体（Module ③）、仿真/磨削/工艺文件（Module ④⑤⑥）
- 不修改步骤导航标签
- 不引入 Pinia / 异步任务队列
- 不导出 STEP/IGES/STL
- 不添加轴孔/键槽
- GLB 不包含顶点色/UV/材质
- 不实现 K-0.3~K-0.8
- 不做非渐开线齿廓分支

## 11. 验收标准

- `npm test` 全部通过
- `pytest backend/core/` 全部通过（含 OCCT 集成测试）
- 手动验证：启动 app → 填步骤1参数 → 进步骤2 → 点"生成齿轮" → 3D 视口显示齿圈 → 可旋转/缩放观察
- 设计书算例1（z_w=41, m_n=2.5, β_w=0, x_w=0）：d_a 误差 < 0.01mm, r_b 误差 < 0.001mm

## 12. 变更履历

| # | 日期 | 来源 | 变更 |
|---|------|------|------|
| 1 | 2026-08-06 | Grill Q1 | 步骤2产出确认为工件齿轮3D模型（非包络计算） |
| 2 | 2026-08-06 | Grill Q2 | 几何计算全部后端OCCT |
| 3 | 2026-08-06 | Grill Q3 | 齿轮GLB替换hob模型 |
| 4 | 2026-08-06 | Grill Q4 | GLB仅含齿圈，无轴孔键槽 |
| 5 | 2026-08-06 | Grill Q5 | 步骤2面板：按钮+进度+结果摘要 |
| 6 | 2026-08-06 | Grill Q6 | E1全做：圆角+半周期+齿厚反算 |
| 7 | 2026-08-06 | Grill Q7 | ThruSections统一管线，直齿斜齿同一代码路径 |
| 8 | 2026-08-06 | Grill Q8 | 单齿单元+阵列构建齿圈 |
| 9 | 2026-08-06 | Grill Q9 | 按模块分包目录结构 |
| 10 | 2026-08-06 | Grill Q10 | 单一同步端点POST /api/workpiece/generate |
| 11 | 2026-08-06 | Grill Q11 | 分层测试：纯数学+OCCT集成+API契约 |
| 12 | 2026-08-06 | Grill Q12 | 前端本次打通：api+GLB加载+状态面板 |
| 13 | 2026-08-06 | Grill Q13 | OCCT直接tessellate→pygltflib，不走STL |
| 14 | 2026-08-06 | Grill Q14 | K-0.1+K-0.2+K-0.6首批 |
| 15 | 2026-08-06 | Grill Q15 | JSON内嵌base64 GLB |
| 16 | 2026-08-06 | Grill Q16 | 组件命名WorkpieceViewer.vue |
| 17 | 2026-08-06 | Grill Q17 | GLB纯几何positions+normals+indices |
| 18 | 2026-08-06 | Grill Q18 | 步骤标签暂不改 |

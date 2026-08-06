# backend/ — Python 几何计算后端

FastAPI + OpenCASCADE (OCP) 车齿刀几何内核。

## 运行环境

- Python 3.14+，conda env `power-skiving`
- OCCT 绑定：`pythonocc-core`（当前用 OCP 7.9.3）
- 启动：`conda run -n power-skiving python app.py`
- 端口：`http://127.0.0.1:5199`

## 目录

```
backend/
├── app.py              # FastAPI 入口，CORS 已配置
├── requirements.txt
└── core/               # OCCT 几何计算（待建）
```

## API 规范

- 错误格式：`{ "error": "描述", "code": 400 }`
- 模型传输：仅 glTF/GLB
- CORS：`allow_origins=["*"]`

## 六模块流水线

```
模块① 工件与工艺方案   → ProcessPlan + WorkpieceSurface
模块②a 前刀面定义      → RakeSurface
模块②b 刃形求解        → EdgeCurve + GeneratrixSurface
模块②c 后刀面生成      → FlankSurface
模块③ 三维几何与结构   → ToolSolid (STEP)
模块④ 正向仿真验证     → SimReport
⑤ 磨削  ⑥ 工艺文件
```

## 开发纪律

1. **实现公式前先读设计书**——按 K 公式编号定位原文
2. **符号体系**：内部 rad / 接口 °；变量名与设计书一致（w/t/F_w/F_t，严禁用 1/2 表示工件/刀具）
3. **坐标系标签**：任何点集/曲面对象必须携带坐标标签（W/T/F_w/F_t/R）
4. **缺口清单项**：未销项用 skeleton + assert 占位，不得直接当已验证公式写入

## 设计书（只读引用）

`E:/OneDrive/Claude_Word/PowerSkivingDoc/reports/车齿刀设计书/`

关键公式：K-0.x（变换库）、K-1.x（模块①）、K-2.x（模块②）、K-3.x~K-6.x

## 开发分批

1. **第一批**：K-0.x → 模块①主体 → ②b 离散路线 → ②a 平面前刀面
2. **第二批**：E1/T13 计量齿厚 → T8 变位链 → ②b 解析路线 ε_NR
3. **缓行**：K-2.4 锥面前刀面 / 工作角度 / 机床补偿 / 模块⑤（回读 PDF 前不动）

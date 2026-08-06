## Parent

[#5](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/5) — 步骤2 工件齿轮 3D 生成与可视化（spec）

## What to build

将 Ticket 2 产出的 OCCT 齿圈实体导出为 GLB 二进制格式，并通过 FastAPI HTTP 端点暴露。端点接收 GearParams JSON，返回计算结果 + base64 编码的 GLB。

从用户视角：`curl -X POST /api/workpiece/generate` 返回包含齿轮几何数据的 JSON 响应。这是前后端之间第一个真正的数据通道。

## Acceptance criteria

- [ ] BRepMesh_IncrementalMesh 三角剖分齿圈实体，剖分精度 ≤ 0.01mm
- [ ] TopExp_Explorer 遍历提取 positions、normals、indices
- [ ] pygltflib 写入有效 GLB 二进制（可用 gltf-transform 或 Three.js 验证）
- [ ] POST /api/workpiece/generate 接收 GearParams JSON，返回 200 + {result, model_glb_base64}
- [ ] GLB 仅含纯几何（positions + normals + indices），无颜色/UV/材质
- [ ] 非法参数（m_n ≤ 0, z_w < 1, b_w ≤ 0）返回 {error: string, code: 400}
- [ ] backend/requirements.txt 取消 pythonocc-core 注释，新增 pygltflib
- [ ] FastAPI TestClient 端到端测试：200 响应结构正确、GLB base64 非空、400 错误格式正确

## Blocked by

- [#7](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/7) — Ticket 2 OCCT 齿轮构建器
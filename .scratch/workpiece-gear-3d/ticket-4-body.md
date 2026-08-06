## Parent

[#5](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/5) — 步骤2 工件齿轮 3D 生成与可视化（spec）

## What to build

打通前后端全链路。前端：扩展 API 客户端（fetchWorkpiece）、新建 WorkpieceViewer.vue 步骤2面板（生成按钮 + 加载动画 + 结果摘要 + 错误处理）、MainPanel 挂载步骤2、HelloWorld 用 GLTFLoader 加载 GLB 替换 hob 模型。用户完成步骤1参数填写后进入步骤2，点击"生成齿轮"即可在 3D 视口中看到自己的工件齿轮。

从用户视角：这是整个步骤2唯一直接面向用户的交付——填完参数 → 看到 3D 齿轮旋转。

## Acceptance criteria

- [ ] `src/api/index.ts` 新增 `fetchWorkpiece(params: GearParams): Promise<{result: WorkpieceResult, modelGlbBase64: string}>`
- [ ] `WorkpieceViewer.vue`：inject gearParams → "生成齿轮"按钮 → 调用 fetchWorkpiece → ElButton loading 状态 → 成功显示结果摘要（d_a/d_f/r_b/r_pw/m_t/α_t）+ ElMessage 提示 → 失败显示 ElMessage.error
- [ ] `MainPanel.vue` `.step-body` 新增 `v-else-if="currentStep === 2"` 挂载 WorkpieceViewer，步骤1→2 推进流畅
- [ ] `HelloWorld.vue` 新增 `GLTFLoader` import，解码 base64 GLB → `GLTFLoader.parse()` → 替换当前 hob 模型
- [ ] 齿轮使用 `MeshStandardMaterial({metalness: 0.3, roughness: 0.4})`，复用现有 PBR 灯光+ACES+OrbitControls+自动旋转
- [ ] 面板展开时齿轮自动偏移避让（复用现有 `panel:toggle` 逻辑）
- [ ] 步骤1参数修改后回步骤2，可"重新生成"
- [ ] `src/api/api.test.ts`：mock fetch 验证请求 URL/body/返回值/错误处理
- [ ] `WorkpieceViewer.test.ts`：mock fetchWorkpiece + provide gearParams → 验证按钮/加载/摘要/错误状态
- [ ] `MainPanel.integration.test.ts` 扩充：验证步骤2 分支渲染 + 步骤推进
- [ ] `npm test` 全部通过

## Blocked by

- [#8](https://github.com/TheoPanda/PowerSkivingToolGenerator/issues/8) — Ticket 3 GLB 导出 + API 端点
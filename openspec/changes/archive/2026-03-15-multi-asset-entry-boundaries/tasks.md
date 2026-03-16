## 1. Asset Boundary 契约

- [x] 1.1 定义 canonical `asset_scope / asset_profile / market_profile / execution_profile` 类型与 registry
- [x] 1.2 为当前 `baseline_V10.1` 绑定唯一正式 A 股 canonical profile

## 2. Runtime Compile 收口

- [x] 2.1 在 runtime config compile 第一阶段引入 asset boundary compile
- [x] 2.2 让 universe / signal / risk-exit / bundle compile 显式消费 canonical asset profile
- [x] 2.3 收口 builtin config 与 execution override 中散落的 A 股默认

## 3. Universe 与 Provider 入口

- [x] 3.1 将 universe resolver 改为先按 asset family 分发，再进入 A 股 adapter
- [x] 3.2 让 route registry 与 provider facade 显式消费 asset profile
- [x] 3.3 为未支持资产 family 增加显式 unsupported error 路径

## 4. HTTP Surface 与 Snapshot

- [x] 4.1 在 manifest、surface 与实验列表摘要中暴露资产上下文
- [x] 4.2 为 ResultsWorkbenchSnapshot 增加 `assetContext`
- [x] 4.3 收口桌面页壳与 workbench 展示逻辑，只消费 `assetContext`

## 5. Study 与生成入口

- [x] 5.1 要求 `.study.yaml` 显式声明 `asset_scope`
- [x] 5.2 让 generated thin script 与 `study_run` 只透传 canonical asset scope
- [x] 5.3 明确 baseline 不再承担资产入口语义

## 6. 回归与文档

- [x] 6.1 用 `baseline_V10.1 -> exp_20260314_144548534_7db9` 做 runtime config、manifest、surface 与 perf 对照
- [x] 6.2 补齐 OpenSpec、mapping 文档与边界测试

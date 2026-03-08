# Workbench 配置中心与运行真相统一说明

日期：2026-03-08

## 结论

本轮已完成两件事：

1. 前端顶部配置入口收敛为单一“配置中心”。
2. `run_async` 与 `execution_preview` 统一改为“单一运行真相”模式：
   - 请求优先提交 `runtime_config_json`
   - `config_id` 仅作为 provenance
   - 后端不再允许 `config_id` 静默覆盖已提交的 runtime config

## 背景问题

旧链路同时存在以下并行入口或并行真相：

- 顶部 `preset` 下拉
- 顶部“加载”按钮
- 隐藏 `configList / loadLatest`
- 运行请求同时携带 `config_id + workbench_config`
- 执行预览走 `config_json`，正式运行走 `workbench_config`

这会导致两个问题：

1. 用户无法判断“本次运行究竟基于哪一份配置”。
2. `execution_preview` 与 `run_async` 可能来自不同配置来源。

## 本轮实现

### 前端

- 顶部只保留一个可见入口：`配置中心`
- 配置中心统一展示四类来源：
  - 当前草稿
  - 锁定 Candidate
  - 内置模板
  - 已保存配置
- 当前来源提示与来源 chip 现在会明确区分：
  - 草稿运行
  - 已加载配置
  - 草稿已偏离
  - 锁定候选

### 后端

- `run_async` 新增 `runtime_config_json`
- `execution_preview` 新增 `runtime_config_json`
- `resolve_runtime_config_source()` 现在优先解析 `runtime_config_json`
- 当同时提交 `config_id + runtime_config_json` 时：
  - 若 hash 一致：`loaded_config_runtime`
  - 若 hash 不一致：`loaded_dirty_runtime`
  - `config_id` 仅保留 provenance，不得再反向覆盖 runtime config

### 元信息

本轮补齐以下 provenance 字段：

- `resolved_config_mode`
- `resolved_config_id`
- `resolved_config_hash`
- `resolved_config_source_type`
- `resolved_config_owner`

这些字段现在会出现在：

- `execution_preview` 返回
- `experiment run_async` 返回结果
- `run_meta.json -> report_consistency`

## 最小验证

### 1. saved config -> execution preview

输入：

- `config_id = cfg_clean_baseline_csi800_10y`
- `runtime_config_json = cfg_clean_baseline_csi800_10y.config_json`

结果：

- `resolved_config_mode = loaded_config_runtime`
- `config_conflict_policy = runtime_matches_config_id`

### 2. dirty draft -> execution preview

输入：

- `config_id = cfg_clean_baseline_csi800_10y`
- 在 `runtime_config_json` 中将 `breakout_window: 55 -> 50`

结果：

- `resolved_config_mode = loaded_dirty_runtime`
- `config_conflict_policy = config_id_provenance_only`

这证明“已加载配置 + 草稿偏离”现在会被显式识别，不再被静默吞掉。

### 3. saved config -> run_async

验证实验：

- `exp_20260308_005207682_89ce`

关键结果：

- `resolved_config_mode = loaded_config_runtime`
- `universe_mode = HS300_ZZ500`
- `raw_count = 800`
- `tradable_symbols = 519`

说明 clean baseline 现在确实按 runtime config json 运行，不再错误掉回 `CUSTOM 3` 只股票。

### 4. locked candidate -> run_async

验证实验：

- `exp_20260308_004957689_8ab1`

关键结果：

- `resolved_config_mode = locked_candidate`
- `candidate.status = ready`

说明旧 candidate 路径仍兼容，没有被本轮 contract 改坏。

## 对后续 results-surface change 的约束

后续结果页重排必须遵守：

1. 顶部不得重新引入第二个可见配置入口。
2. 结果页展示当前来源时，只能读取：
   - `resolved_config_mode`
   - `resolved_config_id`
   - `resolved_config_hash`
   - `resolved_config_source_type`
   - `resolved_config_owner`
3. 前端不得再根据 `config_id` 自行反查并重写当前运行真相。
4. `execution_preview` 与 `run_async` 必须继续共用同一 handoff 规则。

## 仍保留的兼容层

为避免一次性断旧链路，本轮仍保留：

- 隐藏的旧控件 DOM
- 后端 `config_json / workbench_config` 兼容解析

但这些路径现在仅作为兼容层，UI 不再对用户暴露。

# Proposal: Fix Frontend-Backend Pipeline Integrity

## Why

全链路审计发现 12 个前后端交互裂缝，导致：
- EMA 策略的 reason_code 全部错误显示为 SMA（影响诊断、统计、报告）
- 信号漏斗 raw_signal / blocked / skipped 数据全链路失真（永为 0 或极低）
- 前端 exit_rules（ATR stop/trail/time）、risk_gate 等配置发送了但后端完全丢弃
- 加载历史实验后摘要栏和 JSON 预览显示陈旧配置
- 多个计数器（time_exit、atr_trail_update）因引擎未实现或匹配逻辑错误而永为 0

## What Changes

修复 12 个问题，按 3 层分组：

### A. 引擎层（数据产出）
- A1: reason_code 按 ma_type 动态拼接，不再硬编码 SMA
- A2: `_compute_metrics()` 补充 raw_signal / blocked / orders / skipped / closed_trades
- A3: 引擎实现 TIME_EXIT 退出逻辑
- A4: atr_trail_update 计数逻辑修正

### B. 中间层（数据传递）
- B1: reversal 统计补充 EMA_CROSS_DOWN 匹配
- B2: experiment label 生成器按策略类型取 MA config
- B3: `_build_runtime_cfg_from_workbench()` 补齐 exit_rules 映射（ATR stop/trail 已有引擎支持但参数未传递）

### C. 前端层（显示/回填）
- C1: renderSummaryBar() 加载实验后用实际配置而非 config_draft
- C2: 加载实验后同步 config_draft
- C3: blocked / skipped 从引擎直接传出
- C4: diagnostics tRows 补 reversal_exit_count
- C5: compare_symbol 不硬编码

## Capabilities

- pipeline-data-integrity: 引擎到前端的数据完整性修复
- strategy-awareness: 策略类型感知（reason code、label、参数映射）
- config-hydration: 配置加载/回填正确性

## Impact

- 修改文件 ~7 个，均为现有文件
- 不新增 API 端点或数据表
- 向后兼容：所有修复均为行为修正，不改变接口契约

## 1. 配置与编译链路

- [x] 1.1 扩展 `BacktestV2ExperimentRequest` 以接收 `signal_generation` 与 `signal_composition` 两个可选配置块（DoD：请求模型可验证通过并保留现有选股字段；验证：API 请求模型单测与示例请求校验；风险：前后端字段名漂移）
- [x] 1.2 在语义编译链路中编译 `signal_generation.modules`、`signal_composition.compose_mode`、`same_symbol_policy`、`holding_ownership`（DoD：运行时配置包含新增字段且 baseline 请求不注入默认值；验证：编译器单测与 `config_snapshot` 对比；风险：隐式默认值破坏 baseline）
- [x] 1.3 为第一阶段模块白名单增加校验，仅接受 `breakout_55` 与 `rsi_reversal`（DoD：未支持模块会在编译期失败并返回明确错误；验证：负向配置测试；风险：静默回落到错误 provider）

## 2. 协议对象与上下文

- [x] 2.1 扩展 `DaySignals` 契约，增加 `raw_alpha_signals`、`composed_buy_signals`、`composed_sell_signals` 与稳定的组合诊断键（DoD：单策略与组合路径都能构造合法 `DaySignals`；验证：对象构造单测与 daily diagnostics 快照；风险：旧调用方读取字段时报错）
- [x] 2.2 扩展 `DayContext` 只读快照，向信号层暴露 `holding_sources` 归因信息（DoD：信号层可读取持仓来源且不能反向修改引擎状态；验证：上下文快照单测；风险：可变引用导致状态污染）
- [x] 2.3 调整 SignalProvider 路由与接口，使组合路径不会错误回落到 SMA provider（DoD：启用组合配置时走专用组合 provider 或等价路径；验证：路由单测与 provider 选择断言；风险：动量/反转被错误解释为 SMA 逻辑）

## 3. 多 alpha 组合运行时

- [x] 3.1 在 `S6` 内实现 `S6a` 原始信号生成与 `S6b` 组合决策流转（DoD：原始信号与组合后信号对象能在同一交易日完整生成；验证：组合 provider/adapter 单测；风险：把组合逻辑误塞进 `S7`）
- [x] 3.2 实现第一阶段 `regime_route` 组合模式，基于 `S2-S5` 可见输出启停 `breakout_55` 与 `rsi_reversal`（DoD：不同 regime 下模块启停结果可重复；验证：固定输入快照测试；风险：使用未来时点或重复计算 regime）
- [x] 3.3 实现 `same_symbol_policy = prefer_higher_score` 的确定性冲突裁决（DoD：同股双买仅保留一条组合信号并记录 `conflict_resolution`；验证：冲突样例测试；风险：依赖遍历顺序造成非确定性）
- [x] 3.4 在 `S7` 接入 `hard_sleeve_budget`，只消费组合后的最终信号（DoD：订单规划按 sleeve 预算约束执行且不读取原始信号；验证：订单规划单测与候选审计快照；风险：预算逻辑与现有仓位上限冲突）

## 4. 来源归因与审计产物

- [x] 4.1 为订单、成交、持仓补齐 `entry_alpha_id`、`entry_sleeve_id`、`entry_reason_code`、`entry_date` 的透传链路（DoD：买入成交后持仓可追溯来源，未成交订单不落持仓来源；验证：orders/trades/holding 状态测试；风险：归因字段只写入部分链路）
- [x] 4.2 在 `S9` 实现 `source_only` 退出所有权，并在 `S8` 保留 `global_risk_override` 覆盖标记（DoD：来源不匹配卖出不会误杀持仓，全局风控强平会显式标记；验证：退出归因场景测试；风险：策略退出与风控退出混淆）
- [x] 4.3 扩展 `audit.json`、组合诊断计数与相关 reason_code 输出（DoD：审计可见原始信号数、组合后信号数、冲突裁决、来源退出与全局覆盖退出；验证：audit schema 测试与产物快照；风险：新增字段缺少稳定键名）
- [x] 4.4 扩展 `orders.csv`、`trades.csv` 或等价产物中的来源字段，保证 UI 和研究审计可追溯（DoD：来源字段在产物中可读；验证：导出文件快照；风险：产物协议与前端消费不一致）

## 5. 回归验证与启用准备

- [x] 5.1 为 baseline 单策略路径增加回归测试，确认未启用组合配置时结果不变（DoD：baseline 指标或关键产物与变更前一致；验证：回归测试与快照对比；风险：新增字段触发隐式行为变化）
- [x] 5.2 为组合路径增加 T+1、同股冲突、来源退出、全局覆盖四类核心场景测试（DoD：四类场景均有可重复自动化测试；验证：测试套件通过；风险：只测 happy path）
- [x] 5.3 运行第一阶段样例 `breakout_55 + rsi_reversal + regime_route`，生成可复现命令与产物说明（DoD：形成最小验收 run，包含 config snapshot、audit、orders、trades；验证：人工审阅产物与命令复跑；风险：样例依赖本地临时配置无法复现）
  已验证容器内复跑命令，验收样例 exp_id=`exp_20260309_011329170_a9f5`，产物含 `compiled_plan.json`、`audit.json`、`orders.csv`、`trades.csv` 与配置快照。

## ADDED Requirements

### Requirement: core 热点文件必须按职责持续拆分且不得改变 V10.1 结果
系统 MUST 对 `backend/core` 中的大型热点文件进行职责拆分，包括但不限于 helper 抽离、类型收口、纯函数搬移和模块边界澄清。该拆分 SHALL NOT 改变 `baseline_V10.1 -> exp_20260314_144548534_7db9` 的执行时点、成交规则、绩效结果和 counters。

#### Scenario: 拆分 engine_vector 热点文件
- **WHEN** 系统拆分 `breakout_signal_provider.py`、`strict_runtime_impl.py` 或同等级热点文件
- **THEN** 拆分 MUST 只移动纯逻辑、类型或 helper
- **THEN** 拆分后 `baseline_V10.1` 的 perf 和 counters MUST 保持不变

#### Scenario: 拆分 portfolio 或 service 热点文件
- **WHEN** 系统拆分 `portfolio_builder.py`、`market_snapshot_service.py` 或其他热点文件
- **THEN** 新边界 MUST 让职责更单一、依赖方向更清晰
- **THEN** 该拆分 SHALL NOT 顺手引入新的研究行为变化

### Requirement: core 热点拆分必须优先服务多资产扩展
系统 MUST 让 `backend/core` 热点拆分优先消除会阻碍多资产接入的耦合点，例如把当前 A 股特化展示逻辑、历史配置语义或研究级临时逻辑继续固化在核心主干中。

#### Scenario: 新资产需要复用现有核心模块
- **WHEN** 后续资产类型需要复用某个核心模块
- **THEN** 拆分后的模块 MUST 提供清晰的输入输出与单一职责
- **THEN** 新资产接入 SHALL NOT 被旧耦合结构阻塞

## ADDED Requirements

### Requirement: 宽基ETF独立主线必须继续受统一Governor管控
系统 MUST 提供 `cn-broad-based-etf-standalone-mainline` 能力，将宽基 ETF 研究线定义为受统一 Governor/CTA 管控的独立主线。该主线 MUST 消费与其他 A 股 sleeve 相同的 canonical 5-state、总风险边界和预算真相，但 SHALL 在该边界内保留本地主线级的进入、退出和暴露响应逻辑。

#### Scenario: 宽基ETF主线消费统一Governor真相
- **WHEN** 系统运行宽基 ETF 独立主线研究
- **THEN** 该主线 MUST 消费统一 Governor 输出的 `effective_state_5`、总风险预算和防守/回撤状态
- **THEN** 系统 SHALL NOT 为该主线创建第二套独立 regime 或独立 Governor 真相源

### Requirement: 宽基ETF独立主线必须具备自己的进入退出逻辑
宽基 ETF 独立主线 MUST 明确定义自己的 enter/exit 逻辑、绝对过滤、相对排序、持仓槽位与 fallback 语义。该逻辑 SHALL NOT 默认继承个股 alpha 的部署风格，也 SHALL NOT 仅被解释为“辅助 beta sleeve”。

#### Scenario: 宽基ETF主线拥有本地进入退出决策
- **WHEN** Governor 允许 ETF 主线在当前交易日部署风险预算
- **THEN** 宽基 ETF 主线 MUST 仍可依据本地 enter/exit 逻辑决定是否入场、换仓或退出
- **THEN** 产物 MUST 能区分“Governor 不允许部署”和“Governor 允许但 ETF 主线自身未入场”

### Requirement: 宽基ETF主线必须允许受控承接而不是无约束抄底
宽基 ETF 独立主线 MUST 支持 `controlled_accumulation` 语义：在 Governor 许可的状态带宽内，宽基 ETF 可以保留或分层增加部分暴露以承接更便宜的筹码。该能力 MUST 受 `target_exposure`、`min_deployable_exposure`、最大承接上限和显式 `reason_codes` 约束。

#### Scenario: 宽基ETF在受控弱环境中承接便宜筹码
- **WHEN** Governor 状态进入系统定义的受控承接带宽，且宽基 ETF 主线仍满足本地部署条件
- **THEN** 系统 MUST 允许主线维持或增加部分宽基 ETF 暴露
- **THEN** 产物 MUST 显式记录承接发生的状态带宽、目标暴露和 `reason_codes`

#### Scenario: 宽基ETF不得在无约束条件下抄底
- **WHEN** Governor 状态处于系统定义的禁做区间或超过承接上限
- **THEN** 系统 MUST 阻止宽基 ETF 主线继续增加风险暴露
- **THEN** 系统 MUST 通过 `reason_codes` 或等价字段说明禁做原因

### Requirement: 本轮宽基ETF独立主线不得混入行业ETF
`cn-broad-based-etf-standalone-mainline` 当前范围 MUST 仅研究宽基 ETF。系统 SHALL NOT 在该主线中混入行业 ETF、主题 ETF 或其他更快风格轮动资产。

#### Scenario: 宽基主线拒绝行业ETF
- **WHEN** 研究配置尝试将行业 ETF 或主题 ETF 纳入该主线
- **THEN** 系统 MUST 返回显式错误、告警或研究边界标记
- **THEN** 系统 SHALL NOT 将其静默视为宽基主线的一部分

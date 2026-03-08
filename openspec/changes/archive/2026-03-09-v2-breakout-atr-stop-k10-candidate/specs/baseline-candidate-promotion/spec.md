## ADDED Requirements

### Requirement: 候选方案必须以锁定 baseline 为输入真相
系统 SHALL 以锁定 baseline `exp_20260307_051743747_77d8` 的已解析运行时配置作为候选构建起点，不得通过预设名、代码默认值或前端草稿隐式推断候选参数。

#### Scenario: 候选从锁定 baseline 派生
- **WHEN** 系统构建 `v2-breakout-atr-stop-k10-candidate` 的运行时配置
- **THEN** 候选配置 SHALL 以锁定 baseline 的 `run_config.json` 为源配置
- **THEN** 候选配置 SHALL 只允许声明的目标参数偏移

#### Scenario: 基线来源不可解析
- **WHEN** 锁定 baseline 的配置文件或元信息缺失、损坏或不可解析
- **THEN** 系统 SHALL 拒绝构建候选配置
- **THEN** 候选状态 SHALL 保持未就绪

### Requirement: 候选方案默认关闭且可回退
系统 SHALL 将正式候选与 baseline 默认行为分离。未显式启用候选时，系统必须继续采用 baseline 语义；取消候选后，系统必须能够无迁移回退。

#### Scenario: 未启用候选时保持 baseline
- **WHEN** 运行请求未显式选择 `v2-breakout-atr-stop-k10-candidate`
- **THEN** 运行时配置 SHALL 保持 baseline 的 `strategy.params.atr_stop_k=1.2`
- **THEN** 系统 SHALL 不得静默切换到 `1.0`

#### Scenario: 启用候选时仅改变目标参数
- **WHEN** 运行请求显式选择 `v2-breakout-atr-stop-k10-candidate`
- **THEN** 运行时配置 SHALL 将 `strategy.params.atr_stop_k` 设为 `1.0`
- **THEN** 其余 baseline 约束 SHALL 保持不变

#### Scenario: 取消候选后无迁移回退
- **WHEN** 用户取消候选启用或候选审计失败
- **THEN** 后续运行 SHALL 恢复 baseline 语义
- **THEN** 系统 SHALL 不要求迁移历史产物或重写历史实验

### Requirement: 候选 readiness 必须附带审计证据包
系统 SHALL 仅在证据包完整且未发现未来函数或时间错位风险时，才允许把研究优胜方案标记为正式候选。

#### Scenario: 正式候选证据包完整
- **WHEN** `atr_stop_k=1.0` 被标记为 ready for implementation
- **THEN** 证据包 SHALL 包含全样本对照、局部稳健性、分段窗口检查、终点敏感性检查和对应实验 `exp_id`
- **THEN** 证据包 SHALL 明确记录当前候选相对 baseline 的已知 trade-off

#### Scenario: 审计风险阻断候选推进
- **WHEN** 证据包中发现未来函数、时间错位或非目标参数漂移
- **THEN** 系统 SHALL 阻止候选进入 implementation 阶段
- **THEN** 结论 SHALL 明确标记为审计未通过

### Requirement: 候选方案不得破坏研究合同
正式候选的比较 SHALL 保持锁定 baseline 的研究合同不变，包括成本、股票池、执行与评价口径；若使用 `t` 日收盘生成信号，候选仍 MUST 在 `t+1` 执行。

#### Scenario: 比较口径保持一致
- **WHEN** 系统比较 baseline 与 `v2-breakout-atr-stop-k10-candidate`
- **THEN** 手续费、滑点、股票池、成交规则、benchmark 和评价口径 SHALL 保持一致

#### Scenario: 候选继续遵守 T+1
- **WHEN** 候选沿用 `t` 日收盘数据生成信号
- **THEN** 订单 SHALL 排入下一交易日执行
- **THEN** 候选不得在信号日当日成交

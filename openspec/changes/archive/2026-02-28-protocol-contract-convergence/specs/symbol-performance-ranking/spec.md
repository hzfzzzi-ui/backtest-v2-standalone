## MODIFIED Requirements

### Requirement: 回测结果必须输出个股绩效汇总产物
系统 MUST 在每次实验完成后输出可读取的个股绩效汇总产物，至少包含每个 symbol 的收益率、回撤、净收益、交易次数与未平仓近似收益字段。

#### Scenario: 实验完成并生成标准产物
- **WHEN** 回测任务状态变为成功并写入 artifacts
- **THEN** 系统 SHALL 生成 `symbol_performance.csv` 产物
- **THEN** `result.artifacts.symbol_performance` SHALL 指向该文件的相对路径
- **THEN** 每条记录 SHALL 至少包含 `symbol`, `return_pct`, `max_drawdown`, `net_pnl`, `trades`, `unrealized_approx_pnl`

## ADDED Requirements

### Requirement: 个股绩效产物必须支持空文件降级
系统 MUST 在无法计算个股绩效时写出合法空产物，避免协议缺失。

#### Scenario: 无交易或无可用估值数据
- **WHEN** 回测期间无交易记录，或个股估值数据不可用
- **THEN** 系统 SHALL 写出 `symbol_performance.csv` 且仅包含表头或空记录
- **THEN** 系统 SHALL 在 `run_meta.missing_fields` 记录对应缺失来源

#### Scenario: 前端读取空个股绩效产物
- **WHEN** 前端加载 `symbol_performance.csv` 且无数据行
- **THEN** 前端 SHALL 显示空状态而非报错
- **THEN** 其他绩效面板与图表 SHALL 正常工作

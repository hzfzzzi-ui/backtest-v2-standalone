## ADDED Requirements

### Requirement: 回测结果必须输出个股绩效汇总产物
系统 MUST 在每次实验完成后输出可读取的个股绩效汇总产物，至少包含每个 symbol 的收益率、回撤、净收益、交易次数与未平仓近似收益字段。

#### Scenario: 实验完成并生成标准产物
- **WHEN** 回测任务状态变为成功并写入 artifacts
- **THEN** 系统 SHALL 生成 `symbol_performance` 产物（csv 或 json）
- **THEN** 每条记录 SHALL 至少包含 `symbol`, `return_pct`, `max_drawdown`, `net_pnl`, `trades`, `unrealized_approx_pnl`

### Requirement: 未平仓收益必须按区间末日收盘价近似估值
系统 MUST 对未平仓仓位进行近似估值，估值价格使用回测区间最后日期的收盘价（若缺失则回溯最近可用收盘价），并计入个股收益统计。

#### Scenario: 存在未平仓仓位且末日有收盘价
- **WHEN** 某 symbol 在回测结束时仍有持仓且末日收盘价可用
- **THEN** 系统 SHALL 使用末日收盘价计算未平仓近似收益
- **THEN** 该收益 SHALL 计入 `net_pnl` 与 `return_pct`

#### Scenario: 末日收盘价缺失
- **WHEN** 某 symbol 末日收盘价缺失但历史存在更早可用收盘价
- **THEN** 系统 SHALL 使用最近可用收盘价进行估值
- **THEN** 产物 SHALL 标记估值使用了回溯价格

### Requirement: 前端榜单必须支持按收益降序与个股筛选
前端 MUST 提供个股绩效榜单，默认按收益率从高到低排序，并支持按 symbol 筛选查看。

#### Scenario: 初次加载个股绩效榜单
- **WHEN** 用户打开包含有效回测产物的结果页
- **THEN** 榜单 SHALL 按 `return_pct` 从高到低展示
- **THEN** 榜单 SHALL 显示至少 symbol、收益率、回撤、交易次数

#### Scenario: 用户输入 symbol 筛选
- **WHEN** 用户选择或输入指定 symbol
- **THEN** 榜单 SHALL 仅显示匹配 symbol 的记录
- **THEN** 图表数据源 SHALL 同步切换到该 symbol

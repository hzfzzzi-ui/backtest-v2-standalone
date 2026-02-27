## ADDED Requirements

### Requirement: 实验索引文件
系统 SHALL 在 `outputs/experiments/index.json` 维护一个全局实验索引，每次回测完成后自动追加。

#### Scenario: 回测完成后追加索引
- **WHEN** 一次回测实验成功完成并通过 stabilize 阶段
- **THEN** 系统 SHALL 在 index.json 中追加一条记录，包含 exp_id、label、created_at、status、total_return、max_drawdown、sharpe、trades、has_report 字段

#### Scenario: 自动生成可读标签
- **WHEN** workbench_config 包含 strategy="SMA_CROSS", sma.fast_ma=5, sma.slow_ma=20, universe_mode="CUSTOM", 2 只标的, price_adj="hfq", 区间 2024-01~06
- **THEN** label 字段 SHALL 为 "SMA_CROSS 5/20 | CUSTOM 2只 | HFQ | 2024-01~06"

#### Scenario: index.json 不存在时自动创建
- **WHEN** index.json 文件不存在（首次运行或清空后）
- **THEN** 系统 SHALL 创建新的 index.json 并写入 `[{...}]`

---

### Requirement: 实验列表 API
系统 SHALL 提供 `GET /api/backtest_v2/experiments` 端点返回实验列表。

#### Scenario: 正常返回列表
- **WHEN** 客户端调用 GET /api/backtest_v2/experiments
- **THEN** 系统 SHALL 返回 index.json 内容，按 created_at 倒序排列（最新在前）

#### Scenario: 无实验时返回空列表
- **WHEN** index.json 为空或不存在
- **THEN** 系统 SHALL 返回 `[]`

#### Scenario: 孤儿记录自动清理
- **WHEN** index.json 中某条记录的实验目录已不存在
- **THEN** 系统 SHALL 在返回列表时过滤掉该条记录，并更新 index.json

---

### Requirement: 实验报告查看 API
系统 SHALL 提供 `GET /api/backtest_v2/experiments/{exp_id}/report` 端点返回 report.html。

#### Scenario: report.html 存在
- **WHEN** 客户端请求某实验的报告且 report.html 存在
- **THEN** 系统 SHALL 返回 HTML 内容（Content-Type: text/html）

#### Scenario: report.html 不存在
- **WHEN** 客户端请求某实验的报告但 report.html 不存在
- **THEN** 系统 SHALL 返回 404

---

### Requirement: 删除单个实验 API
系统 SHALL 提供 `DELETE /api/backtest_v2/experiments/{exp_id}` 端点删除单个实验。

#### Scenario: 删除成功
- **WHEN** 客户端调用 DELETE 且实验目录存在
- **THEN** 系统 SHALL 删除实验目录及所有内容，从 index.json 移除对应记录，返回 `{"status": "deleted"}`

#### Scenario: 实验不存在
- **WHEN** 客户端调用 DELETE 但实验目录不存在
- **THEN** 系统 SHALL 返回 404

---

### Requirement: 清空所有实验 API
系统 SHALL 提供 `DELETE /api/backtest_v2/experiments` 端点清空所有实验。

#### Scenario: 清空成功
- **WHEN** 客户端调用 DELETE /api/backtest_v2/experiments
- **THEN** 系统 SHALL 删除 experiments 目录下所有 exp_* 子目录，重置 index.json 为 `[]`，返回 `{"status": "cleared", "count": N}`

---

### Requirement: stock_names.json 持久化
系统 SHALL 在 stabilize 阶段将中文股票名查询结果写入 `stock_names.json`。

#### Scenario: 正常写入
- **WHEN** portfolio_trades.csv 包含 symbol 列，含 600519.SH 和 000001.SZ
- **THEN** 系统 SHALL 查询 DB 获取中文名称，写入 stock_names.json 如 `{"600519.SH": "贵州茅台", "000001.SZ": "平安银行"}`

#### Scenario: 无交易记录
- **WHEN** portfolio_trades.csv 不存在或为空
- **THEN** 系统 SHALL 写入空 `stock_names.json` 如 `{}`

---

### Requirement: tier 持久化到 run_meta.json
系统 SHALL 在 stabilize 阶段将策略评级 tier 写入 run_meta.json。

#### Scenario: tier 写入
- **WHEN** 回测结果包含 tier 字段
- **THEN** run_meta.json 顶层 SHALL 包含 `"tier": "T0"` 字段

---

### Requirement: 前端 History 面板
前端 SHALL 在 Drawer 中新增「实验历史」面板，通过 Rail 第 5 个图标切换。

#### Scenario: 面板展示实验列表
- **WHEN** 用户点击 History 图标
- **THEN** Drawer SHALL 显示实验历史面板，包含所有实验卡片，按时间倒序排列

#### Scenario: 实验卡片内容
- **WHEN** 面板渲染一个实验
- **THEN** 卡片 SHALL 显示：可读标签（策略名/参数）、回测区间、核心指标（收益/回撤/夏普/交易数）、创建时间、「查看报告」和「加载结果」两个按钮

#### Scenario: 查看报告
- **WHEN** 用户点击「查看报告」按钮
- **THEN** 系统 SHALL 在新标签页打开该实验的 report.html

#### Scenario: 加载结果到工作台
- **WHEN** 用户点击「加载结果」按钮
- **THEN** 系统 SHALL 加载该实验的全部产物到 state.active_artifacts，覆盖当前工作台状态，并刷新所有面板

#### Scenario: 空状态
- **WHEN** 实验列表为空
- **THEN** 面板 SHALL 显示空状态提示「暂无实验记录，运行回测后将自动保存」

#### Scenario: 清空全部
- **WHEN** 用户点击「清空」按钮并确认
- **THEN** 系统 SHALL 调用 DELETE /api/backtest_v2/experiments 清空所有实验，刷新面板

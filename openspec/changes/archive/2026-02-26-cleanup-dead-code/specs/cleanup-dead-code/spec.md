## REMOVED Requirements

### Requirement: 孤立前端文件
前端目录中不再保留与回测 V2 工作台无关的 JS 文件。

#### Scenario: 删除孤立文件后系统正常
- **WHEN** 删除 cashflow.js、dashboard.js、strategy.js、watchlist.js、holdings.js、holdings_detail.js、holdings_categories.js、backtest.js
- **THEN** `index.html` 加载正常，回测功能不受影响

**Reason**: 这些文件属于另一个交易管理系统，从未被当前 `index.html` 引用
**Migration**: 无需迁移，代码保留在 git 历史中

### Requirement: 后端废弃端点
后端不再保留已返回 410 Gone 的旧版回测端点。

#### Scenario: 删除废弃端点
- **WHEN** 删除 `POST /api/backtest_v2/run` 和 `POST /api/backtest_v2/run_async`
- **THEN** 现有前端功能不受影响（前端使用 `/experiment/run_async`）

**Reason**: 这两个端点已返回 HTTP 410 Gone，无任何客户端调用
**Migration**: 使用 `POST /api/backtest_v2/experiment/run_async`

### Requirement: 后端死函数
后端不再保留从未被调用的内部函数。

#### Scenario: 删除死函数
- **WHEN** 删除 `infer_tier()`、`_write_experiment_click_report()`、`_promote_single_md_report()`
- **THEN** 所有 API 端点正常工作，Docker 构建成功

**Reason**: 经代码分析确认，这三个函数在整个代码库中无任何调用者
**Migration**: 无需迁移

## Why

项目从完整交易管理系统中独立出来时，前端残留了 8 个不再使用的 JS 文件（cashflow、dashboard、strategy、watchlist、holdings 等），它们引用了约 29 个后端不存在的 API。后端也有 3 个从未被调用的函数和 2 个已废弃的 410 端点。这些死代码增加了维护成本和理解难度，需要清理。

## What Changes

- **删除** 8 个孤立前端 JS 文件：`cashflow.js`、`dashboard.js`、`strategy.js`、`watchlist.js`、`holdings.js`、`holdings_detail.js`、`holdings_categories.js`、`backtest.js`
- **删除** 后端 3 个从未被调用的函数：`infer_tier()`、`_write_experiment_click_report()`、`_promote_single_md_report()`
- **删除** 后端 2 个已废弃端点：`POST /api/backtest_v2/run`（410 Gone）、`POST /api/backtest_v2/run_async`（410 Gone）
- **删除** 临时文件 `backend/tmp_query_symbols.py`
- **确认** `utils.js` 是否被 `backtest_v2.js` 引用，若无引用则一并删除

## Capabilities

### New Capabilities

（无新增能力，纯清理变更）

### Modified Capabilities

（无需求层面的变更，仅删除未使用代码）

## Impact

- **前端**：删除 8 个 JS 文件（~3000 行），不影响 `index.html` 或 `backtest_v2.js` 的功能
- **后端**：删除 `backtest_v2.py` 中约 140 行死代码 + 1 个临时脚本文件
- **API**：无现有功能受影响（删除的端点已返回 410 Gone）
- **测试**：需验证删除后 Docker 构建和回测功能正常

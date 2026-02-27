## 1. 确认依赖关系

- [x] 1.1 检查 `utils.js` 是否被 `backtest_v2.js`、`api.js` 或 `ui.js` import，若无引用则加入删除清单。验证：grep 搜索 `utils` 在保留文件中的引用数为 0。

## 2. 删除前端孤立文件

- [x] 2.1 删除以下 9 个前端 JS 文件（含 utils.js，确认无引用）：`frontend/assets/cashflow.js`、`frontend/assets/js/backtest.js`、`frontend/assets/js/dashboard.js`、`frontend/assets/js/strategy.js`、`frontend/assets/js/watchlist.js`、`frontend/assets/js/holdings.js`、`frontend/assets/js/holdings_detail.js`、`frontend/assets/js/holdings_categories.js`、`frontend/assets/js/utils.js`。验证：`frontend/assets/js/` 目录仅剩 `api.js`、`backtest_v2.js`、`ui.js`。

## 3. 删除后端死函数

- [x] 3.1 从 `backtest_v2.py` 中删除 `infer_tier()` 函数（约 L183）。验证：grep `infer_tier` 返回 0 结果。
- [x] 3.2 从 `backtest_v2.py` 中删除 `_write_experiment_click_report()` 函数（约 L1417）。验证：grep `_write_experiment_click_report` 返回 0 结果。
- [x] 3.3 从 `backtest_v2.py` 中删除 `_promote_single_md_report()` 函数（约 L1487）。验证：grep `_promote_single_md_report` 返回 0 结果。

## 4. 删除废弃端点和临时文件

- [x] 4.1 从 `backtest_v2.py` 中删除 `POST /api/backtest_v2/run` 废弃端点及其关联死函数 `_run_backtest_v2_sync`、`_run_backtest_v2_job`。验证：grep 无结果。
- [x] 4.2 从 `backtest_v2.py` 中删除 `POST /api/backtest_v2/run_async` 废弃端点。验证：grep 无结果。
- [x] 4.3 删除 `backend/tmp_query_symbols.py` 临时脚本。验证：文件不存在。

## 5. 清理可能失效的 import

- [x] 5.1 检查 `backtest_v2.py` 中删除死函数后是否有 import 变为未使用（如 `subprocess`、`sys` 等），若有则一并清理。验证：`date`、`subprocess`、`sys` 均仍有其他使用处，无需清理。

## 6. 验证

- [x] 6.1 Docker 重新构建并启动（`docker compose up -d --build`），确认服务正常启动，访问前端页面无报错。验证：`curl http://localhost:8091/healthz` 返回 `{"ok":true}`，前端 HTML 正常加载。

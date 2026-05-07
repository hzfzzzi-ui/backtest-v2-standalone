## 1. 数据接入口

- [x] 1.1 为 CN ETF 刷新脚本新增 `pit_cn_etf_dividend_events` 落表与 `fund_div` 抓取。DoD：side table 可增量 upsert，provider 能查到窗口内事件。验证：新增/更新 `refresh_cn_etf_daily` 单测并跑 `pytest tests/unit/test_refresh_cn_etf_daily.py`。风险：Tushare 事件字段缺口导致事件键不稳定。
- [x] 1.2 扩展 `DataProvider` / `PostgresDataProvider` / `CachedDataProvider` / `DataBundle`，正式暴露 ETF dividend events 与 summary 统计。DoD：`cn_etf` data bundle 含事件集和事件计数，非 ETF 路径不受影响。验证：新增 data bundle/provider 单测。风险：provider 查询条件不当会漏掉跨 ex_date/pay_date 窗口事件。

## 2. 运行时记账

- [x] 2.1 在 runtime bootstrap / ledger 中加入 ETF 分红事件索引、processed event 状态与 `dividend_receivable` 账本。DoD：prepare/day loop 可在不影响股票路径的前提下读取 dividend lifecycle。验证：新增 runtime setup 单测。风险：状态字段位置选错会污染非 ETF path。
- [x] 2.2 在 open fills 前处理 ETF 分红生命周期：除息日确认权益、按 `dividend_cash_timing_mode` 入账 cash 或 receivable，并对 `position_entry_adj` 做 rebasing。DoD：不再双重计数分红，份额折算逻辑保持原样。验证：新增 `fill_accounting` 单测覆盖 `ex_date`/`pay_date` 两种口径。风险：rebasing 公式错误会扭曲 ETF NAV。
- [x] 2.3 扩展 NAV / daily snapshot / accounting snapshot，使 `pay_date` 口径下 `nav = cash + dividend_receivable + market_value`。DoD：daily/accounting 审计证据能看到 receivable 与 cash credit。验证：新增 `nav_snapshot` 与 `daily_accounting` 单测。风险：若 cash 与 receivable 混淆，会破坏可用现金语义。

## 3. 审计与回归

- [x] 3.1 扩展 `backtest-audit` / `accounting-integrity-audit` 计算逻辑，纳入 dividend cash credit 与 receivable settlement。DoD：审计公式与 spec 一致，异常样本可定位分红链路。验证：新增 `experiment_audit` 单测。风险：旧只含 BUY/SELL 的假设若未清理，会让审计误报。
- [x] 3.2 跑聚焦回归，验证 `511010` 分红窗口链路闭合且无双重计数。DoD：分红窗口 cash/NAV/receivable 行为可解释，ETF 路径无新增 20%+ 异常跳变。验证：相关单测 + 必要的脚本/实验复核。风险：只过单测不看真实窗口，可能遗漏历史脏数据。

## Rollback

- 回退 ETF 分红 side table 与 provider 接口，恢复 `cn_etf` 只依赖日线 + `adj_factor` 的旧口径。
- 回退 runtime ledger / NAV / audit 中的 dividend event 路径，恢复无显式分红现金事件的基线实现。
- 删除本 change 目录并重新挂回旧实验结果，但该回退会重新引入 ETF 分红链路不可审计问题。

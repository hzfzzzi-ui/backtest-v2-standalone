## ADDED Requirements

### Requirement: cn_etf 研究入口必须显式暴露 ETF 基准真相
当 `asset_scope=cn_etf` 时，系统 MUST 以 ETF 研究入口的 benchmark 配置作为唯一真相；若入口未显式指定 benchmark，系统 SHALL NOT 静默继承 A 股股票主线的 `000300.SH`，并 MUST 在产物中显式暴露 benchmark 来源或空值事实。

#### Scenario: ETF 入口未指定 benchmark
- **WHEN** `cn_etf` 研究 preset 将 `universe.benchmark` 设为空
- **THEN** 运行时配置与 `run_meta.json` MUST 不再静默写入 `000300.SH`
- **THEN** 系统 MUST 暴露该 benchmark 来自 ETF 入口为空或 ETF fallback 的事实

### Requirement: cn_etf 研究入口必须保持 ETF 覆盖与日线表真相
当 `cn_etf` 研究入口进入主线运行时，系统 MUST 在 `run_meta.json` 和相关摘要中保持 ETF 的 `daily_table`、`price_series_semantics`、`coverage_start` 和 `coverage_end` 真相，不得回退成股票主线默认值。

#### Scenario: ETF 运行写出 ETF 覆盖真相
- **WHEN** `asset_scope=cn_etf` 的运行结束
- **THEN** `run_meta.json` MUST 写出 `pams_cn_etf_daily`
- **THEN** 相关覆盖窗口 MUST 来源于 ETF 覆盖摘要而不是股票数据链

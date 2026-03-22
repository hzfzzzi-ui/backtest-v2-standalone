## 1. 规格固化

- [x] 1.1 补齐 `cn-daily-data-sync` 与 `market-data-freshness-status` 的变更规格。DoD: 明确 V2 主线同步顺序、skip/success 判定和 freshness 锚点；验证: `openspec validate wire-cn-daily-sync-to-v2-mainline --type change --strict` 通过；风险: 若规格仍沿用旧表口径，代码实现会继续误报 fresh。
- [x] 1.2 产出技术设计文档，说明为什么保留 legacy bridge、为什么 freshness 只认 V2 主线。DoD: design 中明确顺序、依赖、回退和风险；验证: 设计文档可独立回答“为什么不能继续看旧表日期”；风险: 若设计不清晰，后续容易再次把旧表恢复成 freshness 真相源。

## 2. 服务实现

- [x] 2.1 在 `market_data_sync_service.py` 中接入 V2 raw/main/moneyflow 更新器，并按正式依赖顺序编排。DoD: 单次 `run_cn_daily_sync_once()` 会执行 legacy bridge、index bridge、V2 raw、V2 main、V2 moneyflow、CSI800 PIT 与下游自动同步；验证: 单测断言调用顺序与 summary 字段；风险: 顺序错误会导致主表或 moneyflow 构建失败。
- [x] 2.2 将 run record 和 `build_market_data_sync_status()` 的 freshness 锚点切到 V2 主线。DoD: skipped/success/stale/fresh 都基于 `pams_ohlcv_daily_v2 + pit_stock_moneyflow_v2 + whitelist`；验证: 单测覆盖旧表已新但 V2 落后、V2 全齐成功、moneyflow 落后失败；风险: 若只改 run summary 不改 status 聚合，前端仍会误判。

## 3. 回归验证

- [x] 3.1 更新 `tests/unit/test_market_data_sync_service.py`，覆盖 V2 主线成功与失败语义。DoD: 至少覆盖顺序、skip 口径、success 口径、DB fallback 口径；验证: `pytest tests/unit/test_market_data_sync_service.py -q` 通过；风险: 旧测试若仍按 legacy 口径断言，会掩盖主线回归。
- [x] 3.2 执行 OpenSpec 与单测回归，记录可回退边界。DoD: OpenSpec 严格校验和目标单测都通过，且回退仅需撤销服务层改动；验证: `openspec validate ... --strict` + `pytest ...`; 风险: 如果只跑单测不跑 spec 校验，这次 L3 变更会留下流程债务。

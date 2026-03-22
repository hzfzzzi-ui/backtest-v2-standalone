## Why

当前 `pams_ohlcv_daily` 在 `2025-09-18` 到 `2026-02-13` 期间存在原始 `adj_factor` 缺口。研究运行时虽然会在 `pg_provider` 规范化阶段对 `adj_factor` 做前向填充并兜底 `1.0`，但这会把原始数据缺口静默掩盖掉，导致：

- `hfq` 信号价格实际依赖“填充后的 adj_factor”，而不是完整原始数据；
- `1626/0726` 这类包含 2025-2026 尾段的窗口存在可解释性和可审计性风险；
- 日常 `update_pams_ohlcv_daily` 同步链路只按“最新交易日 + 1”增量推进，没有正式的历史缺口修复入口；
- `market_data_sync_service` 当前只按“是否追到目标交易日”判断成功，无法把 `adj_factor` 缺口识别成同步失败。

这个问题不应继续依赖人工 SQL 排查或运行时静默填充。系统需要一个正式的 `adj_factor` 缺口修复与同步审计路径。

## What Changes

- 为 `update_pams_ohlcv_daily` 增加显式的 `adj_factor` 缺口修复模式，在给定日期范围内只重抓当前库里存在 `adj_factor IS NULL` 的交易日。
- 为更新 summary 增加 `adj_factor` 完整性审计字段，至少覆盖修复前命中的缺口日期、修复后剩余缺口日期、剩余缺口行数与完整性布尔结果。
- 调整 `market_data_sync_service` 的成功判定：即使已经追到目标交易日，只要本次同步覆盖的交易日仍存在 `adj_factor` 缺口，就必须标记为失败，而不是静默成功。
- 补充 `update_pams_ohlcv_daily` 与 `market_data_sync_service` 的单元测试，覆盖 repair 模式与同步失败判定。

## Capabilities

### Modified Capabilities

- `price-adjustment`: `adj_factor` 相关能力不再只依赖运行时前向填充，系统必须提供正式的历史缺口修复入口，并把同步后仍存在的原始缺口视为数据完整性失败。

## Impact

- 影响代码主要在 `backend/cli/managed/update_pams_ohlcv_daily.py`、`backend/core/services/market_data_sync_service.py` 与对应测试。
- 不修改 `baseline_V10.1` 配置，不修改研究信号逻辑，不引入新的 provider 主链。
- 本次改动属于数据口径修复与同步治理，默认保持现有增量同步行为，仅新增显式 repair 能力与更严格的失败判定。

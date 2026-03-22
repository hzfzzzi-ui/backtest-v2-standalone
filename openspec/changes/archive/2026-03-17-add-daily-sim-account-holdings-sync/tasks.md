## 1. 指数日更桥接

- [x] 1.1 将 `update_pit_index_daily` 接入 `run_cn_daily_sync_once()`。DoD: run summary 新增 `pit_index_daily_refresh`，scheduler 成功后 `pit_index_daily` 能追上目标交易日；验证: `test_market_data_sync_service.py` + 实库只读核验；风险: 若导入失败，必须显式失败而不是静默跳过。
- [x] 1.2 为 `pit_index_daily` 增量导入补最小回归。DoD: 覆盖“成功接入 summary”和“导入异常导致 scheduler failed”；验证: unit test；风险: 不能破坏现有 `csi800_pit` 刷新顺序。

## 2. 模拟盘自动导入服务

- [x] 2.1 新增 `sim_account_auto_sync_service`，实现“读取 JSON 文件 -> 标准化 snapshot -> 状态落盘”。DoD: 新服务只负责外部导入边界，不改现有 snapshot schema；验证: unit test 覆盖 success/file missing/invalid payload；风险: 不得覆盖旧 `latest.json`。
- [x] 2.2 在自动导入成功后触发 `run_position_aware_reconcile()`。DoD: `reconcile/latest.json` 与新 snapshot 绑定，默认使用 scheduler target date 作为 `strategy_as_of_date`；验证: unit test；风险: 日期错位会直接污染 trade sheet。
- [x] 2.3 新增 `auto_sync_status.json` 读写。DoD: 至少返回 `status/account_id/source_path/snapshot_id/trade_date/reconcile_id/message/updated_at`；验证: unit test；风险: 失败状态不能被成功状态残留覆盖。

## 3. 每日调度串联

- [x] 3.1 将模拟盘自动导入接入每日 scheduler，并放在市场数据同步之后。DoD: scheduler run summary 记录 `sim_account_auto_sync` 子结果；验证: `test_market_data_sync_service.py`；风险: 运行链变长后，summary 必须保留各步骤状态，便于定位故障。
- [x] 3.2 为导入路径提供环境变量配置与 disabled 行为。DoD: 未配置时 scheduler 不报错，但 summary 明确返回 disabled；验证: unit test；风险: 不能让“未配置”伪装成成功。

## 4. 验证与文档

- [x] 4.1 增加集成回归，覆盖“市场同步 -> 持仓导入 -> reconcile 刷新”闭环。DoD: 至少有一条 integration 或 service-level 回归；验证: pytest；风险: 不能只测单模块而遗漏串联问题。
- [x] 4.2 补运行说明。DoD: 文档说明外部 JSON 文件格式、环境变量、失败回退；验证: 手工按文档跑通一次；风险: 若导入格式不透明，后续运维会重复踩坑。

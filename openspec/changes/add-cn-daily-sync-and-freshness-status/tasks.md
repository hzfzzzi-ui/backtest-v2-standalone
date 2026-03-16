## 1. 同步真相源

- [x] 1.1 新增 `pams_data_sync_runs` 或等价同步状态真相源。DoD: 能持久化 `sync_key/target_trade_date/status/started_at/finished_at/latest_trade_date_before/latest_trade_date_after/error_text/summary_json`；验证: 建表初始化 + 读写单测；风险: 当前仓库无完整 migration 框架，需避免脏启动失败。
- [x] 1.2 实现基于活交易日历源的前一交易日解析服务。DoD: 能在交易日、周末、节假日场景返回正确 `target_trade_date`，且不依赖停更的库内旧表；验证: 针对交易日历样本的单测；风险: 日历缺失时必须显式失败，不能静默退化为自然日。

## 2. 定时同步执行链

- [x] 2.1 抽取 `update_pams_ohlcv_daily` 的可复用执行入口。DoD: scheduler 可直接复用正式写库链路并保留现有摘要字段；验证: 现有 CLI 仍可运行，新增服务入口单测通过；风险: 若复制逻辑而非复用，会形成第二套抓数真相源。
- [x] 2.2 在 backend 服务中接入后台日更调度器与互斥保护。DoD: 支持环境变量控制启停/时间/时区，单实例内不重入，且推荐具备数据库 advisory lock；验证: 启动后可模拟到点触发并写入状态表；风险: 后台异常不得阻断 FastAPI 主服务。
- [x] 2.3 实现成功/失败/跳过状态写回。DoD: 成功同步、重复已新鲜、交易日历异常、数据源异常都能写出可审计状态；验证: 覆盖 success/stale/failed 场景的测试或脚本回放；风险: 若只写成功不写失败，前端无法判断是否需要人工介入。

## 3. API 状态面

- [x] 3.1 新增 `/api/backtest_v2/market_data/sync_status` 薄接口。DoD: 返回 `latest_success_trade_date/target_trade_date/status/lag_days/last_run_started_at/last_run_finished_at/message` 等最小状态对象；验证: 路由测试与序列化快照；风险: 不得把系统状态塞进实验 `surface` 导致边界混乱。
- [x] 3.2 实现 freshness 状态聚合语义。DoD: 能稳定区分 `fresh/stale/running/failed/never_synced/disabled`；验证: 用状态表样本和空库样本做聚合测试；风险: 若状态机定义含糊，前端会再次回到“自己猜状态”。

## 4. 前端显性展示

- [x] 4.1 在桌面 A 股系统顶部显性展示“最新同步日期”。DoD: 页面初始化后可见最新同步日期或显式状态文案，不依赖加载某个实验结果；验证: 前端构建通过 + 手工页面检查；风险: 禁止把缺失日期渲染为空白、`0` 或误导性正常状态。
- [x] 4.2 在状态中心展示同步详情与异常提示。DoD: fresh/stale/failed/running/never_synced/disabled 都有明确展示，失败时能看到错误摘要或 lag 信息；验证: mock API 响应驱动 UI 状态检查；风险: 不能让系统同步状态和实验 API 错误提示互相覆盖。

## 5. 部署与回归验证

- [x] 5.1 补齐 `docker-compose` 与环境变量默认值。DoD: standalone 环境具备正式启停开关、默认触发时间和 Tushare token 入口；验证: compose 配置检查 + 容器启动验证；风险: 默认值不当会导致过早触发或完全不运行。
- [ ] 5.2 完成端到端回归与回退说明。DoD: 能通过一次手动触发或模拟调度验证写库、状态接口和前端展示三者一致，并记录关闭调度的回退方式；验证: 数据库查询 + API 返回 + 前端截图/人工核对；风险: 若只验证单层，将无法证明“写库真相源”和“前端显示”一致。

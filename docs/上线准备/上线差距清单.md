# 上线差距清单

本清单服务于“个人多资产趋势配置系统”的上线准备审计。当前结论：本仓库不是生产 READY 状态；已勾选项只表示 repo 内可验证边界，未勾选项必须关闭后才能标记正式上线。

## 1. 产品与文档

- [x] 根目录 `README.md` 使用正式产品名。
- [x] 所有核心文档使用“个人多资产趋势配置系统”作为正式定位。
- [x] 文档明确 PAMS 是独立资产管理系统。
- [x] 文档明确研究平台不直接接券商下单。
- [x] 文档明确 `outputs/` 不是源码主路径。
- [x] 文档明确当前状态不是生产 READY 声明。

## 2. 命名治理

- [x] 新增正式命名清单。
- [x] 新增废弃命名清单。
- [x] 文档不再把 `backtest_V2_standalone` 作为产品名。
- [x] 文档不再把 `PAMS/pams_` 作为研究平台正式命名前缀。
- [x] `shadow` 和 `AB` 已映射到 `diagnostic_probe` 和 `controlled_experiment`。
- [ ] 仓库目录仍为 `backtest_V2_standalone`，尚未完成正式仓库名迁移。
- [ ] `pams_ohlcv_daily_v2`、`pams_cn_etf_daily` 等历史表名仍在兼容期，尚未完成 canonical market 命名迁移。

## 3. API 表面

- [x] `python_api_routes.csv` 不存在无说明的重复 `method + path`。
- [x] `routes/*` 是唯一 HTTP decorator owner。
- [x] impl/service 层不声明 route decorator。
- [x] API 层不调用另一个 API route 函数。
- [x] API 返回无 NaN/Inf。
- [x] API schema 有测试覆盖。

## 4. 研究主链

- [x] baseline 主逻辑有回归测试。
- [x] 信号时点、成交时点、价格口径显式记录。
- [x] 三窗口研究纪律仍可执行。
- [x] controlled experiment 不会自动改变 baseline。
- [x] diagnostic probe 不会进入 live 发布路径。

## 5. 数据主链

- [x] Tushare 已进入 raw vendor 层。
- [x] 上层通过 canonical market data 访问。
- [x] 字段 source matrix 存在。
- [x] 停牌、退市、缺口、合成补位有显式状态。
- [x] 数据 freshness 状态可查询。
- [ ] iFinD raw vendor 同步器未实现；当前仅保留 raw vendor 合同和预留命名。
- [ ] TradingView 和 IBKR 未实现生产数据接入，不得作为正式数据源宣传。

## 6. 研究产物

- [x] 每个实验产出 `run_meta.json`。
- [x] 每个实验产出 manifest。
- [x] 每个实验产出 perf/nav/funnel/reason codes。
- [x] artifact 路径相对化。
- [x] 产物 schema 有校验。

## 7. PAMS 外部化

- [x] `api.mobile` 不属于正式研究平台主路径。
- [x] `mobile_*` services 标记为 externalized_to_pams 或 deprecated。
- [x] `sim_account` 不作为账户真值。
- [x] `transaction_lifecycle_service` 不作为研究平台正式交易主表 owner。
- [x] 调仓包合同存在。
- [ ] PAMS app/web、通知、审批、交易生命周期和券商适配未在本仓库端到端验证。
- [ ] OpenSpec `split-quant-platform-and-pams-live-signal-contract` 的用户确认项仍未完成。

## 8. 前端

- [x] Research Workbench 只消费 API 和 artifact surface。
- [x] 前端不重算核心研究口径。
- [x] 移动端资产/审批页面不属于研究平台正式上线范围。
- [x] 图表数据来自平台 API，不直连供应商数据。
- [ ] `frontend/mobile.html` 和 mobile service worker 仍在仓库中，尚未迁移或删除。

## 9. 测试与审计

- [x] 边界测试覆盖 API route owner。
- [x] 边界测试覆盖 PAMS/mobile/sim_account 禁止主路径新增引用。
- [x] baseline regression check 可运行。
- [x] 数据合同测试可运行。
- [x] 研究报告和上线报告可生成。
- [ ] 当前工作区存在大量既有修改、删除和未跟踪研究草稿，尚未形成 clean worktree 与全量 CI 证据。
- [ ] `outputs/` 中仍存在历史 mobile/sim/account/研究产物，尚未完成上线裁剪确认。

## 10. 阻断项

存在以下任一项时，不得上线：

- 未解释的 baseline 行为变化
- 未解释的数据口径变化
- API route 双 owner
- PAMS 资产管理能力仍作为研究平台正式功能宣传
- 研究平台直接接券商执行
- `outputs/` 被源码依赖
- 研究-only 模块可直接进入 live strategy 发布
- iFinD、TradingView、IBKR 被宣传为已实现生产接入但缺少合同、测试和回退方案
- PAMS 跨仓库接收、展示、审批和交易生命周期未完成可复现 dry-run

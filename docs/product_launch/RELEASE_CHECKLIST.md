# 正式上线验收清单

## 1. 产品与文档

- [x] 根目录 `README.md` 使用正式产品名。
- [x] 所有核心文档使用“个人多资产趋势配置系统”作为正式定位。
- [x] 文档明确 PAMS 是独立资产管理系统。
- [x] 文档明确研究平台不直接接券商下单。
- [x] 文档明确 `outputs/` 不是源码主路径。

## 2. 命名治理

- [x] 新增正式命名清单。
- [x] 新增废弃命名清单。
- [x] `backtest_V2_standalone` 不再作为产品名。
- [x] `PAMS/pams_` 不再作为研究平台正式命名前缀。
- [x] `shadow` 和 `AB` 已映射到 `diagnostic_probe` 和 `controlled_experiment`。

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

- [ ] Tushare/iFinD 等供应商数据进入 raw vendor 层。
- [ ] 上层通过 canonical market data 访问。
- [x] 字段 source matrix 存在。
- [ ] 停牌、退市、缺口、合成补位有显式状态。
- [x] 数据 freshness 状态可查询。

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
- [x] PAMS 是正式通知、审批、执行状态 owner。

## 8. 前端

- [x] Research Workbench 只消费 API 和 artifact surface。
- [x] 前端不重算核心研究口径。
- [x] 移动端资产/审批页面不属于研究平台正式上线范围。
- [x] 图表数据来自平台 API，不直连供应商数据。

## 9. 测试与审计

- [x] 边界测试覆盖 API route owner。
- [x] 边界测试覆盖 PAMS/mobile/sim_account 禁止主路径新增引用。
- [x] baseline regression check 可运行。
- [x] 数据合同测试可运行。
- [x] 研究报告和上线报告可生成。

## 10. 阻断项

存在以下任一项时，不得上线：

- 未解释的 baseline 行为变化
- 未解释的数据口径变化
- API route 双 owner
- PAMS 资产管理能力仍作为研究平台正式功能宣传
- 研究平台直接接券商执行
- `outputs/` 被源码依赖
- 研究-only 模块可直接进入 live strategy 发布

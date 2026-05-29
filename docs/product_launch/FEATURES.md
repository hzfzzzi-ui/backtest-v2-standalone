# 功能特性与当前状态

本清单服务于“个人多资产趋势配置系统”的上线准备边界：系统提供配置研究、baseline 治理、实验审计和 live 调仓建议生成，不承接资产记账、审批或交易执行真值。

## 1. 当前已落地能力

### 1.1 Market Data Domain

当前能力：

- Tushare raw vendor 接入
- 原始数据落地和同步状态记录
- 交易日历、停复牌、复权、涨跌停、指数、ETF 和基础行情数据治理
- 字段来源矩阵和数据质量诊断
- canonical market data 访问合同

当前限制：

- iFinD 仅有 raw vendor 预留合同，未实现正式同步器。
- TradingView 不作为本仓库数据真值。
- IBKR 不作为本仓库行情或交易数据真值。
- `pams_ohlcv_daily_v2` 等历史表名仍处于兼容期，尚未完成 canonical market 命名迁移。

验收要求：

- 每个研究数据字段必须能追溯来源。
- 数据缺口、合成补位、停牌、退市尾部必须显式标记。
- 上层策略不得直接选择供应商表名。

### 1.2 Experiment Domain

当前能力：

- 实验配置编译
- 异步实验运行
- job 查询和取消
- 结果产物稳定化
- manifest、run_meta、rows、surface、perf、nav、funnel、reason codes 输出

验收要求：

- 所有实验必须有 `run_meta.json`。
- API 返回不得出现 NaN/Inf。
- 实验结果必须能通过 manifest 定位产物。
- 配置哈希、执行合同哈希、数据窗口必须进入审计信息。

### 1.3 Engine Domain

当前能力：

- 向量化回测引擎
- signal provider 合同
- stage pipeline
- execution assumptions
- risk/exit counters

验收要求：

- 信号时点和成交时点必须显式。
- baseline 主逻辑必须可回归。
- stage counters 必须能解释交易漏斗。

### 1.4 Portfolio Research Domain

当前能力：

- 候选计划
- 排序、选股、组合构建
- 订单规划研究
- 调仓建议生成
- 持仓感知 reconcile 派生分析

当前限制：

- portfolio research 只能生成研究结果或调仓建议。
- 账户真值和交易状态不得在本域内持有。
- `sim_account` 文件链路仅能作为兼容审计输入，不是正式账户系统。

### 1.5 Baseline Governance

当前能力：

- baseline 注册
- baseline index
- 回归检查
- 三窗口研究纪律
- 审计报告

验收要求：

- baseline 升级必须有证据链。
- baseline 回滚路径必须存在。
- diagnostic probe 和 controlled experiment 不得自动升级 baseline。

### 1.6 Research Study Domain

当前能力：

- study YAML
- study runner
- conclusion registry
- research journal
- markdown report
- controlled experiment 和 diagnostic probe 管理

当前限制：

- 仓库中仍有大量一次性研究草稿和未归档 OpenSpec 变更。
- 非 formal surface 不得进入 live 发布路径。
- 研究结论必须包含风险、失败模式和是否建议推进。

### 1.7 Result Workbench

当前能力：

- 实验列表
- 实验详情
- 结果对比
- artifact surface
- stage funnel 展示
- baseline 和研究结果查看

验收要求：

- 前端不得重算核心研究口径。
- 前端只能消费 API 和 manifest/surface 合同。
- 展示字段不得反向污染后端产物协议。

### 1.8 Live Package Publisher

当前能力：

- live strategy registry
- publish gate
- `daily_position_adjustment_package@1` 合同和校验
- no-op / blocked / invalid 显式状态
- 从研究侧生成调仓包的服务原型

当前限制：

- 跨 PAMS 的接收、幂等入库、app/web 展示、通知、审批和交易生命周期 dry-run 未在本仓库验证。
- 调仓包不是成交事实。
- 本仓库不得直接调用 IBKR、同花顺或其他券商接口执行下单。

## 2. 兼容遗留能力

以下能力仍存在于仓库中，短期可用于兼容或审计，但不得作为正式研究平台主路径继续扩展：

- `backend/api/mobile`
- `backend/api/transactions`
- `backend/core/services/mobile_*`
- `backend/core/services/sim_account_*`
- `backend/core/services/transaction_lifecycle_service.py`
- `frontend/mobile.html`
- `frontend/mobile-service-worker.js`
- 文件型 `approval_ticket`

## 3. 规划或外部系统能力

以下能力需要独立 plan/spec、测试和回退方案后才能进入正式范围：

- iFinD raw vendor 同步器
- TradingView 研究辅助输入或图表链接
- IBKR 账户/交易读取或下单适配
- PAMS app/web 通知、审批、交易生命周期和券商适配
- 美股 ETF、加密现货、防守层资产正式接入
- `backtest_V2_standalone` 仓库名迁移
- `pams_` 表名和模块命名迁移

## 4. 非目标能力

以下能力不得作为本平台正式上线主路径：

- 移动端审批
- app/web 资产管理
- 账户、现金、持仓真值
- broker adapter
- IBKR 下单
- 同花顺客户端自动下单
- Telegram 交易确认
- 文件型 approval ticket
- `sim_account` 作为正式账户系统
- PAMS 命名的研究平台正式接口

这些能力应迁移到 PAMS 或保持在明确兼容/审计边界内。

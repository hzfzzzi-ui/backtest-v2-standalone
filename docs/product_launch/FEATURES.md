# 正式功能特性清单

本清单服务于“个人多资产趋势配置系统”的正式上线边界：系统提供配置研究、baseline 治理、实验审计和 live 调仓建议生成，不承接资产记账、审批或交易执行真值。

## 1. 正式上线能力

### 1.1 Market Data Domain

正式能力：

- Tushare raw vendor 接入；iFinD 等新增供应商必须先落 raw vendor 合同，当前不作为已实现数据源宣传
- 原始数据落地和同步状态记录
- 交易日历、停复牌、复权、涨跌停、指数、ETF 和基础行情数据治理
- 字段来源矩阵和数据质量诊断
- canonical market data 访问合同

验收要求：

- 每个研究数据字段必须能追溯来源
- 数据缺口、合成补位、停牌、退市尾部必须显式标记
- 上层策略不得直接选择供应商表名

### 1.2 Experiment Domain

正式能力：

- 实验配置编译
- 异步实验运行
- job 查询和取消
- 结果产物稳定化
- manifest、run_meta、rows、surface、perf、nav、funnel、reason codes 输出

验收要求：

- 所有实验必须有 `run_meta.json`
- API 返回不得出现 NaN/Inf
- 实验结果必须能通过 manifest 定位产物
- 配置哈希、执行合同哈希、数据窗口必须进入审计信息

### 1.3 Engine Domain

正式能力：

- 向量化回测引擎
- signal provider 合同
- stage pipeline
- execution assumptions
- risk/exit counters

验收要求：

- 信号时点和成交时点必须显式
- baseline 主逻辑必须可回归
- stage counters 必须能解释交易漏斗

### 1.4 Portfolio Research Domain

正式能力：

- 候选计划
- 排序、选股、组合构建
- 订单规划研究
- 调仓建议生成
- 持仓感知 reconcile 派生分析

验收要求：

- portfolio research 只能生成研究结果或调仓建议
- 账户真值和交易状态不得在本域内持有
- 调仓建议必须能转为版本化调仓包

### 1.5 Baseline Governance

正式能力：

- baseline 注册
- baseline index
- 回归检查
- 三窗口研究纪律
- 审计报告

验收要求：

- baseline 升级必须有证据链
- baseline 回滚路径必须存在
- diagnostic probe 和 controlled experiment 不得自动升级 baseline

### 1.6 Research Study Domain

正式能力：

- study YAML
- study runner
- conclusion registry
- research journal
- markdown report
- controlled experiment 和 diagnostic probe 管理

验收要求：

- 每个 study 必须有状态：`formal_surface`、`controlled_experiment`、`diagnostic_probe`、`archived`
- 非 formal surface 不得进入 live 发布路径
- 研究结论必须包含风险、失败模式和是否建议推进

### 1.7 Result Workbench

正式能力：

- 实验列表
- 实验详情
- 结果对比
- artifact surface
- stage funnel 展示
- baseline 和研究结果查看

验收要求：

- 前端不得重算核心研究口径
- 前端只能消费 API 和 manifest/surface 合同
- 展示字段不得反向污染后端产物协议

### 1.8 Live Package Publisher

正式目标能力：

- live strategy registry
- publish gate
- daily live run
- `daily_position_adjustment_package@1`
- no-op / blocked / invalid 显式状态
- 对 PAMS 的调仓包发布

验收要求：

- 只有 `live_approved` 策略可发布
- 调仓包必须包含 `strategy_id`、`strategy_run_id`、`baseline_id`、`config_hash`、`execution_contract_hash`、`signal_date`、`execution_date`
- 调仓包不是成交事实

## 2. 非正式上线能力

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

这些能力应迁移到 PAMS 或删除。

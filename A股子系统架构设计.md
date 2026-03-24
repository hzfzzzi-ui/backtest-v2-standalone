# A股子系统架构设计

## 0. 文档状态

这份文档不再作为单一的 Phase 1 合同草案正文，而作为导读页和变更说明。

原草案已经拆分为两份文档：

- [A股子系统接口模块定义.md](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股子系统接口模块定义.md)
- [A股子系统系统架构思路.md](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股子系统系统架构思路.md)

拆分原因：

- 原草案同时承担“接口合同”和“系统思想”两类职责，受众混杂
- 原草案里有几处把未来目标能力写成了当前已存在模块，容易误导实现顺序
- 当前代码主干已经有部分能力雏形，但仍是分散实现，适合先拆出“面向架构师的接口定义”与“面向量化交易专家的系统思路”

## 1. 这次相对原草案的关键修正

### 1.1 `global_portfolio_governor`

原草案写法：

- 倾向把 `global_portfolio_governor` 写成当前已存在的独立模块

修改后写法：

- 改为“Phase 1 的正式目标能力 / 逻辑总控层”
- 明确当前实现仍分散在：
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/stage_pipeline/adapters/order_planning.py`
  - `backend/core/portfolio/portfolio_runtime.py`

修改原因：

- 当前代码里确实已有预算与状态控制雏形，但还不是单独服务或单独模块

### 1.2 `market_regime_engine`

原草案写法：

- 倾向把 `market_regime_engine` 写成当前已独立的公共上游服务
- 主状态直接写成 `RISK_ON / NEUTRAL / RISK_OFF / CRISIS`

修改后写法：

- 改为“逻辑上独立、实现上仍内嵌在现有 runtime/provider 链路中的状态解释层”
- Phase 1 保留当前技术五状态骨架，三状态只作为派生视图

修改原因：

- 当前正式链路里的 regime 主要依附于 `breakout_signal_provider` 和相关五状态引擎
- 下游行为已经依赖细粒度技术状态，不能在文档层直接假设已经换成全新主状态合同

### 1.3 `cn_etf_beta`

原草案写法：

- 容易读成 ETF beta 已正式接入统一多 sleeve 主线

修改后写法：

- 改为“Governor 约束下的 Phase 1 ETF beta sleeve 目标”
- 明确当前已存在的是：
  - `cn_etf` 数据链
  - `cn_etf` 资产范围
  - `cn_etf` research entry
- 不把它写成已经完成统一 Governor 接入的生产主线

修改原因：

- 当前 ETF 研究入口已通，但还处在 research entry 阶段
- 既有 smoke run 也说明它还不能被描述成成熟正式主线

### 1.4 `attribution_audit`

原草案写法：

- 只在各模块里散点要求审计字段，没有单独模块

修改后写法：

- 新增 `attribution_audit` 作为 Phase 1 正式模块

修改原因：

- 后续如果没有单独归因与审计层，将无法稳定回答：
  - 今天降仓是因为 regime
  - 还是因为 drawdown ladder
  - 还是因为 sleeve budget
  - 还是因为人工 override

### 1.5 预留位

原草案写法：

- `value_bluechip_satellite` 和 `insurance_overlay` 保留架构位置，但表达还不够硬

修改后写法：

- 明确写成“预留位，不进入当前 Phase 1 主开发与主验收”

修改原因：

- 当前代码和研究主线都还不具备把它们写成正式执行模块的条件

## 2. 建议阅读顺序

### 面向代码架构师

先读：

- [A股子系统接口模块定义.md](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股子系统接口模块定义.md)

重点关注：

- 模块边界
- 当前代码映射
- 输入输出合同
- Phase 1 非目标
- 迁移顺序

### 面向量化交易专家

先读：

- [A股子系统系统架构思路.md](C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股子系统系统架构思路.md)

重点关注：

- 个股 alpha / ETF beta / 预留防守与保险层的角色
- 市场状态判断的定位
- 仓位总控的定位
- Phase 1 与后续阶段边界

## 3. 当前收敛后的统一原则

- 信号可以分层，仓位不能分家
- A 股系统以后统一以 canonical 五状态作为唯一正式状态真相源
- 三状态只允许作为展示、粗粒度预算和外部解释的派生视图，不得反向成为上游真相
- 历史五状态和内部四状态只允许作为引擎内部过渡别名存在，不得继续外溢到正式 spec、正式产物、Governor 输入和前端正式语义
- 市场状态判断服务仓位切换，不以涨跌预测准确率为唯一目标
- `V10.1` 应被正式重定位为 `cn_stock_trend_alpha_core`
- `cn_etf_beta` 在 Phase 1 只承担低频、可解释的 beta sleeve 职责
- `value_bluechip_satellite` 与 `insurance_overlay` 继续保留为预留位
- `attribution_audit` 必须成为正式模块，而不是继续散在结果产物里

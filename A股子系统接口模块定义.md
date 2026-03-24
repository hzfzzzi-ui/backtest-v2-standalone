# A股子系统接口模块定义

## 0. 文档目的

本文档面向代码架构师。

目标是定义 A 股子系统在当前代码边界下的 Phase 1 正式模块、输入输出合同、合法调用链、当前代码映射关系、缺口与迁移顺序。

本文档**不**假设所有目标能力已经作为独立模块实现。凡是当前还处于分散实现或 research entry 的能力，都会明确标记。

## 1. Phase 1 正式模块

Phase 1 正式模块收敛为 5 个：

- `market_regime_engine`
- `global_portfolio_governor`
- `cn_stock_trend_alpha_core`
- `cn_etf_beta`
- `attribution_audit`

当前明确不进入 Phase 1 正式主交付的预留位：

- `value_bluechip_satellite`
- `insurance_overlay`

## 2. 顶层调用链

合法调用链：

```text
market_regime_engine
        ↓
global_portfolio_governor
        ↓
+--------------------------+-------------------+
| cn_stock_trend_alpha_core| cn_etf_beta       |
+--------------------------+-------------------+
        ↓
attribution_audit
        ↓
run_meta / audit / reports / snapshots
```

禁止调用链：

- `cn_stock_trend_alpha_core -> global total risk overwrite`
- `cn_etf_beta -> global total risk overwrite`
- `cn_stock_trend_alpha_core -> independent regime engine`
- `cn_etf_beta -> independent regime engine`
- `market_regime_engine -> direct trade execution`
- `sleeve -> bypass governor`
- `manual override -> overwrite base regime payload without audit trail`

## 3. 当前代码映射总览

### 3.1 `market_regime_engine`

当前状态：

- 逻辑已存在，但主要内嵌在 provider/runtime 链路中
- 当前最关键锚点在：
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/engine_vector/weekly_five_state_engine.py`
  - `backend/core/engine_vector/regime_engine_evaluator.py`
  - `backend/core/audit/regime_audit.py`

当前判断：

- 它不是独立服务
- 它更接近“当前已存在的技术状态引擎 + 未来要补的可归因状态装配层”

### 3.2 `global_portfolio_governor`

当前状态：

- 逻辑已分散存在，但未抽成独立模块
- 当前主要分散在：
  - `backend/core/stage_pipeline/adapters/order_planning.py`
  - `backend/core/portfolio/portfolio_runtime.py`
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/strategies/multi_alpha_strategy.py`

当前判断：

- 它是 Phase 1 的逻辑总控目标
- 不是当前已落地的单一服务或单文件模块

### 3.3 `cn_stock_trend_alpha_core`

当前状态：

- 这是当前正式主线 `V10.1` 最接近的一段
- 主要锚点在：
  - `backend/core/engine_vector/breakout_signal_provider.py`
  - `backend/core/engine_vector/breakout_provider_day_signals.py`
  - `backend/core/engine_vector/multi_alpha_signal_provider.py`

当前判断：

- 它已经是现有代码里最成熟的正式执行层
- 但必须从“整个系统”重定位为“股票 alpha sleeve”

### 3.4 `cn_etf_beta`

当前状态：

- `cn_etf` 已经具备独立 research entry 和独立日线真值表
- 主要锚点在：
  - `backend/cli/managed/refresh_cn_etf_catalog.py`
  - `backend/cli/managed/refresh_cn_etf_daily.py`
  - `backend/core/config/asset_profiles.py`
  - `backend/core/universe/universe_resolver.py`
  - `backend/core/tools/runtime_data_access.py`
  - `backend/core/tools/data_bundle_builder.py`
  - `research/studies/etf/*.study.yaml`

当前判断：

- 它可以作为 Phase 1 正式 sleeve 目标写入接口文档
- 但仍应被描述为“基于已有 ETF 研究入口的低频 beta sleeve”
- 不应写成已经成熟接入统一 Governor 的生产主线

### 3.5 `attribution_audit`

当前状态：

- 相关信息已存在，但分散
- 当前主要锚点在：
  - `backend/core/stage_pipeline/adapters/daily_accounting.py`
  - `backend/core/tools/experiment_runner.py`
  - `backend/core/audit/research_audit.py`
  - `backend/core/audit/regime_audit.py`
  - `backend/api/backtest_v2/artifacts_finalize.py`

当前判断：

- 需要在 Phase 1 被正式命名和合同化
- 不应继续只作为产物层零散字段存在

## 4. 模块合同

### 4.1 `market_regime_engine`

#### 4.1.1 模块定位

`market_regime_engine` 是 A 股子系统唯一合法的市场环境判断模块。

它的职责不是预测短期涨跌，而是：

- 识别风险环境变化
- 提高仓位切换正确性
- 为 Governor 提供统一环境输入
- 生成可归因的状态解释证据

#### 4.1.2 Phase 1 实现定位

Phase 1 中，它应被描述为：

- 逻辑上独立
- 实现上仍嵌在现有 runtime/provider 链路中的状态解释层

Phase 1 不应把它写成全新独立服务。

#### 4.1.3 Phase 1 主状态合同

Phase 1 保留当前技术五状态骨架作为主状态：

- `BULL`
- `TRANS_UP`
- `LIGHT`
- `TRANS_DOWN`
- `RISK_OFF`

派生视图允许输出三状态：

- `RISK_ON = BULL + TRANS_UP`
- `NEUTRAL = LIGHT`
- `RISK_OFF = TRANS_DOWN + RISK_OFF`

`CRISIS` 在 Phase 1 不作为主状态，应先作为 `stress_flag / crisis_overlay` 形式出现。

这里的硬约束是：

- 这五状态是 A 股系统唯一正式状态真相源
- 三状态只允许从五状态派生，不得反向成为 Governor、audit、前端或人工判断的上游真相
- 历史五状态命名和内部四状态命名只允许在 engine 内部过渡存在，不得继续出现在正式 contract、正式产物和正式 UI 语义中

#### 4.1.4 输入合同

输入分三类，优先级如下：

- `technical`
- `sentiment`
- `macro_global`

Phase 1 约束：

- `technical` 为主导
- `sentiment` 为解释增强和弱约束
- `macro_global` 为弱辅助或弱 veto，不得主导主状态切换

#### 4.1.5 输出合同

```json
{
  "base_state_5": "BULL|TRANS_UP|LIGHT|TRANS_DOWN|RISK_OFF",
  "coarse_state": "RISK_ON|NEUTRAL|RISK_OFF",
  "confidence": 0.0,
  "risk_budget_multiplier": 1.0,
  "defense_bias": 0.0,
  "reason_codes": [],
  "subscores": {
    "technical": {},
    "sentiment": {},
    "macro_global": {}
  },
  "state_stability_metrics": {},
  "manual_override": {
    "active": false
  },
  "effective_state_5": "BULL|TRANS_UP|LIGHT|TRANS_DOWN|RISK_OFF",
  "effective_coarse_state": "RISK_ON|NEUTRAL|RISK_OFF"
}
```

必须区分：

- `base_*`
- `effective_*`

禁止人工 override 直接覆盖原始模型输出而不留痕。

补充约束：

- `base_state_5` 是唯一正式状态真相源
- `effective_state_5` 是唯一正式生效状态真相源
- `coarse_state` 与 `effective_coarse_state` 仅是派生视图
- 任意下游模块不得只根据三状态重新反推或重建五状态

#### 4.1.6 权限边界

有权：

- 输出市场状态
- 输出预算乘数建议
- 输出防守偏置建议
- 输出解释字段

无权：

- 直接生成交易指令
- 直接改写总预算
- 直接决定具体证券

### 4.2 `global_portfolio_governor`

#### 4.2.1 模块定位

`global_portfolio_governor` 是 A 股子系统唯一合法的全组合总控层。

它负责：

- 总风险预算
- sleeve budget
- drawdown ladder
- 恢复与冷却
- defense floor
- 风险-off 执行约束

#### 4.2.2 Phase 1 实现定位

Phase 1 中，它应被描述为：

- 已有现实代码雏形
- 但仍分散在多个 adapter/provider/runtime 文件中的逻辑总控目标

不应把它写成已经抽象完成的独立服务。

#### 4.2.3 输入合同

```json
{
  "regime_output": {
    "base_state_5": "...",
    "effective_state_5": "...",
    "coarse_state": "...",
    "confidence": 0.0,
    "risk_budget_multiplier": 1.0,
    "defense_bias": 0.0,
    "reason_codes": []
  },
  "portfolio_state": {
    "nav": 0.0,
    "current_drawdown": 0.0,
    "sleeve_exposure": {},
    "cash_ratio": 0.0,
    "recent_turnover": 0.0,
    "recovery_state": "",
    "cooldown_state": ""
  },
  "config": {
    "base_portfolio_risk": 0.0,
    "drawdown_ladder": {},
    "sleeve_caps": {},
    "regime_budget_map": {},
    "recovery_rules": {},
    "cooldown_rules": {}
  }
}
```

#### 4.2.4 输出合同

```json
{
  "portfolio_budget": {
    "total_risk_budget": 0.0,
    "total_exposure_cap": 0.0
  },
  "sleeve_budgets": {
    "cn_stock_trend_alpha_core": {
      "enabled": true,
      "risk_budget": 0.0,
      "exposure_cap": 0.0
    },
    "cn_etf_beta": {
      "enabled": true,
      "risk_budget": 0.0,
      "exposure_cap": 0.0
    }
  },
  "governor_state": {
    "regime_state": "",
    "drawdown_state": "",
    "recovery_state": "",
    "cooldown_state": ""
  },
  "execution_flags": {
    "allow_new_risk": true,
    "force_deleveraging": false,
    "defense_floor_required": false
  },
  "reason_codes": []
}
```

#### 4.2.5 参数归属

必须上移到 Governor：

- `base_portfolio_risk`
- `dd_scale_10`
- `dd_scale_15`
- `dd_fixed_20`
- `dd_stop_pct`
- bull / light / trans_up / risk_off 类总预算倍率

必须保留在 sleeve：

- `max_positions`
- `single_stock_cap`
- `industry_cap`
- breakout / ranking / exits
- ETF 内部排序与趋势过滤

### 4.3 `cn_stock_trend_alpha_core`

#### 4.3.1 模块定位

`cn_stock_trend_alpha_core` 是 A 股子系统的股票 alpha 主引擎。

Phase 1 中，它以当前 `V10.1` 主干为基础，正式重定位为：

- 股票 alpha sleeve
- 不是整个系统
- 不再承担系统级总风控职责

#### 4.3.2 输入合同

输入必须包括：

- `governor_budget`
- `regime_context`
- `market_data`
- `alpha_features`

#### 4.3.3 输出合同

```json
{
  "stock_alpha_output": {
    "candidate_pool": [],
    "ranked_candidates": [],
    "approved_entries": [],
    "exit_actions": [],
    "target_positions": []
  },
  "sleeve_audit": {
    "blocked_by_regime": 0,
    "blocked_by_liquidity": 0,
    "blocked_by_crowding": 0,
    "blocked_by_gap": 0,
    "blocked_by_quality_veto": 0,
    "selected_count": 0,
    "avg_rank_score": 0.0,
    "reason_codes": []
  }
}
```

#### 4.3.4 权限边界

有权：

- 在预算内选股
- 在预算内排序
- 在预算内控制集中度
- 在预算内执行退出

无权：

- 改写 Governor 下达的总预算
- 私自扩大全组合总暴露
- 另起一套市场状态体系

### 4.4 `cn_etf_beta`

#### 4.4.1 模块定位

`cn_etf_beta` 是 Governor 约束下的 A 股 ETF beta sleeve。

Phase 1 正式定义：

- 低频
- 可解释
- 可审计
- 基于现有 `cn_etf` 数据链和 research entry
- 只表达 beta / limited defense candidate

#### 4.4.2 Phase 1 范围

Phase 1 核心 beta universe：

- `510300.SH`
- `510500.SH`
- `510050.SH`
- `512100.SH`

Phase 1 limited defense candidate：

- `512890.SH`

Phase 1 明确不并入 `cn_etf_beta` 核心的资产：

- `518880.SH`
- `511010.SH`
- `588000.SH`
- `159915.SZ`

#### 4.4.3 输入合同

```json
{
  "as_of_date": "YYYY-MM-DD",
  "asset_scope": "cn_etf",
  "universe_id": "cn_etf_first_wave_core",
  "execution_profile": "cn_etf_tplus1_next_open",
  "regime_state": "RISK_ON|NEUTRAL|RISK_OFF",
  "regime_confidence": 0.0,
  "sleeve_target_budget": 0.0,
  "defense_bias": 0.0,
  "max_positions": 3,
  "single_instrument_cap": 0.35,
  "turnover_cap": 0.20,
  "min_hold_days": 10
}
```

#### 4.4.4 输出合同

```json
{
  "module_id": "cn_etf_beta_v0_1",
  "as_of_date": "YYYY-MM-DD",
  "requested_budget": 0.0,
  "applied_budget": 0.0,
  "state": "RISK_ON|NEUTRAL|RISK_OFF",
  "targets": [],
  "cash_weight": 0.0,
  "defense_weight": 0.0,
  "reason_codes": []
}
```

#### 4.4.5 策略范式约束

Phase 1 仅允许：

- 绝对趋势过滤
- 相对强弱排序
- 周频或双周频正式调仓
- Governor 驱动的风险预算约束

Phase 1 禁止：

- 复用 `V10.1` 个股 breakout / 残差 / 资金流主逻辑
- 高频 ETF 轮动
- 复杂优化器
- 将 gold / bond 正式防守资产并入当前 ETF beta 核心

### 4.5 `attribution_audit`

#### 4.5.1 模块定位

`attribution_audit` 是 A 股子系统的横切归因与审计层。

它负责把以下几类信息统一成正式可追踪链路：

- regime 归因
- budget 归因
- sleeve 归因
- manual override 归因
- 运行结果产物归因

#### 4.5.2 为什么 Phase 1 必须正式纳入

没有它，后面无法稳定回答：

- 为什么今天总预算下降
- 为什么今天股票 sleeve 没上仓
- 为什么 ETF sleeve 只给到 limited exposure
- 是 regime、drawdown、cooldown、turnover cap 还是人工 override 在起作用

#### 4.5.3 输入合同

```json
{
  "regime_payload": {},
  "governor_payload": {},
  "stock_sleeve_payload": {},
  "etf_sleeve_payload": {},
  "runtime_events": {},
  "manual_override_events": {}
}
```

#### 4.5.4 输出合同

```json
{
  "state_logs": [],
  "budget_logs": [],
  "sleeve_logs": [],
  "reason_code_summary": {},
  "manual_override_log": [],
  "run_meta_patch": {},
  "audit_patch": {}
}
```

#### 4.5.5 当前代码映射方向

Phase 1 可以先从以下现有产物和链路汇聚：

- `daily_accounting`
- `experiment_runner`
- `research_audit`
- `regime_audit`
- `run_meta.json`
- `audit.json`

但正式合同上，应把它定义成独立模块，而不是继续只靠零散字段。

## 5. Phase 1 非目标

以下内容明确不属于当前主线交付：

- `value_bluechip_satellite` 正式接入
- `insurance_overlay` 正式接入
- ETF gold/bond/期权统一纳入 Governor 的生产执行
- 复杂多资产优化器
- 黑箱资产配置器
- 高频 ETF 切换
- 情绪/NLP 作为主状态裁判
- 宏观全球因子直接主导状态切换

## 6. 相对原草案的正式修改清单

### 6.1 原草案写法

- Phase 1 仅包含 4 个正式模块

修改后写法：

- Phase 1 正式模块改为 5 个，新增 `attribution_audit`

修改原因：

- 统一总控如果没有单独归因层，后续无法解释状态、预算和执行之间的因果链

### 6.2 原草案写法

- `global_portfolio_governor` 像是现成独立模块

修改后写法：

- 改为“Phase 1 逻辑总控目标，当前仍为分散实现”

修改原因：

- 当前代码还没有抽象成单独 Governor 服务

### 6.3 原草案写法

- `market_regime_engine` 像是已独立存在的公共上游服务

修改后写法：

- 改为“保留五状态骨架、内嵌于现有 runtime/provider 的可归因状态解释层”

修改原因：

- 当前正式实现并不是独立服务

### 6.4 原草案写法

- `cn_etf_beta` 容易读成已经接入正式统一主线

修改后写法：

- 改为“Phase 1 低频 ETF beta sleeve 目标，依托现有 research entry 和 ETF 数据链”

修改原因：

- 当前 ETF 路径已可研究，但尚不应被表述成成熟生产级 beta 主线

### 6.5 原草案写法

- `insurance_overlay` 与 `value_bluechip_satellite` 仍有被误读为近端交付的空间

修改后写法：

- 明确标注为预留位，不进入当前主开发与主验收

修改原因：

- 当前代码和研究主线都不支持把它们写成正式执行模块

## 7. 迁移顺序建议

建议严格按以下顺序推进：

1. 先把 `market_regime_engine` 合同化并补足可归因输出
2. 再把 `global_portfolio_governor` 从分散逻辑收敛成明确控制层
3. 再把 `V10.1` 正式重定位为 `cn_stock_trend_alpha_core`
4. 再把 `cn_etf_beta` 接进统一 Governor 预算
5. 同步建设 `attribution_audit`
6. 最后才推进 `value_bluechip_satellite` 与 `insurance_overlay`

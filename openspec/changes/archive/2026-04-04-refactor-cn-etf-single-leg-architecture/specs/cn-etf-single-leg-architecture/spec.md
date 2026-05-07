# cn-etf-single-leg-architecture Specification

## Purpose

约束 ETF 单腿在不扩展到 combo、前端和研究语义改造的前提下，完成可审计、可回退的分层重构，并保留稳定 facade 入口。

## ADDED Requirements

### Requirement: ETF 单腿必须通过稳定 facade 保留既有入口

系统 MUST 在第一轮重构中保留 ETF 单腿的既有公开入口，使外部调用点无需同轮修改 import。内部实现 MAY 迁移到新的 ETF 子模块，但旧入口文件 SHALL 退化为 facade 或 re-export。

#### Scenario: Contract 入口保持稳定

- **WHEN** 调用方继续从 `backend/core/config/etf_beta_contract.py` 导入 ETF contract 相关公开函数
- **THEN** 系统 MUST 继续提供这些公开符号
- **THEN** 旧文件 MUST 只承担 facade 或 re-export 责任，而不是继续承载全部实现

#### Scenario: Provider 入口保持稳定

- **WHEN** 调用方继续从 `backend/core/engine_vector/cn_etf_beta_signal_provider.py` 导入 `CNETFBetaSignalProvider`
- **THEN** 系统 MUST 继续提供相同类名与稳定运行入口
- **THEN** 外部 runtime 调用链 SHALL NOT 因内部子模块拆分而被迫同步迁移

### Requirement: ETF 合同实现必须拆分为默认值、归一化、暴露语义和 summary 边界

系统 MUST 将 ETF 单腿合同实现拆分为职责单一的子模块，至少覆盖默认值、归一化、暴露语义和 summary 四类边界。合同层 SHALL 保持“输入清洗”和“合同求解”分离，summary 逻辑 SHALL NOT 继续反向污染合同求解主路径。

#### Scenario: 默认值与归一化有独立 owner

- **WHEN** 系统需要构建 ETF 默认 contract 或清洗 governed `etf_beta` 配置
- **THEN** 默认值与归一化逻辑 MUST 分别由专属子模块负责
- **THEN** 暴露语义模块 SHALL 仅消费归一化后的输入，而不是重复兼容原始配置噪声

#### Scenario: 暴露语义与 summary 不再混在同一 owner

- **WHEN** 系统需要计算 `target_exposure`、`deployment_pace`、bucket target 或 phase1 summary
- **THEN** 暴露语义与 summary MUST 由不同子模块分别负责
- **THEN** `summary` 组装 SHALL NOT 继续在合同热点里直接混写执行语义

### Requirement: ETF provider 实现必须拆分为配置装配、选择、执行路径和诊断聚合

系统 MUST 将 ETF provider 的内部实现拆分为可独立维护的边界，至少包含配置装配、provider state owner、候选池/排序选择、执行路径和诊断聚合。provider facade SHALL 只保留稳定协议与调度职责。

#### Scenario: Provider state 与配置装配先于路径拆分

- **WHEN** 系统开始拆分 ETF provider
- **THEN** 系统 MUST 先建立集中化的 provider config 与 state owner
- **THEN** 后续选择、执行和诊断模块 MUST 通过该 owner 访问共享状态，而不是继续扩散新的隐式 `self` 字段

#### Scenario: 执行路径不再与诊断拼装混写

- **WHEN** 系统处理 monthly rebalance、`TRANS_UP` redeploy 或其他 ETF 执行路径
- **THEN** 执行路径模块 MUST 负责买卖决策与下单路径
- **THEN** 诊断模块 MUST 独立负责 reason code、execution path 标签和 gap 证据聚合

### Requirement: ETF actual exposure 与 formal-research view 必须通过专属 accounting 边界输出

系统 MUST 为 ETF 单腿建立专属 accounting 边界，统一输出 actual exposure、policy/timing/residual gap 和 formal/research view。通用 `daily_accounting.py` SHALL 仅保留编排职责，不得继续长期承载 ETF 领域解释真相。

#### Scenario: 通用 daily accounting 委托 ETF 专属 accounting

- **WHEN** stage pipeline 在 ETF 单腿运行中生成日级 accounting
- **THEN** `daily_accounting.py` MUST 将 ETF actual exposure 与 gap 解释委托给 ETF 专属 accounting 模块
- **THEN** 通用记账热点 SHALL NOT 继续直接拼装 ETF formal/research view 细节

#### Scenario: Gap 解释共享同一份 ETF accounting 真相

- **WHEN** research audit、formal audit 或 artifact 固化层消费 ETF 的 target/actual 差异解释
- **THEN** `pace_policy_gap`、`rebalance_timing_gap` 和 `execution_residual_gap` MUST 来自同一 ETF accounting 边界
- **THEN** 系统 SHALL NOT 在多个无关模块中各自重算并漂移这些字段

### Requirement: ETF summary 与 artifact 契约必须兼容且不得扩展范围

系统 MUST 在第一轮 ETF 单腿重构中保持当前 study 入口、semantic config 入口以及 ETF summary / artifact 字段兼容。该重构 SHALL NOT 借机扩展到 stock+ETF combo、前端工作台或新的研究语义。

#### Scenario: ETF summary 字段保持兼容

- **WHEN** `artifacts_finalize.py` 为 ETF 单腿运行写入 `run_meta`、`governed_snapshot` 或等价 summary 结构
- **THEN** ETF 相关字段名和顶层放置位置 MUST 保持与现有消费者兼容
- **THEN** API 层 MAY 改为消费新的 summary 模块，但 SHALL NOT 重新定义第二套 ETF summary 真相

#### Scenario: 本次重构不得扩大到 combo 或前端

- **WHEN** 本次 change 进入 apply 阶段
- **THEN** `cn_stock_etf_unified_runtime_service.py`、stock+ETF combo 语义和前端加载链路 MUST 保持不在本次实现范围内
- **THEN** 任何为兼容 import 而发生的改动 SHALL 仅限于 ETF 单腿主链的薄包装，不得演变为跨系统重构

### Requirement: ETF 单腿新边界必须保持单向依赖

系统 MUST 让 ETF 单腿的新模块遵守单向依赖方向：合同与配置层在上游，执行层在中游，accounting 与 artifact 消费层在下游。下游模块 SHALL NOT 反向成为合同或 provider 的依赖。

#### Scenario: Accounting 与 artifact 不得反向进入合同层

- **WHEN** 系统新增 ETF contract、provider、accounting 或 summary 子模块
- **THEN** `stage_pipeline/adapters` 与 `api/artifacts` 层 SHALL NOT 被 `config` 或 `engine_vector` 上游模块反向 import
- **THEN** ETF 合同和执行层 MUST 仅向下游暴露稳定数据结构，而不是依赖下游实现细节

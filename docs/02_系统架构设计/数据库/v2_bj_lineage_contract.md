# `BJ` Lineage Contract

## 1. 目的

这份合同约束 `V2` 在 `BJ pre-2021-11-15` 阶段的历史代码映射治理。

核心目标：
- 不再把当前 `920xxx.BJ` 代码机械回溯到成立前历史
- 必须通过显式 lineage 证据补源
- 诊断时允许启发式猜测，但正式 canonical build 不允许直接消费通用启发式映射

## 2. 适用范围

- `market_phase = bj_pre_20211115`
- 当前 symbol 为 `bj%`
- 需要为 `turnover_rate` 等低质量字段补源的场景

## 3. 正式表

表名：`public.pit_security_symbol_lineage`

字段：
- `current_symbol`
- `current_ts_code`
- `historical_symbol`
- `historical_ts_code`
- `phase_start`
- `phase_end`
- `phase_type`
- `mapping_source`
- `mapping_confidence`
- `is_active`
- `notes`
- `created_at`
- `updated_at`

## 4. 使用纪律

- `lineage` 仅用于 `BJ pre-2021-11-15` 的补源与审计辅助，不得把低可信映射伪装成高可信主源
- 显式 lineage 表映射优先级高于任何启发式规则
- 正式 build 默认只允许消费显式 lineage，不允许直接消费通用 `920xxx -> 430xxx` 启发式
- 正式映射必须显式标记：
  - `mapping_source = official_bse_code_mapping` 或等价人工核实名称
  - `mapping_confidence >= 2`
- 低可信启发式只能保留在诊断或一次性核查脚本中，不进入 canonical 主路径

## 5. 当前最小种子

第一批仅允许纳入已核实的新旧代码映射。

已核实样本示例：
- `bj920047 -> bj430047`
- `bj920090 -> bj430090`
- `bj920139 -> bj430139`
- `bj920023 -> bj832023`
- `bj920879 -> bj830879`
- `bj920152 -> bj831152`
- `bj920087 -> bj831087`
- `bj920974 -> bj830974`
- `bj920799 -> bj873799`
- `bj920961 -> bj873961`

扩展原则：
- 先补 audit 头部样本
- 每次扩展都必须有映射来源记录
- 每次扩展后必须重跑定向重建和定向审计

## 6. 验证标准

lineage 接入后至少验证：
- `bj_pre_20211115` 的 `low_turnover_rate_confidence` 是否下降
- `turnover_rate_source` 是否从 `imputed_zero` 转成显式 lineage 来源
- 若 lineage 源返回 `0` 且当日 `volume > 0`，不得直接升格为可用值

## 7. 风险

- 最大风险不是补不到，而是补错
- 所有 lineage 映射必须始终带：
  - `mapping_source`
  - `mapping_confidence`
- 如果补充后质量仍不足，下一步应继续查源或补官方映射，不得恢复通用启发式覆盖

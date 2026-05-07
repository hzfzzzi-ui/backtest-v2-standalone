## Context

当前基线 `A_STOCK_ETF_V1` 已登记 `execution_contract_ref`，但复跑时仍可能从 `baseline_config_snapshot.json` 重新编译 unified combo。重新编译会触发两个偏差：个股子腿通过 `runtime_config_json` 运行时丢失语义编译产生的 `execution_overrides`；ETF 子腿被 `_promote_etf_component_semantic_config_to_formal_v1` 无条件改写为 phase1 配置。

正式修复必须保持“执行真相只有 execution_contract”，不能把 `component_source_contract` 或 baseline snapshot 再提升成执行真相。

## Goals / Non-Goals

**Goals:**
- 让 unified combo 的子腿执行合同包含 `runtime_config` 与 `execution_overrides` 两类执行参数。
- 让 baseline 复跑优先解析 `execution_contract_ref` 指向的正式合同。
- 保留已声明的 ETF R1 研究口径，不在编译阶段隐式改写为 phase1。
- 用测试证明个股排名开关和 ETF source_entry_type 在复跑链路中不漂移。

**Non-Goals:**
- 不调整个股策略、ETF 策略、防守资产配置、信号/成交时点或市场数据源。
- 不清理历史产物，不改写已归档实验。
- 不把 provenance、study/baseline 引用重新放回 execution contract。

## Decisions

1. `execution_contract.components[*]` 增加 `execution_overrides`。
   - 原因：`runtime_config` 是配置树，`enable_multifactor_rank`、`mf_topk` 等实际进入执行壳的是 overrides；只保存 runtime config 不能完整复现执行行为。
   - 替代方案：把这些字段塞回 runtime config 顶层。拒绝，因为会混淆 runtime config 与执行壳覆盖参数，且无法表达所有已有 override。

2. unified combo 子腿请求仍可使用 `runtime_config_json`，但必须同步设置 body 级执行字段。
   - 原因：当前单腿服务在 `runtime_config_supplied` 时不会从语义配置派生 overrides；因此需要由组合执行合同显式提供并注入请求。
   - 替代方案：强制子腿走 `config_json` 语义路径。拒绝，因为这会重新引入 component_source_contract 作为执行来源，与唯一执行合同原则冲突。

3. baseline 复跑解析 `execution_contract_ref` 后再进入 unified combo。
   - 原因：baseline snapshot 是编辑/装配辅助，不是执行真相；复跑必须使用已登记合同 hash 对应的 artifact。
   - 替代方案：把 execution_contract 内联回 baseline_config_snapshot。拒绝，因为会破坏 baseline identity 与 snapshot 分离。

4. ETF phase1 提升改为条件化。
   - 原因：R1 standalone ETF 是已批准研究口径，不能被统一 combo 编译器无条件改写。
   - 替代方案：删除 phase1 提升。拒绝，因为缺省正式 phase1 anchor 仍需要保留现有规范化能力。

## Risks / Trade-offs

- [Risk] 老产物缺少 `execution_overrides`，复跑仍可能不完全等价。→ Mitigation: 对旧合同只做兼容读取；正式基线需在迁移/登记时写出完整新合同。
- [Risk] baseline 复跑入口较多，可能存在未覆盖脚本路径。→ Mitigation: 优先修 runtime service 主入口，并补 baseline 解析单元测试；后续脚本回归如发现遗漏再收敛。
- [Risk] ETF 条件化 phase1 可能让旧默认 unified template 保持旧 R1 口径。→ Mitigation: 仅当输入没有明确 ETF source 或明确 phase1 时才应用 phase1，已声明 source 的配置保持自身口径。

## Migration Plan

1. 扩展 execution contract 生成和读取，新增 `execution_overrides` 但兼容缺失字段。
2. 调整 baseline 复跑解析逻辑，读取 `baseline.json.execution_contract_ref.artifact` 指向的合同。
3. 调整 ETF phase1 提升条件，保留显式 R1 研究配置。
4. 运行单元测试和最小基线复跑；若结果仍不匹配，停止并继续定位，不登记新绩效。

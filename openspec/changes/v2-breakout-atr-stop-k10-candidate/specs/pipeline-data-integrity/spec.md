## ADDED Requirements

### Requirement: 候选运行时配置必须满足单路径漂移
候选运行时配置在编译完成后 SHALL 与锁定 baseline 进行结构化比较。除 `strategy.params.atr_stop_k` 外，系统不得引入其他参数漂移。

#### Scenario: 候选只修改 atr_stop_k
- **WHEN** 系统为 `v2-breakout-atr-stop-k10-candidate` 编译运行时配置
- **THEN** 编译后的配置与锁定 baseline 的差异 SHALL 仅包含 `strategy.params.atr_stop_k`
- **THEN** `strategy.params.atr_stop_k` SHALL 等于 `1.0`

#### Scenario: 非目标字段发生漂移
- **WHEN** 编译后的候选配置在 `costs`、`execution`、`universe`、`benchmark`、`benchmark_regime` 或其他非目标字段上与锁定 baseline 不一致
- **THEN** 系统 SHALL 将该次候选构建标记为失败
- **THEN** 审计结果 SHALL 明确指出发生漂移的字段路径

### Requirement: 候选编译不得覆盖 baseline 默认值
候选编译路径 SHALL 是显式分支。普通运行、baseline 回归或未声明候选的请求 MUST 保持原 baseline 参数，不得被候选逻辑静默覆盖。

#### Scenario: 普通运行不触发候选改写
- **WHEN** 系统处理普通 baseline 运行或未声明候选的单次运行请求
- **THEN** 编译后的运行时配置 SHALL 保持 baseline 的 `strategy.params.atr_stop_k=1.2`
- **THEN** 系统 SHALL 不得注入 candidate-only 参数覆盖

#### Scenario: 候选分支保留 provenance
- **WHEN** 系统处理显式声明的 `v2-breakout-atr-stop-k10-candidate`
- **THEN** 运行元信息 SHALL 记录候选名称、源 baseline `exp_id` 与唯一主改动路径
- **THEN** 该 provenance SHALL 可用于后续审计与回退

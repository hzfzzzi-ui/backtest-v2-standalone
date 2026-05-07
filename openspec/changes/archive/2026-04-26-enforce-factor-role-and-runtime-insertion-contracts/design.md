## Context

当前系统已经通过多轮研究确认：不少因子的问题不在研究面，而在 runtime 插入层。典型例子是 `monthly_divergence_rate` 被错误接成 candidate veto/tiebreak，以及 `pre_profit_failure_context_risk` 被错误接到 candidate buy layer。现在局部 hook 已经各自开始防错，但规则分散在 resolver 内部，semantic 编译与 runtime 请求构建阶段并没有统一合同，仍然允许非法接法穿透到实验层。

## Goals / Non-Goals

**Goals:**
- 建立统一的因子角色合同，覆盖当前已经存在的 research hook。
- 在 semantic 编译与 runtime 请求构建两条主入口上执行同一套合同校验。
- 保持 resolver 的局部无效状态返回，保证绕过主入口时仍然可审计。
- 在不改变 baseline 正常行为的前提下，阻止明显错误的接法进入实验。

**Non-Goals:**
- 不扩展到 ETF / defense。
- 不新增新的 research hook。
- 不改变合法接法下的排序、退出或交易行为。
- 不把 `asset_context` 从自由字典整体收紧成完整 schema。

## Decisions

### 决策 1：新增共享合同辅助模块，而不是继续在每个 resolver 里写分散规则
- 选择：新增共享 helper，集中维护角色、层级、动作的 canonical 合同。
- 原因：当前问题是系统级纪律缺失，不是单个 hook bug。共享合同可以被 semantic 编译、runtime 请求和 resolver 共用。
- 备选：继续在 `moneyflow_overlay.py` 与 `holding_exit_fragility.py` 内部分别加判断。
- 放弃原因：会继续产生规则漂移，无法保证未来新增 hook 复用同一套约束。

### 决策 2：semantic 编译与 runtime 请求构建双层拦截
- 选择：在 `validate_semantic_config_json` 与 `run_experiment_request_body` 两层都执行合同校验。
- 原因：前者覆盖 `config_json`，后者覆盖 `runtime_config_json` / `workbench_config`。两层都加才能堵住现有主入口。
- 备选：只在 resolver 中返回 invalid 状态。
- 放弃原因：会让非法接法进入实验入口，直到运行时才暴露，污染实验管理与审计链。

### 决策 3：保持非破坏性兼容，显式字段优先，缺省角色按现有动作推断
- 选择：允许 hook 配置新增 `factor_role`，但对历史配置在缺省时按现有动作推断默认角色。
- 原因：当前仓库已有大量 research-only 配置与测试，不应因为新增合同字段而整体失效。
- 备选：强制所有现有配置补齐 `factor_role`。
- 放弃原因：改动面过大，且不满足最小改动原则。

### 决策 4：resolver 仍保留本地 invalid 状态
- 选择：即使主入口会提前拒绝，resolver 仍保留 `invalid_*` 状态输出。
- 原因：直接单测 resolver、或未来有局部调用时，仍然需要稳定审计语义。
- 备选：只在主入口抛错，resolver 假定输入总合法。
- 放弃原因：会削弱模块自治和审计能力。

## Risks / Trade-offs

- [风险] 新合同默认角色推断与历史语义不一致 -> 缓解：仅对当前两个 hook 采用最小推断映射，并补充回归测试。
- [风险] semantic 与 runtime 双层校验产生重复逻辑 -> 缓解：两层只调用同一个共享 helper，不复制规则表。
- [风险] 未来其他 hook 仍未接入合同 -> 缓解：本次 change 先覆盖当前已存在且真实使用过的两个 hook，后续再扩展。
- [风险] runtime_config_json 的自由字典被收紧后影响旧实验脚本 -> 缓解：仅拦截明确非法的角色/层级/动作组合，不要求所有字段显式声明。

## Migration Plan

1. 新增共享合同 helper，并定义当前两个 hook 的允许角色/层级/动作映射。
2. 在 semantic 编译逻辑中对 `asset_context` 做统一校验。
3. 在 runtime 请求构建阶段对 merged `asset_context` 做统一校验。
4. 将 `moneyflow_overlay` 与 `holding_exit_fragility` resolver 改为复用共享合同。
5. 补单元测试覆盖 semantic、runtime、resolver 三层。
6. 若需要回退，只需移除共享 helper 接入并恢复两个 resolver 的本地逻辑。

## Open Questions

- 当前是否需要把 `trim_candidate` 也纳入持仓层正式可实验动作，还是继续只保留合同但不推进 A/B。
- 后续若新增第三类 hook，是否需要把合同上移到 `asset_context` 的专门 schema，而不是继续保持字典型字段。

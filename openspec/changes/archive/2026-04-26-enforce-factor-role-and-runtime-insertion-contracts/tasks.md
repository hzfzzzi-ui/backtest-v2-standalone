## 1. Artifacts 与合同定义

- [x] 1.1 完成 proposal/design/specs/tasks，并明确当前只覆盖 `moneyflow_overlay` 与 `holding_exit_fragility` 两条 hook。DoD：change 进入 apply-ready；验证：`openspec status --change enforce-factor-role-and-runtime-insertion-contracts --json`；风险：能力边界写得过大导致实现失焦。
- [x] 1.2 新增共享合同 helper，定义 canonical 角色、插入层、动作映射与稳定错误原因。DoD：共享 helper 可被 semantic/runtime/resolver 复用；验证：阅读 helper 导出的校验接口与常量；风险：默认角色推断与历史语义不一致。

## 2. 主入口校验接入

- [x] 2.1 在 `semantic_config_compiler` 的逻辑校验阶段接入 asset_context 合同校验。DoD：`config_json` 非法接法返回 400 且带路径；验证：新增 compiler 单测；风险：误伤合法历史配置。
- [x] 2.2 在 `experiment_runtime_service` 的 runtime 请求构建阶段接入同一套合同校验，覆盖 `runtime_config_json` 与 `workbench_config`。DoD：非法 runtime/workbench 配置在实验启动前被拒绝；验证：新增 runtime service 单测；风险：只校验部分入口导致绕过。

## 3. Hook 收敛与回归用例

- [x] 3.1 让 `moneyflow_overlay` 与 `holding_exit_fragility` resolver 复用共享合同，并保留局部 invalid 状态用于审计。DoD：resolver 继续返回稳定 invalid 原因；验证：新增/更新 overlay 与 fragility 单测；风险：局部状态语义变化破坏已有审计。
- [x] 3.2 更新测试覆盖 semantic、runtime、resolver 三层，并回填任务完成状态。DoD：测试文件覆盖非法角色、非法层级、非法动作与合法缺省推断；验证：静态检查测试断言是否完整；风险：只测单层导致合同漂移再次出现。

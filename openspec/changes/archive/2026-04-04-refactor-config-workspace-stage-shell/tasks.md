## 1. 正式阶段边界

- [x] 1.1 定义 `config_workspace` 的主阶段和高级阶段目录。（DoD: specs 固定阶段目录与职责；验证: `openspec validate refactor-config-workspace-stage-shell` 通过；风险: 阶段定义与现有高频工作流不符）
- [x] 1.2 固定抽屉标题、说明文案与阶段职责的正式边界。（DoD: spec 有明确阶段说明场景；验证: delta spec 完整；风险: 文案收口不足）

## 2. 模块收口

- [x] 2.1 将 `multi-alpha-workbench-ui` 收口到 `config_workspace` 正式模块语义。（DoD: 不再围绕旧壳定义配置区；验证: 场景覆盖主/高级入口；风险: 旧壳语义残留）
- [x] 2.2 在 `frontend-module-split` 中明确配置工作区的独立模块边界。（DoD: delta spec 明确模块归属；验证: OpenSpec validate 通过；风险: 模块边界与 desktop shell 冲突）

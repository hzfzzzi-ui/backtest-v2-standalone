## MODIFIED Requirements

### Requirement: `results-workbench` MUST 作为 `results_workspace` 子模块存在
系统 MUST 将 `results-workbench` 定义为 `results_workspace` 的子模块，而不是整个桌面端正式宿主。

#### Scenario: 结果区渲染实验结果
- **WHEN** 桌面端展示某次实验结果
- **THEN** `results-workbench` MUST 仅消费来自统一 app state 的结果数据
- **THEN** `results-workbench` SHALL NOT 继续持有整页宿主或跨区编排职责

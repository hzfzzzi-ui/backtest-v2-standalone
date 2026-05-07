## ADDED Requirements

### Requirement: 桌面端 MUST 提供单页 `desktop app` 作为正式宿主
系统 MUST 提供单页 `desktop app` 作为桌面端正式宿主。配置、运行、结果和状态中心 MUST 在同一宿主边界内组织；桌面端 SHALL NOT 再将静态旧壳和结果子应用拼接视为长期正式架构。

#### Scenario: 打开桌面端主入口
- **WHEN** 用户打开桌面端主入口
- **THEN** 系统 MUST 进入新的单页 `desktop app`
- **THEN** 顶部命令条、配置工作区、运行编排、结果区和状态中心 MUST 处于统一宿主边界内

### Requirement: 桌面端 MUST 采用单一顶层 app state
系统 MUST 采用单一顶层 app state，并按 `config_workspace`、`run_orchestration`、`results_workspace`、`status_center`、`desktop_shell` 切分领域状态。

#### Scenario: 运行完成后刷新结果工作区
- **WHEN** 一次运行结束并产出结果
- **THEN** `run_orchestration` MUST 将结果 hydrate 到统一 app state
- **THEN** `results_workspace` MUST 仅从统一状态读取结果，而不是自行直连 API

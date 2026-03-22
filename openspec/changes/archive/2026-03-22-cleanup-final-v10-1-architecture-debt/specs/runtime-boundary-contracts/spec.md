## MODIFIED Requirements

### Requirement: 桌面研究页必须以 experiment manifest 和 runtime snapshot 为真相
系统 MUST 让桌面研究页以 `experiment manifest`、`runtime snapshot` 与派生的 `ResultsWorkbenchSnapshot` 为唯一主真相。配置来源 metadata 仅可作为 provenance 辅助信息，页面状态 SHALL NOT 再以 `config_id` 或 `input_source_meta` 作为主运行语义。

#### Scenario: 桌面页加载历史实验
- **WHEN** 用户从历史列表载入某个实验
- **THEN** 页面状态 MUST 围绕该实验的 `manifest`、`surface` 和 `runtime snapshot` 更新
- **THEN** 页面 SHALL NOT 仅以 `config_id` 解释当前结果真相

#### Scenario: 页面草稿偏离已加载来源
- **WHEN** 用户在页面上修改配置并偏离已加载来源
- **THEN** 页面 MUST 将偏离状态表达为“当前 runtime 草稿与已加载来源不同”
- **THEN** 页面 SHALL NOT 将 `config_id` 视为唯一可运行真相

### Requirement: Config Draft 必须作为独立核心模块存在
系统 MUST 将“表单输入 -> config draft -> runtime request”的前端配置核心从旧控制器中抽离为独立模块。旧页面控制器 SHALL NOT 继续承担完整配置编译职责。

#### Scenario: 用户修改配置草稿
- **WHEN** 桌面页表单发生修改
- **THEN** 系统 MUST 由独立的 config draft core 更新运行草稿
- **THEN** 旧控制器文件 SHALL 仅负责控件联动和展示提示

#### Scenario: 新资产接入复用配置核心
- **WHEN** 系统接入新的资产类型或新的 runtime source
- **THEN** 配置核心 MUST 允许复用统一的 draft 和 request 编译流程
- **THEN** 旧控制器 SHALL NOT 再通过资产特化分支继续膨胀


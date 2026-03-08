## MODIFIED Requirements

### Requirement: 冻结脚本必须有明确治理信息
无法在本轮迁移的脚本 MUST 进入冻结清单，并记录原因、当前调用面、替代路径与退役触发条件。  
当且仅当冻结脚本满足零 live caller、存在替代路径且结果门禁继续通过时，系统 MAY 将其推进到真正 retirement。

#### Scenario: frozen script 进入 retirement wave
- **WHEN** 某个 frozen legacy script 已满足删除前置条件
- **THEN** 系统可以在后续 retirement wave 中删除该脚本，并同步更新 active spec、测试与运维文档

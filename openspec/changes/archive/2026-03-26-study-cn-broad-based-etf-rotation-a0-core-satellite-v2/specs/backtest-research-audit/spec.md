## ADDED Requirements

### Requirement: research audit 必须能解释 A0 V2 的槽位与替换模式
当实验属于 `broad_based_rotation_template_a0_core_satellite_v2` 时，`research_audit` MUST 能统一回答：
- 核心槽位选了谁
- 成长槽位选了谁
- 是否发生了 proxy 替换
- 哪个槽位因过滤、预算或部署门槛而空缺

#### Scenario: A0 V2 审计可回答组合构建来源
- **WHEN** 用户查看 A0 V2 研究实验的 `research_audit`
- **THEN** 审计结果 MUST 能明确区分核心宽基选择、成长卫星选择和替换模式

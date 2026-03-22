## ADDED Requirements

### Requirement: 默认测试集必须只依赖正式脚本面
系统 MUST 让默认 `pytest` 测试集只依赖正式脚本面：`backend/cli/main.py`、`backend/cli/managed/*`、`backend/scripts/generated/run_<study_id>.py` 和明确声明的薄 wrapper。默认测试 SHALL NOT 继续直接导入已退役或未声明为正式接口的顶层脚本实现。

#### Scenario: 测试覆盖脚本行为
- **WHEN** 单元测试或集成测试需要验证脚本行为
- **THEN** 测试 MUST 调用正式 CLI surface、managed module 或 generated thin script
- **THEN** 测试 SHALL NOT 直接依赖已退役的顶层脚本实现路径

#### Scenario: 顶层 wrapper 继续保留
- **WHEN** 顶层 `backend/scripts/*.py` 因兼容原因暂时保留
- **THEN** 该文件 MUST 只承担单向委托或参数透传职责
- **THEN** 默认测试 MAY 校验其委托关系
- **THEN** 默认测试 SHALL NOT 把该 wrapper 当作长期主实现宿主

### Requirement: 兼容脚本退场必须同步更新 inventory 与治理测试
系统 MUST 在每次脚本迁移、删除或降级为 wrapper 时同步更新 `backend/scripts/inventory.json` 与治理测试，保证脚本面现状可审计。

#### Scenario: 某个脚本从主实现降级为 wrapper
- **WHEN** 某个顶层脚本不再承载主实现而仅保留薄委托
- **THEN** inventory MUST 更新其分类和宿主路径
- **THEN** 治理测试 MUST 能识别该文件已不再是主实现

#### Scenario: 某个历史脚本被完全删除
- **WHEN** 某个退役脚本被移除
- **THEN** inventory 和治理测试 MUST 同步移除对其主实现身份的假设
- **THEN** 默认测试 collect SHALL NOT 因历史导入路径而失败

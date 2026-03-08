## ADDED Requirements

### Requirement: internal compatibility shim 必须显式收口
系统 MUST 为仍需兼容的内部工具提供显式 internal compatibility shim 边界。  
该边界 SHALL 只承载兼容职责，不得继续长出新的产品逻辑。

#### Scenario: 新增内部工具调用 shim
- **WHEN** 某个内部工具需要依赖 shim 能力
- **THEN** 系统 MUST 更新调用者矩阵与冻结文档，显式记录该调用者为何仍需 shim

#### Scenario: 尝试向 shim 添加产品功能
- **WHEN** 某项需求本质上属于公开产品表面或引擎主链逻辑
- **THEN** 系统 SHALL NOT 把它实现到 internal shim 中

### Requirement: 每个 shim 都必须声明退役门槛
每个 internal shim MUST 具备清晰的调用者列表、替代入口与退役前置条件。  
系统 SHALL NOT 保留“用途不明、调用者不明、无法退役”的 shim。

#### Scenario: shim 仍被保留
- **WHEN** 某个 shim 仍然存在于代码库中
- **THEN** 文档 MUST 标注该 shim 的 live callers、replacement surface 与删除门槛

#### Scenario: shim 进入删除候选
- **WHEN** 某个 shim 的 live callers 已全部迁移或冻结
- **THEN** 系统 MUST 将其列入第一批删除候选，并附上证据与回归门禁要求

### Requirement: 第一批删除候选必须证据驱动
第一批 legacy 删除候选 MUST 基于调用者矩阵、替代入口存在性与回归门禁结果共同确认。  
系统 SHALL NOT 仅凭“看起来没人用”就删除 legacy 模块。

#### Scenario: 提名某模块进入删除候选
- **WHEN** 某个 legacy 模块被列入删除候选
- **THEN** 候选记录 MUST 说明零 live caller 证据、替代入口以及需要通过的验证项

#### Scenario: 删除前回归验证
- **WHEN** 某批 legacy 模块准备实际删除
- **THEN** 系统 MUST 继续通过锁定基线 `exp_20260308_021045840_cde0` 的核心产物回归门禁

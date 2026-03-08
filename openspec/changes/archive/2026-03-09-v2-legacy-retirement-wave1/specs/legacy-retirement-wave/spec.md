## ADDED Requirements

### Requirement: legacy retirement 必须按证据波次执行
系统 SHALL 以 wave 的形式执行 legacy retirement。  
每个 wave MUST 明确删除对象、零 live caller 证据、替代入口与删除前置条件。  
系统 SHALL NOT 因“代码看起来没用”而直接删除 active 模块。

#### Scenario: wave1 删除冻结脚本
- **WHEN** `run_alpha_v1.py` 已被列为 frozen legacy script，且调用者矩阵显示无 active live caller
- **THEN** 系统 MAY 将其纳入 `legacy-retirement-wave1` 删除范围

#### Scenario: live shim 不得误入本 wave
- **WHEN** 某个 shim 仍被公开路由、internal helper 或研究脚本直接调用
- **THEN** 系统 SHALL 将其排除在当前 retirement wave 之外，并在文档中记录原因

### Requirement: retirement wave 必须继续通过结果门禁
每个 legacy retirement wave 在删除动作完成后 MUST 继续通过锁定基线回归门禁。  
如果核心产物与锁定基线不一致，系统 SHALL 判定该 wave 不可接受。

#### Scenario: delete wave 后复跑基线
- **WHEN** wave1 完成删除动作
- **THEN** 系统必须复跑 `exp_20260308_021045840_cde0` 的基线对比，且核心产物继续 `PASS`

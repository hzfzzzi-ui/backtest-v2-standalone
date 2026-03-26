## ADDED Requirements

### Requirement: ETF beta sleeve 必须支持宽基轮动模板 A 作为正式研究族
`cn-etf-beta-sleeve` MUST 支持“宽基轮动模板 A”作为正式研究族之一。该研究族 SHALL 被定义为 A 股 beta core 研究线，而不是行业轮动层、个股 alpha 替代物或正式防守层。

#### Scenario: 模板 A 按 beta core 角色运行
- **WHEN** 系统启用模板 A 研究
- **THEN** `cn_etf_beta` MUST 以 beta core sleeve 语义运行
- **THEN** 系统 SHALL NOT 把模板 A 静默解释为行业轮动或防守层策略

### Requirement: ETF beta sleeve 必须显式暴露宽基角色映射与代理资产
当 `cn_etf_beta` 运行模板 A 时，产物 MUST 显式暴露：

- 沪深300位
- 中证500位
- 中证1000位或其代理
- 红利位或其代理
- 成长位

若某个角色当前使用代理资产，系统 MUST 在产物中显式标记 `proxy=true` 或等价语义。

#### Scenario: 模板 A 产物暴露 role map
- **WHEN** 模板 A 完成一次实验
- **THEN** `run_meta` 或等价产物 MUST 暴露每个角色对应的 ETF
- **THEN** 若某个角色是代理资产，产物 MUST 能直接看出而不是靠用户猜测

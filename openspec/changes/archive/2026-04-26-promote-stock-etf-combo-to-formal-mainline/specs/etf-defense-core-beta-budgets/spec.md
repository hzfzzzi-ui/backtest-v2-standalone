## ADDED Requirements

### Requirement: weak-state defense and fallback MUST stay inside the formal ETF boundary
当 ETF 预算层进入 `TRANS_DOWN` 或 `RISK_OFF` 时，系统 MUST 只允许 formal defense 与 formal core beta 资产承担 weak-state defense / fallback 角色。research-only fallback 语义 SHALL NOT 进入正式主线合同。

#### Scenario: weak-state path uses only formal defense scope
- **WHEN** ETF 预算层运行于 `TRANS_DOWN` 或 `RISK_OFF`
- **THEN** 系统 MUST 只使用 formal defense 与 formal core beta 资产生成弱势目标
- **THEN** research-only fallback 资产 SHALL NOT 出现在 formal target truth 中

### Requirement: formal ETF budget outputs MUST separate formal truth from research diagnostics
系统 MUST 在 ETF budget explain / audit 中区分 formal truth 与 research diagnostics。formal output contract SHALL 只暴露 defense 与 core beta 的正式预算、目标与偏差。

#### Scenario: reading ETF weak-state explain under formal mainline
- **WHEN** 用户查看 formal mainline 下的 ETF weak-state explain 或 audit
- **THEN** 能看到 defense 与 core beta 的正式预算、目标与偏差
- **THEN** research-only fallback reason family SHALL NOT 作为 formal output truth 暴露

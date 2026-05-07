## Why

当前弱势环境里的很多问题不是目标结构错误，而是状态切换后旧仓没有先释放现金，导致防守承接和弱势累积在“几乎无自由现金”的情况下运行。需要把现金释放从 execution patch 上收为正式合同。

## What Changes

- 定义状态边缘的现金释放合同。
- 明确从 `BULL/LIGHT` 切到 `TRANS_DOWN/RISK_OFF` 时，哪些仓位可减、减多少、释放多少现金给防守层或累积层。
- 保持释放为“部分去风险”，不默认全清。

## Capabilities

### New Capabilities
- `state-edge-cash-release-contract`: 定义状态切换边缘的部分去风险和现金释放真相。

## Impact

- Affected code:
  - account allocator
  - state transition controls
  - inventory / cash management
- Affected artifacts:
  - `run_meta.json`
  - state-edge explain / reason codes
- Dependencies: 依赖账户预算层与状态机输出，不直接修改 stock alpha 和 regime。

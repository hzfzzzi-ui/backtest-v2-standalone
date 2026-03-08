## Why

`v2-script-migration-and-legacy-retirement-gate` 已经完成了脚本治理和 internal helper 收口，并给出第一批安全删除候选。  
当前证据充分、且不会误伤主链的退休对象只有一个：`backend/scripts/run_alpha_v1.py`。

如果继续把它停留在“冻结但仍存在”的状态，代码库里仍会保留一个已经退役但可见的旧入口，既增加维护心智成本，也会让 active spec 与真实代码状态继续漂移。

## What Changes

- 执行第一批 evidence-driven legacy retirement，只退役 `backend/scripts/run_alpha_v1.py`
- 同步收敛 active spec、测试与运维文档，明确这项能力已经退役，而不是仍由 frozen stub 承接
- 建立 wave1 的 retirement ledger，记录删除证据、替代路径与后续更大规模 retirement 的进入条件
- **BREAKING**：`python -m backend.scripts.run_alpha_v1` 不再存在；任何仍需要该历史流程的使用者必须改走新的公开 `config_json` 运行面，或单独创建新的研究脚本

## Capabilities

### New Capabilities
- `legacy-retirement-wave`: 约束实际删除动作必须以零 live caller 证据、替代入口和基线门禁通过为前提

### Modified Capabilities
- `alpha-experiment-runner`: 移除“系统 SHALL 提供 `run_alpha_v1.py`”这一 active capability
- `script-runner-governance`: frozen legacy script 在满足 gate 后可以进入真正 retirement，而不是无限期保留 stub

## Impact

- 直接影响：
  - `backend/scripts/run_alpha_v1.py`
  - `tests/unit/test_internal_script_helper.py`
  - `openspec/specs/alpha-experiment-runner/spec.md`
- 影响文档与删除证据：
  - `docs/ops/legacy_frozen_scripts_2026-03-08.md`
  - `docs/ops/legacy_delete_batch_candidates_2026-03-08.md`
  - 新增 wave1 retirement ledger
- 继续受 `exp_20260308_021045840_cde0` 基线门禁保护

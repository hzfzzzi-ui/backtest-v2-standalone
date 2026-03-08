## Context

当前 `backend/core/tools/internal_script_helper.py` 仅由脚本和测试使用，并非 engine/db/audit/runtime core 的一部分。

## Goals

- 让 `backend/core` 不再依赖 `backend.api.endpoints`
- 保持脚本 helper 行为不变
- 不改变基线回测结果

## Non-Goals

- 本 wave 不抽主 orchestrator
- 本 wave 不抽 artifact stabilizer
- 本 wave 不改脚本业务逻辑

## Decisions

### D1: 迁移 helper 而不是抽主 orchestrator

为了避免高风险的大提取，本 wave 只做 helper relocation：

- 新位置：`backend/scripts/_internal_helper.py`
- 旧位置删除
- 所有脚本和测试改为新 import

### D2: 以 `backend/core` 零 endpoint 反向依赖为完成标准

完成后 `Get-ChildItem backend/core -Recurse | Select-String 'backend.api.endpoints'` 必须为空。

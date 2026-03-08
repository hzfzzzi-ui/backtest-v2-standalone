## Why

`backend/core/tools/internal_script_helper.py` 现在只服务后端脚本与诊断工具，但它仍位于 `core/` 下，并反向依赖 API endpoint 模块。

这会让 `backend/core` 保持对 `backend.api.endpoints` 的最后两处反向依赖，阻碍“core 不依赖 API”的最终收敛。

## What Changes

- 将 `internal_script_helper.py` 从 `backend/core/tools` 迁到 `backend/scripts`
- 更新所有 scripts/tests import
- 删除旧的 core helper 文件
- 补 relocation ledger、回流测试与 baseline gate

## Capabilities

### New Capabilities
- `script-helper-boundary`: 脚本专用 helper 必须位于脚本/support 层，不得放在 core 中

### Modified Capabilities
- `internal-shim-boundary`: `backend/core` 不得再依赖 `backend.api.endpoints`

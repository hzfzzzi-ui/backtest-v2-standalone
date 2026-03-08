# Internal Script Helper Relocation (2026-03-08)

## 结论

脚本专用 helper 已从 `backend/core/tools/internal_script_helper.py` 迁移到 [`backend/scripts/_internal_helper.py`](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/_internal_helper.py)。

## 原因

- 它只服务 scripts/tests
- 它仍然需要调用 API orchestrator 与 artifact stabilizer
- 将其保留在 `backend/core` 会让 core 保留对 API endpoint 的反向依赖

## 删除后保护

- `backend/core` 中不得再保留该 helper
- scripts/tests 必须统一改到 `backend.scripts._internal_helper`
- `backend/core` 对 `backend.api.endpoints` 的 source-level 引用必须清零

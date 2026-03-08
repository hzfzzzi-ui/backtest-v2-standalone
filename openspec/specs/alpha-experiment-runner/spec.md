## Status

该 capability 已于 2026-03-08 在 `v2-legacy-retirement-wave1` 中退役。  
系统当前不再提供 `run_alpha_v1.py` 作为 active script。

## Replacement

- 面向产品或前端的运行：使用公开 `config_json -> experiment_id -> manifest/artifact` 表面
- 面向新的内部研究流程：基于当前公开契约或 `backend/core/tools/internal_script_helper.py` 重新编写研究脚本

## Historical Note

`run_alpha_v1.py` 的历史实现和最初需求保留在 archive change 中，不再作为当前 active requirement 生效。

# 后端重构基线门禁

## 目的

后端重构期间，`exp_20260308_021045840_cde0` 是锁定基线。  
凡是触及以下目录或文件的改动，都必须先执行统一基线比较命令，再决定是否继续推进：

- `backend/api/endpoints/`
- `backend/core/data/`
- `backend/core/tools/experiment_runner.py`
- `backend/core/portfolio/`
- `backend/core/engine_vector/`
- 结果协议相关测试与脚本

## 固定入口

- 基线 contract：`backend/scripts/ops/v2_backend_refactor_baseline_contract.json`
- 比较命令：`python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`

## 输出

命令会：

1. 使用锁定基线配置通过当前代码重新跑一遍回测。
2. 将新实验与 `exp_20260308_021045840_cde0` 比较。
3. 在新实验目录写出 `baseline_compare.json`。

## 结果解释

- `PASS`：保护产物无差异，可以继续下一阶段。
- `WARN`：只有诊断性差异，例如非阻塞诊断产物变化；需要在变更说明中注明。
- `FAIL`：核心结果、配置真相或关键语义漂移；必须先修复，不能继续删旧代码。

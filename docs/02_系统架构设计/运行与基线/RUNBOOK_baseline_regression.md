# RUNBOOK_baseline_regression

## 1. 目的

本 runbook 用于验证当前主线 baseline 与 unified combo 回放锚点在唯一 `execution_contract` 口径下是否保持一致。

当前正式锚点：
- baseline: `baseline_V10.1`
- replay anchor: `A_STOCK_ETF_V1`（`outputs/replay_anchors/`）

## 2. 执行顺序

### 2.1 最小正式回归

```powershell
powershell -ExecutionPolicy Bypass -File tests/run_minimal_formal_regression.ps1
```

期望：
- 单元与前端最小正式回归通过
- 不出现旧统一组合字段回流

### 2.2 生产同环境回放

```powershell
$py = @'
import json
import pathlib
from backend.core.tools.experiment_runtime_access import run_experiment_sync
cfg = json.loads(pathlib.Path('/app/outputs/replay_anchors/A_STOCK_ETF_V1/config.json').read_text(encoding='utf-8'))
res = run_experiment_sync({'config_json': cfg})
print(json.dumps(res, ensure_ascii=False))
'@
docker exec backtest-v2-standalone python -c $py
```

期望：
- `status = OK`
- 运行产物能定位唯一 `execution_contract`
- `input_config.json` 与 `run_meta.json` 不再把旧统一组合字段写成执行真相
- 核心指标保持当前验收结果
  - `cagr = 0.13307783712519594`
  - `total_return = 4.528748964658465`
  - `max_drawdown = -0.2751384763879182`
  - `sharpe = 0.46753113430222226`

## 3. 失败处理

- 如果最小正式回归失败，先看 `execution_contract` 是否缺失，或 provenance 字段是否重新越权成执行真相
- 如果生产同环境回放失败，先确认容器环境与外部数据服务是否可用
- 若只出现外部依赖断连，不应把问题归因到文档或主链收口

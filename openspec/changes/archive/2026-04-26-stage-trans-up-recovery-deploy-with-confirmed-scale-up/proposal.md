## Why

`TRANS_UP` 恢复态门控全局放开后，`2018-2026` 局部窗口改善明显，但 `2012-2017` 被明显打坏。当前问题已经定位为恢复态参与规模过大，而不是完全不该参与；因此需要把恢复态从“直接常态部署”收回到“先轻仓试错、确认后再恢复常态部署”的阶段化行为。

## What Changes

- 在股票 alpha sleeve 的 `TRANS_UP + benchmark_regime_off` 放行路径上新增恢复态轻仓部署缩放配置，不再默认按常态 `order_value_scale=1.0` 直接部署。
- 仅在恢复态放行当日对新买入信号注入 `order_value_scale` 缩放和诊断元数据，不改变 `BULL`、`TRANS_DOWN`、`RISK_OFF` 的既有语义。
- 增加最小 A/B，验证“轻仓恢复”能否减少 `2012-2017` 的恢复态损伤，同时尽量保留 `2018-2026` 的改善。

## Capabilities

### New Capabilities
- `trans-up-staged-recovery-deploy`: 定义 `TRANS_UP` 恢复态的先轻仓部署合同与诊断输出。

### Modified Capabilities
- `cn-stock-trend-alpha-core`: 股票 alpha sleeve 在 `TRANS_UP` 恢复态的入场部署语义从“全量放行”调整为“可配置轻仓放行”。

## Impact

- 影响模块：
  - `backend/core/config/models.py`
  - `backend/api/backtest_v2/semantic_config_schema.py`
  - `backend/api/backtest_v2/runner_config_risk_exit.py`
  - `backend/core/stage_pipeline/adapters/signal_postprocess.py`
  - `tests/unit/test_semantic_config_compiler.py`
  - `tests/unit/test_bridge_adapter_route_control.py`
- 影响研究：
  - 旧主线 carrier 的全样本和 `2018-2026` 组合 A/B
- 风险：
  - 若缩放过强，可能重新压死恢复态参与；若缩放过弱，则无法修复 `2012-2017` 的早进重仓问题。

## Why

当前 `AdaptiveRegimeStrategy` 将市况判断（regime detection）和信号生成（SMA/RSI）硬编码在一个类中，导致：
1. 趋势模式只能用 SMA，均值回归模式只能用 RSI，无法自由组合
2. 前端 UI 把 regime + trend + MR 参数混在一个面板里，用户无法直观理解"先判断市况 → 再选信号策略"的决策链路
3. 新增市况模式（如三元：牛/震荡/熊）或新信号策略（如 EMA、布林带）需要修改核心类

需要将 regime detection 拆分为独立层，信号策略变为可插拔子策略。

## What Changes

- **拆分后端架构**: `AdaptiveRegimeStrategy` 重构为 `RegimeRouter`（路由壳）+ `RegimeDetector`（市况判断）+ 两个可插拔子策略实例（趋势模式策略 + MR 模式策略）
- **前端 Signal Generation 面板重构**: 拆为三个子面板 — ① 市况判断、② 趋势模式信号、③ 震荡模式信号
- **API 编译路径更新**: `_experiment_runner_api.py` 的配置编译支持新的分层结构
- **策略注册更新**: `registry.py` 构造 `RegimeRouter` 时内部组装两个子策略
- **保持向后兼容**: 当 regime detection 关闭时，退化为纯 SMA/EMA 策略；原 `ADAPTIVE_REGIME` 策略名继续可用

## Capabilities

### New Capabilities
- `regime-router`: 市况路由器 — 根据 regime detection 结果将信号生成委托给不同子策略的路由壳架构
- `regime-signal-ui`: 前端分层信号面板 — 将 Signal Generation 拆分为市况判断 + 趋势信号 + 震荡信号三个独立可配置子面板

### Modified Capabilities
- `adaptive-regime-strategy`: REQ-1 双模式信号路由从硬编码 SMA+RSI 变为可插拔子策略；REQ-3 参数结构从扁平变为分层（regime / trend / mr 三组）

## Impact

- **后端**: `adaptive_regime.py` 重构为 `regime_router.py`；`registry.py` 修改构造逻辑；`_experiment_runner_api.py` 编译路径重写
- **前端**: `index.html` Signal Generation 面板 HTML 重构；`ui-controls.js` 配置序列化/反序列化重写；`backtest_v2.js` 面板切换逻辑更新
- **引擎路径**: 不变 — 仍走 `generic_signals` 路径
- **产物协议**: 不变 — Signal meta 字段保持兼容
- **已有实验**: 9 个保留的实验结果不受影响（配置中仍可识别旧参数格式）

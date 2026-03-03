## Why

SMA 路径有 8 级退出规则优先级链（RISK_OFF > ATR_STOP > FIXED_STOP > TREND_BREAK > TAKE_PROFIT > ATR_TRAIL > TIME > CROSS_DOWN），而 Generic 路径只实现了 4 级（ATR_STOP > FIXED_STOP > TAKE_PROFIT > ATR_TRAIL）。这意味着：

1. **Generic 路径缺失 RISK_OFF_EXIT**：大盘跌破均线时不会触发全员退出，用户在 Generic 策略上没有系统性风险保护
2. **Generic 路径缺失 TIME_EXIT**：`_max_hold_days2` 虽被读取但从未使用，max_hold_days 配置是死代码
3. **两路径退出逻辑重复**：~50 行核心退出判断代码 × 2 份，参数来源不统一（SMA 从 strategy 属性读，Generic 从 ExitConfig 读）
4. **Phase 4（信号提供者协议）的前置条件**：统一引擎循环需要退出规则是引擎层面的共享函数，而非分散在两路径中

## What Changes

提取两路径共有的引擎退出规则为共享函数 `_evaluate_engine_exits()`，补齐 Generic 路径缺失的 RISK_OFF_EXIT 和 TIME_EXIT，统一退出参数来源。

**策略层退出**（TREND_BREAK_EXIT、CROSS_DOWN 等）不在此次提取范围内，它们属于信号提供者的职责，将在 Phase 4 处理。

## Capabilities

### Modified Capabilities
- `engine-shared-primitives`: 新增 `_evaluate_engine_exits()` 函数规格

## Impact

- **代码消除**：~50 行重复退出判断逻辑合并为一份
- **Bug 修复**：Generic 路径获得 RISK_OFF_EXIT 和 TIME_EXIT 能力
- **回归风险**：SMA 路径数值必须与提取前完全一致；Generic 路径在未启用新退出规则时也必须一致

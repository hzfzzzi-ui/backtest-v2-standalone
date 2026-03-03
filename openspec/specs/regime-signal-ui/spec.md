# regime-signal-ui

前端分层信号面板 — 将 Signal Generation 拆分为市况判断 + 趋势信号 + 震荡信号三个独立可配置子面板。

## ADDED Requirements

### Requirement: 市况判断子面板

Signal Generation 区域 MUST 包含一个"市况判断"子面板（`<details>` 折叠块），包含：
- 启用开关（checkbox）— 关闭时退化为纯趋势策略
- benchmark 输入框（默认 000300.SH，与 universe benchmark 联动）
- regime_ma 输入框（默认 60）

#### Scenario: regime detection 启用
- **WHEN** 用户勾选市况判断启用开关
- **THEN** 显示趋势模式和震荡模式两个子面板，配置编译为 RegimeRouter 策略

#### Scenario: regime detection 关闭
- **WHEN** 用户取消市况判断启用开关
- **THEN** 隐藏震荡模式面板，仅显示趋势模式面板，配置编译为纯 SMA/EMA 策略

### Requirement: 趋势模式信号子面板

Signal Generation 区域 MUST 包含一个"趋势模式"子面板，包含：
- 策略选择器: SMA_CROSS / EMA_CROSS（复用现有 SMA/EMA 参数面板）
- 对应策略的参数（fast_ma, slow_ma, buffer 等）
- 入场趋势过滤选项（复用现有 wbEntryFilterBlock）

#### Scenario: 选择 SMA_CROSS 作为趋势策略
- **WHEN** 趋势模式策略选择器选择 SMA_CROSS
- **THEN** 显示 fast_ma, slow_ma, buffer 输入框

#### Scenario: 选择 EMA_CROSS 作为趋势策略
- **WHEN** 趋势模式策略选择器选择 EMA_CROSS
- **THEN** 显示 EMA 专属参数（fast_ma, slow_ma, ATR 止损等）

### Requirement: 震荡模式信号子面板

Signal Generation 区域 MUST 包含一个"震荡模式"子面板（仅当市况判断启用时显示），包含：
- 策略选择器: RSI_REVERSAL（初始版本仅此一项，后续可扩展）
- RSI 参数: rsi_period, rsi_buy_threshold, rsi_sell_threshold
- 退出参数: mr_max_hold_days, mr_stop_loss_pct

#### Scenario: 配置 RSI 震荡策略
- **WHEN** 震荡模式选择 RSI_REVERSAL
- **THEN** 显示 RSI 周期、买卖阈值、最大持仓天数、止损百分比输入框

### Requirement: 配置序列化

`buildConfigDraft()` MUST 将分层面板序列化为以下结构：

```json
{
  "signal_generation": {
    "regime_detection": {
      "enabled": true,
      "regime_ma": 60
    },
    "trend": {
      "strategy": "SMA_CROSS",
      "sma": { "fast_ma": 5, "slow_ma": 20 }
    },
    "mr": {
      "strategy": "RSI_REVERSAL",
      "rsi": {
        "rsi_period": 6,
        "rsi_buy_threshold": 20,
        "rsi_sell_threshold": 80,
        "mr_max_hold_days": 5,
        "mr_stop_loss_pct": 3
      }
    }
  }
}
```

当 regime_detection.enabled = false 时，mr 节点不序列化。

#### Scenario: regime 启用时序列化
- **WHEN** 市况判断启用，趋势策略=SMA，震荡策略=RSI
- **THEN** buildConfigDraft 输出包含 regime_detection + trend + mr 三个节点

#### Scenario: regime 关闭时序列化
- **WHEN** 市况判断关闭
- **THEN** buildConfigDraft 输出不含 regime_detection 和 mr 节点，仅含 trend 节点（退化为 strategy=SMA_CROSS）

### Requirement: 配置反序列化

`applyConfigToUI()` MUST 能从上述 JSON 结构恢复所有面板状态，包括：
- regime_detection 启用状态和 regime_ma
- 趋势模式策略类型和参数
- 震荡模式策略类型和参数

#### Scenario: 加载保存的 regime 配置
- **WHEN** 用户加载一个含 regime_detection 的配置
- **THEN** 市况判断面板启用，趋势/震荡面板参数正确回填

### Requirement: 摘要栏显示

`renderSummaryBar()` MUST 在摘要栏中显示当前信号策略配置：
- regime 启用时: "Regime(60) → TREND:SMA(5/20) + MR:RSI(6,20/80)"
- regime 关闭时: "SMA(5/20)" 或 "EMA(5/20)"

#### Scenario: regime 启用时摘要
- **WHEN** regime detection 启用
- **THEN** 摘要栏显示 "Regime(N) → TREND:策略(参数) + MR:策略(参数)" 格式

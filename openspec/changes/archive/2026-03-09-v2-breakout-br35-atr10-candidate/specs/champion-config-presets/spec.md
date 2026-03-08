# BR35 Builtin Load Config

## ADDED Requirements

### Requirement: 前端加载列表必须提供 BR35+ATR1.0+CSI800+10Y
系统 SHALL 在 builtin config store 中注册一个可加载的受控配置，名称为 `BR35+ATR1.0+CSI800+10Y`，供前端“加载”菜单直接调用。

#### Scenario: 列表接口返回 builtin config
- **WHEN** 前端请求 `GET /api/backtest_v2/configs`
- **THEN** 返回结果 SHALL 包含 `BR35+ATR1.0+CSI800+10Y`
- **THEN** 该配置 SHALL 标记为 `owner=builtin` 且 `locked=true`

#### Scenario: 前端加载配置
- **WHEN** 用户在前端选择 `BR35+ATR1.0+CSI800+10Y`
- **THEN** UI SHALL 正确回填 `HS300_ZZ500`、`2016-03-01~2026-03-01`、`breakout_window=35`
- **THEN** 该配置 SHALL 不改变默认草稿运行行为，除非用户显式加载并运行

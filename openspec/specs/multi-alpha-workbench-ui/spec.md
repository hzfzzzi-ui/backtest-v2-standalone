# multi-alpha-workbench-ui Specification

## Purpose

定义当前多 alpha / 多资产组合工作台在前端的正式 UI 合同，包括可运行控件、canonical 配置 round-trip、状态配置入口与运行前风险提示。

## Requirements

### Requirement: 工作台必须暴露当前可运行的组合控件

工作台 SHALL 为当前支持的组合策略提供可运行控件，并且只暴露运行时已支持的模块与选项。

#### Scenario: 用户启用组合配置

- **WHEN** 用户在工作台启用组合配置
- **THEN** 页面只显示当前主线支持的组合模块与组合模式

### Requirement: 工作台必须 round-trip canonical config_json

工作台 SHALL 直接生成并回填 canonical `config_json`。

#### Scenario: 运行前生成 canonical 配置

- **WHEN** 用户基于工作台草稿运行组合策略
- **THEN** 提交给后端主路径的 `config_json` 包含 canonical 组合配置

#### Scenario: 导入配置后回填

- **WHEN** 用户加载包含 canonical 组合配置的实验或基线
- **THEN** 工作台将这些配置无损回填到对应控件

### Requirement: 工作台必须暴露正式的市况判断配置入口

Signal Generation 区域 MUST 包含“市况判断”配置子面板，用于表达当前正式 regime / market-state 入口。

#### Scenario: 启用市况判断

- **WHEN** 用户启用市况判断
- **THEN** 工作台展示 benchmark、regime_ma 与对应的状态模式配置入口

#### Scenario: 关闭市况判断

- **WHEN** 用户关闭市况判断
- **THEN** 工作台退化为不依赖该入口的纯趋势配置

### Requirement: 工作台必须在运行前提示最小成交资金风险

Position & Risk 区域 SHALL 显示“买一手所需现金”估算，并在可能触发 `SKIP_LOT_TOO_SMALL` 时提供风险提示。

#### Scenario: 数据加载后显示提示

- **WHEN** universe 校验完成且价格数据可用
- **THEN** 工作台显示按当前股票池估算的最小一手资金需求

#### Scenario: 资金可能不足

- **WHEN** 估算的一手成本高于 `initial_capital / max_positions`
- **THEN** 工作台显示可能触发 `SKIP_LOT_TOO_SMALL` 的警告

### Requirement: 结果概览必须展示正式组合摘要

工作台 SHALL 在结果概览中展示组合类型、启用模块、组合模式与关键来源摘要。

#### Scenario: 加载组合实验结果

- **WHEN** 用户加载一条组合实验结果
- **THEN** 概览区直接显示正式组合摘要

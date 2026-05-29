# 上线准备文档包

本文档包定义 OpenClaw Personal Multi-Asset Trend Allocation System 的上线准备边界、当前功能状态、架构、模块归属、命名治理和验收差距。

当前状态：本仓库不是生产 READY 状态。文档包用于约束后续改造，区分“repo 内已验证”“兼容遗留”“规划/跨系统未验证”，不得作为正式上线完成声明。

## 文档索引

| 文档 | 用途 |
|---|---|
| `FEATURES.md` | 当前功能状态、非目标清单和规划能力 |
| `ARCHITECTURE.md` | 当前产品架构、兼容路径和目标调用关系 |
| `MODULE_OWNERSHIP.md` | 模块归属、保留、迁移、删除策略 |
| `NAMING_AND_DEPRECATION.md` | 正式命名、废弃命名、重命名计划 |
| `RELEASE_CHECKLIST.md` | 上线差距清单和阻断项 |

## 上线原则

正式版本必须体现个人多资产趋势配置系统的边界：

1. 本系统只管理配置研究真值，不管理资产真值。
2. 数据进入统一研究口径后才能被策略、实验和 baseline 使用。
3. 实验产物必须可复现、可审计、可回滚。
4. live 策略只能输出调仓包，不能直接驱动券商交易。
5. PAMS、移动审批、账户同步、交易生命周期不属于本平台正式主路径。
6. 开发阶段遗留命名和过渡链路必须进入明确的废弃或迁移清单。

## 当前事实边界

- 当前已正式接入资产范围：A 股。
- 当前可验证供应商路径：Tushare raw vendor 到 canonical market data。
- 当前未实现供应商生产路径：iFinD、TradingView、IBKR。
- 当前 PAMS 边界：本仓库有调仓包合同、校验和发布门禁原型；PAMS app/web、通知、审批、券商适配和成交回写不在本仓库内验证。
- 当前仓库状态：仍存在 `backtest_V2_standalone`、`pams_`、`mobile`、`sim_account` 等历史命名和兼容路径。

## 正式产品名称

产品中文名：个人多资产趋势配置系统

产品英文名：OpenClaw Personal Multi-Asset Trend Allocation System

推荐仓库名：`openclaw-personal-multi-asset-trend-allocation`

当前仓库名 `backtest_V2_standalone` 是历史名称，尚未完成仓库迁移，不得把“迁移完成”写入验收结论。

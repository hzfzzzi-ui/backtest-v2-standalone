# 产品正式上线文档包

本文档包定义 OpenClaw Personal Multi-Asset Trend Allocation System 的正式上线版本边界、功能特性、架构、模块归属、命名治理和验收标准。

## 文档索引

| 文档 | 用途 |
|---|---|
| `FEATURES.md` | 正式功能特性清单和非目标清单 |
| `ARCHITECTURE.md` | 正式产品架构和系统调用关系 |
| `MODULE_OWNERSHIP.md` | 模块归属、保留、迁移、删除策略 |
| `NAMING_AND_DEPRECATION.md` | 正式命名、废弃命名、重命名计划 |
| `RELEASE_CHECKLIST.md` | 上线验收清单和阻断项 |

## 上线原则

正式上线版本必须体现个人多资产趋势配置系统的边界：

1. 本系统只管理配置研究真值，不管理资产真值。
2. 数据进入统一研究口径后才能被策略、实验和 baseline 使用。
3. 实验产物必须可复现、可审计、可回滚。
4. live 策略只能输出调仓包，不能直接驱动券商交易。
5. PAMS、移动审批、账户同步、交易生命周期不属于本平台正式主路径。
6. 开发阶段遗留命名和过渡链路必须进入明确的废弃或迁移清单。

## 正式产品名称

产品中文名：个人多资产趋势配置系统

产品英文名：OpenClaw Personal Multi-Asset Trend Allocation System

推荐仓库名：`openclaw-personal-multi-asset-trend-allocation`

当前仓库名 `backtest_V2_standalone` 视为历史名称，不再作为正式产品名称使用。

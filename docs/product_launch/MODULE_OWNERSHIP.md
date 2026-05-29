# 模块归属与上线裁剪

模块归属以“个人多资产趋势配置系统”为正式定位：保留配置研究与调仓建议生成主线，资产管理、通知、审批和交易生命周期真值外部化到 PAMS。

## 1. 正式保留模块

| 模块 | 上线状态 | 说明 |
|---|---|---|
| `backend/api/backtest_v2/routes` | 保留但需更名规划 | 当前实验 API 表面 |
| `backend/core/data` | 保留 | 市场数据访问和 PG 映射 |
| `backend/core/engine_vector` | 保留 | 研究引擎核心 |
| `backend/core/stage_pipeline` | 保留 | stage 合同和 adapter |
| `backend/core/portfolio` | 保留 | portfolio research 和 candidate plan |
| `backend/core/config` | 保留 | 配置模型和编译 |
| `backend/core/audit` | 保留但需瘦身 | 研究审计 |
| `backend/core/report` | 保留 | 报告生成 |
| `backend/core/shared` | 保留 | 稳定工具层 |
| `backend/core/tools` | 保留但需分级 | runner、baseline、artifact 工具 |
| `backend/research` | 保留但必须分层 | study、formal surface、diagnostic probe |
| `frontend/app/results-workbench` | 保留 | 正式研究工作台 |
| `tests` | 保留 | 上线质量门禁 |
| `openspec` | 保留 | 规格驱动变更 |

## 2. 必须迁出或删除的模块

| 模块 | 上线状态 | 目标处理 |
|---|---|---|
| `backend/api/mobile` | 不进入正式上线主路径 | 迁移到 PAMS 或删除 |
| `backend/core/services/mobile_*` | 不进入正式上线主路径 | 迁移到 PAMS |
| `backend/core/services/sim_account_*` | 不作为账户真值 | 仅保留 reconcile 派生能力，账户域迁移 PAMS |
| `backend/core/services/transaction_lifecycle_service.py` | 不进入研究平台正式主路径 | 迁移到 PAMS |
| `outputs/mobile_ops/*` | 不作为正式接口 | 删除依赖，仅可短期审计留档 |
| 文件型 `approval_tickets` | 不进入正式上线主路径 | 由 PAMS transaction lifecycle 替代 |
| `frontend/mobile*` | 不进入研究平台正式主路径 | 由 PAMS app/web 替代 |

## 3. 必须冻结的开发期能力

| 能力 | 处理方式 |
|---|---|
| 一次性 shadow script | 转为 diagnostic probe 或 archive |
| AB 命名 study | 统一改称 controlled experiment |
| 非正式 `mobile` 半自动交易流 | 标记 deprecated |
| `sim_account` 文件真值 | 标记 deprecated |
| PAMS 命名的数据表作为研究平台正式对象 | 改为 canonical market 命名 |
| route 层和 impl 层重复 decorator | 必须消除 |

## 4. 正式模块状态枚举

上线前每个模块必须标记状态：

- `formal`
- `formal_candidate`
- `research_only`
- `diagnostic_probe`
- `deprecated`
- `externalized_to_pams`
- `archived`

## 5. 上线阻断项

以下任一项存在时，不得标记正式上线：

- API route 重复定义且无明确兼容说明
- 研究平台正式路径仍暴露移动审批主功能
- 研究平台正式路径仍持有交易生命周期真值
- PAMS 语义命名继续作为正式研究平台名称
- 一次性 study 没有状态标记
- 前端存在核心研究口径重算

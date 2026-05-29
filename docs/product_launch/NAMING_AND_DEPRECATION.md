# 正式命名与废弃计划

当前状态：本文档定义目标命名和废弃纪律，不表示仓库目录、包名、数据库表名已经完成迁移。`backtest_V2_standalone`、`backtest_v2`、`pams_ohlcv_daily_v2`、`pams_cn_etf_daily` 等仍存在于当前仓库，必须按兼容名称治理。

## 1. 命名原则

目标正式版本必须采用产品化命名：

- 名称表达业务职责，不表达历史实现方式
- 名称区分研究、资产、执行、展示
- 研究平台不得使用 PAMS 作为正式命名前缀
- 临时实验命名不得进入正式 API 和主路径
- `shadow`、`AB`、`mobile`、`sim_account` 等开发期术语必须有正式替代或废弃状态

## 2. 产品命名

| 类型 | 当前名称 | 正式名称 | 处理 |
|---|---|---|---|
| 产品 | `backtest_V2_standalone` | OpenClaw Personal Multi-Asset Trend Allocation System | 文档口径已废弃，仓库目录尚未迁移 |
| 仓库建议名 | `backtest_V2_standalone` | `openclaw-personal-multi-asset-trend-allocation` | 后续单独迁移，当前未完成 |
| 中文定位 | 旧量化研究平台口径 | 个人多资产趋势配置系统 | 立即更新文档口径 |
| API 产品名 | `backtest_v2` | Research Experiment API | 兼容期保留路径，文档改名 |

## 3. 模块重命名计划

| 当前名称 | 正式目标名称 | 处理级别 |
|---|---|---|
| `backend/api/backtest_v2` | `backend/api/research_experiments` | L3，需兼容 facade |
| `/api/backtest_v2/*` | `/api/research/experiments/*` | L3，先新增新路径，再废弃旧路径 |
| `data_impl.py` | `experiment_data_service.py` 或拆入 core service | L2 |
| `runner_impl.py` | `experiment_run_service.py` | L2 |
| `history_impl.py` | `experiment_history_service.py` | L2 |
| `mobile` | `pams_app` 或 PAMS 内正式模块 | 外部迁移 |
| `mobile_ops` | PAMS `order_intent` / `notification` / `approval` | 外部迁移 |
| `sim_account` | PAMS `account_state`; 研究平台 `reconcile_input` | 外部迁移和局部重命名 |
| `approval_ticket` | PAMS `order_intent` | 外部迁移 |
| `transaction_lifecycle` | PAMS `transaction_lifecycle` | 外部迁移 |
| `shadow` | `diagnostic_probe` | L2 文档和 registry 先行 |
| `AB` | `controlled_experiment` | L2 文档和 registry 先行 |
| `pams_ohlcv_daily_v2` | `canonical_market_ohlcv_daily` | L3 数据合同迁移 |
| `pams_cn_etf_daily` | `canonical_market_cn_etf_daily` | L3 数据合同迁移 |

## 4. 术语规范

| 正式术语 | 含义 |
|---|---|
| `formal_surface` | 正式研究面，可作为产品研究能力 |
| `controlled_experiment` | 有明确对照组的研究实验 |
| `diagnostic_probe` | 诊断型研究，不改变 baseline |
| `baseline` | 已注册、可回归、可审计、可回滚的正式基线 |
| `live_strategy` | 通过人工批准并绑定 baseline/config/execution contract 的发布策略 |
| `position_adjustment_package` | 研究平台输出给 PAMS 的调仓建议合同 |
| `canonical_market` | 研究平台统一市场数据口径 |
| `artifact` | 运行产物，不是源码，也不是长期业务真值 |

## 5. 废弃策略

废弃分三步：

1. 文档标记 deprecated，并建立替代名称。
2. 增加静态边界测试，禁止新增引用。
3. 删除旧路径或仅保留兼容 facade。

兼容 facade 必须满足：

- 不包含业务逻辑
- 只转发到正式 owner
- 有删除日期或删除条件
- 有测试覆盖

## 6. 禁止进入正式上线的命名

以下命名不得出现在新的正式 API、正式文档标题或主路径模块名中：

- `standalone`
- `backtest_V2` 作为产品名称
- `pams_` 作为研究平台正式对象前缀
- `mobile_ops`
- `approval_ticket`
- `sim_account` 作为账户真值
- `shadow` 作为正式研究能力名称
- `AB` 作为正式能力名称
- `legacy` 作为长期运行路径名称

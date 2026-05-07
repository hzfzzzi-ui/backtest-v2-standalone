# Qlib 可借鉴清单

更新时间：2026-05-02

## 结论

`microsoft/qlib` 值得作为外部设计参考，但不建议作为当前系统的运行依赖直接引入。

本项目的正式定位是“个人多资产趋势配置系统”，当前优先级是可信、可审计、稳健、可解释、可复现、可回滚。Qlib 的定位更接近“AI/ML 量化研究平台”，覆盖数据、模型训练、回测、组合、执行、在线服务和强化学习。两者目标不同，因此只能借鉴局部设计，不应替换当前主线。

## 外部事实

- 仓库：<https://github.com/microsoft/qlib>
- 包名：`pyqlib`
- 许可证：MIT
- 主要语言：Python
- PyPI 当前版本：`0.9.7`
- Python 要求：`>=3.8`
- 官方 README 描述其覆盖完整 ML pipeline：data processing、model training、back-testing，并覆盖 alpha seeking、risk modeling、portfolio optimization、order execution。
- 官方 README 同时提示：官方数据集暂时不可用，Yahoo Finance 数据可能不完美，建议用户准备自己的高质量数据。

## 借鉴原则

1. 不把 Qlib 引入生产依赖。
2. 不把 Qlib 示例收益作为本项目收益锚点。
3. 不把 Qlib 数据源作为正式 A 股或 ETF 数据真相。
4. 不绕过本项目三窗口纪律。
5. 不改变当前 baseline、信号时点、成交时点、股票池、ETF 池、组合构建逻辑。
6. 所有借鉴必须先转成本项目本地 spec，再最小实现、测试、回归、可回滚。

## 可借鉴项

| 编号 | Qlib 设计 | 对本项目价值 | 建议借鉴方式 | 风险 |
| --- | --- | --- | --- | --- |
| Q1 | 表达式化特征系统，例如 `Ref($close, -2)`、`Mean($close, 20)` | 统一特征定义，减少散落脚本口径 | 设计本项目自己的安全特征表达式子集，只编译到本地 PIT 数据访问层 | `Ref` 正负方向容易引入未来函数，必须显式审计 |
| Q2 | `DataHandler / Dataset` 分层 | 区分 raw、infer、learn 数据视图 | 借鉴为本项目 `DataBundle` / runtime data view 的契约文档 | 不能把 learn 标签处理混入推理或实盘路径 |
| Q3 | Processor fit 窗口纪律 | 强化训练窗口与测试窗口隔离 | 增加本项目 processor / factor 标准：任何 fit 参数必须有 `fit_start`、`fit_end` | 若默认全样本 fit，会造成数据泄露 |
| Q4 | YAML workflow / `qrun` | 实验配置可声明、可复现 | 借鉴到 study spec：model/data/backtest/record 分段声明 | YAML 容易一次隐藏多个核心改动，必须受 change level 管控 |
| Q5 | Recorder / artifact template | 产物结构标准化 | 借鉴 artifact manifest、record template 的概念，继续用本项目 `outputs/experiments` 体系 | 不应引入 MLflow 作为当前必要依赖 |
| Q6 | Strategy / Executor / Exchange / Order 分层 | 可对照本项目 stage pipeline 边界 | 做一份本项目 `stage_pipeline` 与 Qlib execution 抽象对照表 | Qlib 默认执行口径不等于本项目正式口径 |
| Q7 | `TopkDropoutStrategy` | 可作为横向基准思想：固定持仓数 + 替换率 | 仅用于研究对照，不作为主策略迁移 | 示例常配 `deal_price: close`，不符合本项目默认审计偏好 |
| Q8 | 模型 zoo 与 Alpha158/Alpha360 | 提供 ML alpha sandbox 参考 | 未来可在隔离研究区做 benchmark adapter | 当前阶段不应转向黑箱 ML alpha |
| Q9 | Online rolling / model serving | 对未来滚动实验管理有参考 | 仅在 P2/P3 后作为“模型版本滚动”设计参考 | 会显著扩大系统复杂度 |
| Q10 | 数据 offline / online mode | 对未来多客户端共享数据服务有参考 | 当前只记录思路，不落地 | 当前个人系统不需要引入数据服务复杂度 |

## 不建议借鉴项

- 不直接使用 Qlib 官方或社区打包数据作为正式数据源。
- 不直接采用 Qlib 示例里的收益、IC、回撤作为本项目能力证明。
- 不直接引入 `pyqlib` 到当前 backend runtime。
- 不直接复制 `Alpha158 / Alpha360` 作为正式特征集。
- 不直接采用 `TopkDropoutStrategy` 替换当前趋势配置主线。
- 不引入 RD-Agent 自动挖因子进入主路径。
- 不用 MLflow 替换当前 artifact / baseline ledger 体系。

## 与当前系统的映射

| 当前系统 | Qlib 对照 | 结论 |
| --- | --- | --- |
| `backend/core/data`、Postgres PIT 数据 | `qlib.data` provider / expression engine | 可借鉴表达式层，不迁移数据底座 |
| `backend/core/stage_pipeline` | `strategy / executor / exchange` | 可做边界对照，不替换执行链 |
| `research` study runner | `qrun` workflow | 可借鉴配置分段与 record 模板 |
| `outputs/experiments` | Qlib recorder artifacts | 可借鉴产物模板，不引入 MLflow |
| baseline regression | Qlib benchmark result | 不可替代，本项目仍以本地 baseline contract 为准 |
| 个人账户闭环 | Qlib portfolio/order execution | 只能参考抽象，不能直接承担账户状态真相 |

## 建议推进顺序

1. P0：不引入 Qlib，仅保留本清单。
2. P1：设计本项目“安全特征表达式子集”spec，重点解决时点方向、窗口、PIT 依赖、禁止未来引用。
3. P1：做 `stage_pipeline` 与 Qlib `Strategy / Executor / Exchange / Order` 边界对照，只输出文档，不改逻辑。
4. P2：抽象 artifact record template，统一实验产物结构和审计字段。
5. P3：在隔离 sandbox 中运行 Qlib LightGBM / Alpha158 作为外部 benchmark，不进入正式 baseline。

## 采用任何 Qlib 思路前的硬门槛

- 必须先出 spec。
- 必须明确 change level。
- 必须说明是否影响信号时点、成交时点、数据窗口、股票池或组合构建。
- 必须通过三窗口验证。
- 必须通过 baseline regression。
- 必须提供回退路径。
- 若涉及特征表达式，必须有未来函数单测。
- 若涉及执行抽象，必须有成交价格、涨跌停、停牌、交易单位、费用口径测试。

## 当前判断

短期最值得借鉴的是 Q1、Q2、Q3、Q5、Q6。

最不建议当前推进的是 Q8、Q9、Q10，因为它们会把系统重心从“个人多资产趋势配置系统”推向“通用 ML 量化平台”，与当前阶段核心任务冲突。

## 深入分析

- Q1/Q2/Q3/Q5/Q6 的深入拆解见：`docs/04_重构思路/qlib_Q1_Q2_Q3_Q5_Q6_深入分析.md`

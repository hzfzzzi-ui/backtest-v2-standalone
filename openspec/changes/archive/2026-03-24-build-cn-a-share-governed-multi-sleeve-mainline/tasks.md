## 1. 入口合同与配置语义收敛

- [x] 1.1 梳理并固化 `baseline_V10.1 -> cn_stock_trend_alpha_core` 的运行时命名与产物命名映射。DoD：运行配置、run_meta 与研究入口不再把 `V10.1` 当成整个 A 股系统。验证：定向运行 1 个 `baseline_V10.1` smoke，检查 `run_meta.json`。风险：历史实验名与新语义混淆。
- [x] 1.2 为 A 股 governed 主线补最小配置 contract，定义 Governor、regime、stock sleeve、ETF sleeve 的统一配置入口。DoD：配置编译链存在单一真相来源。验证：配置编译单测。风险：旧配置兼容。

## 2. Market Regime Engine 合同化

- [x] 2.1 统一 regime 输出为 `base_state_5 / effective_state_5 / coarse_state / effective_coarse_state / confidence / reason_codes`。DoD：现有 regime 产物可稳定输出上述字段。验证：regime 相关单测与 smoke 产物。风险：现有五状态实现字段漂移。
- [x] 2.2 为 regime 增加 `subscores.technical / sentiment / macro_global` 和 `manual_override` 占位输出。DoD：即使 Phase 1 只由技术主导，产物也能输出结构化解释层。验证：run_meta 或 audit 引用检查。风险：解释字段先占位导致误解。
- [x] 2.3 补 regime 切换与 override 的最小 reason code/transition 审计。DoD：可回答“今天为什么是这个状态”。验证：`audit.json` 或等价 debug 产物断言。风险：reason code 粒度过粗。

## 3. Governor 预算总控合同化

- [x] 3.1 在现有预算链路上整理 `total_risk_budget / total_exposure_cap / sleeve_budgets` 输出。DoD：Governor 预算字段可以被统一消费。验证：预算相关单测与 `portfolio_daily.csv`/debug 输出。风险：旧预算逻辑被无意改变。
- [x] 3.2 把 drawdown ladder、recovery、cooldown、defense floor 统一进 Governor 产物语义。DoD：这些状态能在同一预算摘要中出现。验证：模拟不同回撤状态的单测。风险：现有回撤参数语义冲突。
- [x] 3.3 增加 Governor 的 budget reason codes 与拒单/压缩解释字段。DoD：可回答“为什么今天这个 sleeve 没吃满预算”。验证：audit/debug 产物断言。风险：理由归因不稳定。

## 4. 股票 alpha sleeve 重定位

- [x] 4.1 将股票主线显式接入 Governor budget，而不是继续默认拥有全组合预算语义。DoD：股票 sleeve 只消费分配给自己的预算。验证：局部回归与预算字段检查。风险：行为与历史基线出现未解释漂移。
- [x] 4.2 保持股票 alpha 主干边界，禁止 Phase 1 混入左侧蓝筹、ETF beta 或保险逻辑。DoD：代码路径和产物文义都能反映边界。验证：研究入口和 run_meta 检查。风险：旧配置误混模块。

## 5. ETF beta sleeve 接入

- [x] 5.1 基于现有 `cn_etf` data/research entry 构建 `cn_etf_beta` Phase 1 候选池与 core beta 摘要。DoD：正式范围仅限 `510300/510500/510050/512100`，`512890` 作为 limited defense candidate。验证：ETF candidate 单测与 snapshot 摘要。风险：ETF 角色边界被扩大。
- [x] 5.2 让 `cn_etf_beta` 在 Governor 预算内运行，并输出 `eligible_etfs / selected_etfs / selection_reason_codes / sleeve_budget_used`。DoD：ETF sleeve 可独立审计。验证：ETF smoke run 与 audit 输出。风险：误复用个股 breakout 壳。
- [x] 5.3 保持 ETF 真值表与股票 `V2 canonical` 隔离，避免 governed 主线接入时污染股票链路。DoD：运行路径显式使用 ETF 真值表。验证：数据访问与 run_meta 检查。风险：资产表误路由。

## 6. Attribution Audit 与工作台摘要

- [x] 6.1 新增统一 attribution 汇聚层，输出 `state_logs / budget_logs / sleeve_logs / manual_override_logs / reason_code_summary`。DoD：归因信息不再只散落在 run_meta/debug。验证：audit 产物检查。风险：日志字段过多导致产物膨胀。
- [x] 6.2 将 governed 主线的 regime、Governor、attribution 摘要写入 `run_meta.json`、`audit.json` 和最小 snapshot contract。DoD：工作台无需重算核心逻辑即可展示状态来源。验证：snapshot 构建单测与前端 smoke。风险：前端兼容层字段缺失。
- [x] 6.3 补研究审计引用链，确保 audit 能回答“状态为何切换、预算为何变化、是否有人为介入”。DoD：`backtest-research-audit` 能引用 attribution 证据。验证：research audit 单测。风险：evidence_refs 不一致。

## 7. 回归验证与回退

- [x] 7.1 为 regime、Governor、股票 sleeve、ETF sleeve、attribution 增加最小单测和合同测试。DoD：新增 contract 有自动化覆盖。验证：定向 pytest。风险：测试夹具与旧产物不一致。
- [x] 7.2 运行 A 股主线最小回归，确认 contract 收敛未引入未解释的主行为漂移。DoD：输出差异说明。验证：baseline smoke/AB 对比。风险：L3 改动链过长。
- [x] 7.3 明确回退路径：关闭 Governor 新字段、回退 snapshot 暴露面、保留现有股票与 ETF 真值表不变。DoD：tasks、报告与实现说明都写清回退策略。验证：人工 review。风险：回退粒度过粗。

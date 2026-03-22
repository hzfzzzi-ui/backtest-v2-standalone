## 1. Source Governance

- [x] 1.1 产出 `v2` 字段级 source matrix，覆盖 `daily`、`adj_factor`、`daily_basic`、`stk_limit`、`suspend_d`、`moneyflow` 以及 `AkShare`、`巨潮资讯` 等补源候选；DoD：形成正式文档/结构化产物并纳入 `docs/db`；验证：字段、交易所、阶段三维可查；风险：字段口径描述不清会污染后续 schema 设计。
- [x] 1.2 完成 `BJ pre-2021-11-15` 与 `BJ post-2021-11-15` 的 source coverage 专项审计；DoD：形成分段审计报告并识别主问题是历史映射还是正式源缺失；验证：输出前后分段的 coverage/exception 汇总；风险：若仍混用 `bj%` 口径，结论会失真。
- [x] 1.3 设计并落地异常来源分类字典，至少区分 `missing_in_all_sources`、`fallback_available`、`mapping_failure`、`build_rule_rejected`；DoD：异常分类能在审计中聚合输出；验证：随机抽样 exception 可落到某一分类；风险：分类不互斥会导致统计重复。

## 2. Canonical Schema Governance

- [x] 2.1 更新 `pams_ohlcv_daily_v2` schema contract，引入四元 `row_status`、关键字段 `*_source`、`*_confidence`、`BJ` 阶段标记；DoD：schema contract 与 DDL 同步更新；验证：文档与 DDL 字段一致；风险：字段膨胀过快会增加回填成本。
- [x] 2.2 设计 canonical unresolved 表达，禁止无 `daily` 且无 `suspend_d` 的补位行伪装成正常停牌行；DoD：明确 `suspended_confirmed`、`synthetic_gap_fill`、`source_unresolved` 的判定规则；验证：样本 `eligible_no_source` 行能被重新分类；风险：规则改动会扩大与现有 runtime 的行为差异。
- [x] 2.3 设计 `pre_close`、`turnover_rate`、`adj_factor` 的分级补值规则；DoD：每个关键字段都有主源、补源、推导、填零的可信度边界；验证：文档中能解释 `pre_close_imputed_zero` 与 `turnover_rate_imputed_zero` 如何下降；风险：推导链过长会引入口径漂移。

## 3. Build Pipeline Refactor

- [x] 3.1 重构 raw -> canonical build，按新 `row_status` 规则落行并填充 `source`/`confidence` 字段；DoD：build 脚本支持新状态与来源表达；验证：单日 smoke 能正确区分 traded、confirmed suspend、unresolved；风险：历史回填耗时上升。
- [x] 3.2 为 `BJ` 引入阶段化 build 规则，区分历史映射阶段与正式北交所阶段；DoD：`BJ` 前后阶段使用不同判定与异常归因；验证：`2021-11-15` 前后 `BJ` 审计结果可显著分离；风险：lineage 规则定义不清会重复制造 unresolved。
- [x] 3.3 将 `daily_basic` 相关补值从“静默填 0”改为“带来源和可信度的补值”； DoD：`turnover_rate_imputed_zero` 仅保留真实零值或明确低可信零值；验证：异常表能区分真实零值与低可信填零；风险：过度保守会降低覆盖率。

## 4. Audit & Gate Governance

- [x] 4.1 重构 `v2` 审计脚本，输出 canonical gate 与 runtime gate 两套结论；DoD：summary 同时包含两层门禁与阻塞项；验证：新 summary 可直接回答“是否可升 canonical / 是否可供 runtime 消费”；风险：门禁定义过于复杂会影响可解释性。
- [x] 4.2 审计输出按 `SH`、`SZ`、`BJ pre-2021-11-15`、`BJ post-2021-11-15` 四维拆分；DoD：逐市场逐阶段 coverage/exception 可追踪；验证：报告能定位阻塞门禁的市场与阶段；风险：维度过多导致报表难读。
- [x] 4.3 为关键异常提供 drill-down 产物，覆盖 `eligible_no_source`、`turnover_rate_imputed_zero`、`pre_close_imputed_zero`；DoD：异常可按年份、交易所、symbol 样本追溯；验证：随机抽一类异常可定位到样本与来源解释；风险：产物过大影响审计运行时间。

## 5. Runtime Compatibility Governance

- [x] 5.1 设计并实现 `v2` runtime compatibility 层，明确它与 canonical 的边界；DoD：存在独立的 runtime 数据角色或视图/表；验证：配置可显式选择 canonical `v2` 或 runtime `v2`；风险：compat 逻辑散落到策略代码中。
- [x] 5.2 在 runtime compile 中增加 `v1`、canonical `v2`、runtime `v2` 的显式数据角色编译；DoD：runtime config 可审计当前消费角色；验证：`resolved_config` 与 `run_meta` 能回显数据角色；风险：编译层修改不当会影响现有 baseline。
- [x] 5.3 为 runtime compat 定义 unresolved 与低可信字段消费规则；DoD：runtime gate 明确哪些行/字段排除、降级或保留；验证：runtime 诊断产物可追溯排除原因；风险：规则过于激进导致策略覆盖率骤降。

## 6. Regression & Promotion

- [ ] 6.1 基于 `v1`、canonical `v2`、runtime `v2` 跑 `2016-2026`、`2007-2017`、`2007-2026` 三窗口回归；DoD：形成三路对照结果与行为差异说明；验证：产出 perf、trade diff、nav diff、run_meta 对照；风险：若 compat 规则未稳定，回归结果噪声大。
- [ ] 6.2 更新 `docs/db` runbook、schema contract、source matrix 与升格条件说明；DoD：正式文档能指导后续字段增删与回填；验证：文档路径固定且与实现一致；风险：文档滞后会破坏治理纪律。
- [ ] 6.3 形成 `v2` 正式升格建议书，明确 canonical 升格条件、runtime 切换条件与回退方案；DoD：可以直接回答“V2 是否已可作为正式主数据库引擎”；验证：建议书引用最新门禁与回归结果；风险：若 canonical 与 runtime 结论混淆，会误导切换时点。

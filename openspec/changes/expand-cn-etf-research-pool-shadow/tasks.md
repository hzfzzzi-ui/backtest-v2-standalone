## 1. Catalog 与 preset

- [x] 1.1 新增 `cn_etf_research_shadow_pool_v1` preset、候选清单和 `shadow_role` 映射。DoD：preset 只展开 `510880.SH`、`512890.SH`、`518880.SH`、`159915.SZ`、`588000.SH`、`159845.SZ`；验证：catalog 单测覆盖 preset 展开、symbol 标准化和 role map；风险：误改 formal core symbols。
- [x] 1.2 在 universe resolver metadata 中输出 formal、shadow、deferred 分类。DoD：`run_meta` / universe meta 能区分 `formal_scope_symbols`、`shadow_symbols`、`deferred_symbols`；验证：resolver 单测覆盖 shadow preset 与 unsupported symbol；风险：研究入口静默吞掉非 catalog 标的。
- [x] 1.3 明确 deferred 候选拒绝原因。DoD：`511880.SH`、`511260.SH`、跨境 ETF、行业/主题 ETF 不进入 v1 preset；验证：单测断言 reject reason；风险：把现金层或跨境语义混入本轮 ETF sleeve。

## 2. Research study 与产物元信息

- [x] 2.1 新增 shadow pool study。DoD：`research/studies/etf/cn_etf_research_shadow_pool_v1.study.yaml` 可由 `study_runner` 加载；验证：study 加载/生成 request 的单测或 smoke；风险：study 直接引用 raw symbols 绕过 catalog。
- [x] 2.2 在 ETF summary / diagnostics 中输出 pool version 与 role map。DoD：shadow run 产物包含 `pool_version`、`research_only`、`shadow_role_map`、coverage window；验证：summary 构建单测；风险：展示层无法区分正式和研究候选。
- [x] 2.3 输出 promotion gate 字段。DoD：每个候选都有 `formal_eligible`、`promotion_gate_status`、`reject_reason`；验证：short-history 候选单测覆盖 `short_history`；风险：短历史收益被误读为已可转正式。

## 3. Formal 隔离与审计

- [x] 3.1 增加 formal sleeve shadow-promotion guard。DoD：`formal_etf_pool_v1` 下 shadow symbol 出现在 formal selected ETFs 时会触发 audit violation；验证：research audit 单测构造违规输出；风险：shadow 候选静默进入 live baseline。
- [x] 3.2 保持默认 ETF beta contract 不变。DoD：默认 core symbols、limited defense candidates、formal excluded symbols 与当前值一致；验证：`test_etf_beta_contract` 覆盖默认合同；风险：扩池实现意外改变正式候选池。
- [x] 3.3 确认股票 sleeve 与 account layer 无行为变化。DoD：本 change 不修改股票 alpha、账户预算、成交/信号时点；验证：git diff 与相关单测；风险：把资产池研究扩展成组合主逻辑改动。

## 4. Shadow 实验与分析

- [x] 4.1 跑 shadow pool smoke。DoD：shadow study 至少能在一个短窗口生成机器包和人类包；验证：容器内 `study_run` smoke exit 0；风险：数据覆盖或 catalog 入口未打通。
- [x] 4.2 跑三窗口研究。DoD：产出 `2016-2026`、`2012-2017`、`2012-2026` 对照结果；验证：每个窗口记录 exp_id、配置快照和审计摘要；风险：短历史候选导致窗口不可比。
- [x] 4.3 形成 promotion recommendation。DoD：按候选输出“建议转正式 / 保留 shadow / 暂缓 / 剔除”及原因；验证：报告同时包含收益、回撤、波动、交易数、actual exposure、coverage、流动性和相关性信息；风险：只用收益判断。

## 5. 验证与回退

- [x] 5.1 运行相关单测。DoD：catalog、resolver、ETF contract、research audit 相关测试通过；验证：`python -m pytest` 指定测试文件；风险：只跑 smoke 漏掉合同漂移。
- [x] 5.2 运行 OpenSpec 校验。DoD：`openspec validate --changes expand-cn-etf-research-pool-shadow` 通过；验证：CLI exit 0；风险：delta spec 格式不满足归档要求。
- [x] 5.3 跑 formal baseline regression 或等价 guard。DoD：默认正式配置仍指向原 formal 池并通过回归门；验证：baseline regression 或合同级 guard 产物；风险：shadow preset 影响正式 baseline。
- [x] 5.4 记录回退路径。DoD：实现说明写清删除 shadow preset/study/audit 字段即可回退，baseline 不迁移；验证：人工 review；风险：把运行产物当源码合同保留。

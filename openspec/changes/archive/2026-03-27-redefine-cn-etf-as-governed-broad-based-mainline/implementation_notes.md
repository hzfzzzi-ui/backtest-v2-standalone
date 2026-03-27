## 实现结论

`redefine-cn-etf-as-governed-broad-based-mainline` 已完成实现与独立宽基 ETF study 验证。

本轮结论不是“ETF 独立主线成立”，而是：

- Governor/CTA 统一边界与宽基 ETF 主线本地决策已经能被显式拆分和审计
- 宽基 ETF 现在可以用自己的进入/退出、受控承接与 fallback 逻辑运行
- 但本轮所有 standalone mainline 变体仍显著低于 `6%-9% CAGR` 目标
- 因此这条 change 的最终结论是：**实现完成，但不建议升格为新的正式 ETF 主研究线**

## 改了什么

### 1. ETF contract owner 收口

在 [etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py) 中新增并规范化了：

- `strategy_role`
- `governor_boundary_mode`
- `local_policy_mode`
- `controlled_accumulation_mode`
- `exposure_policy_family = broad_based_standalone_mainline_v1`

同时新增了宽基主线的 broad-based bucket 校验、Governor/local split 摘要输出，以及 phase1 summary contract 扩展。

### 2. Schema 与研究入口收口

在 [semantic_config_schema.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py) 中扩展了宽基 ETF 独立主线所需字段，使前端/研究入口/后端编译出的 runtime config 保持一致。

新增独立 study：

- [cn_broad_based_standalone_mainline.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_standalone_mainline.study.yaml)

### 3. Provider 本地 policy 翻译

在 [cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py) 中实现了：

- Governor 边界到 ETF 本地 policy 的翻译
- standalone mainline 的 runtime reason codes
- controlled accumulation 模式暴露
- Governor/local policy 拆分 diagnostics

### 4. Audit 与产物可观测性

在 [research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py) 中新增：

- `governor_boundary` / `local_policy_decision` 拆分检查
- `fallback_exposure_day_count`
- `fallback_exposure_longest_streak`
- `controlled_accumulation_day_count`
- `layering_band_counts`
- standalone mainline source-entry 校验

## 研究结果

真实 study 已运行：

- `CTRL_A0_TOP2_BOND` -> [exp_20260326_082121189_6549](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260326_082121189_6549)
- `MAINLINE_LIGHT_BOND` -> [exp_20260326_082129155_e5ba](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260326_082129155_e5ba)
- `MAINLINE_LIGHT_TD_BOND` -> [exp_20260326_082136478_738b](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260326_082136478_738b)
- `MAINLINE_LIGHT_TD_CASH` -> [exp_20260326_082143832_2e35](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/experiments/exp_20260326_082143832_2e35)

汇总产物：

- [variant_compare.csv](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_broad_based_etf_standalone_mainline_20260326/variant_compare.csv)
- [summary.json](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_broad_based_etf_standalone_mainline_20260326/summary.json)

关键结果：

- 控制组 `CTRL_A0_TOP2_BOND`
  - `CAGR 1.99%`
  - `MaxDD -19.46%`
  - `Sharpe 0.240`
- `MAINLINE_LIGHT_BOND`
  - 与控制组结果基本一致
- `MAINLINE_LIGHT_TD_BOND`
  - `CAGR 1.43%`
  - 比控制组更差
- `MAINLINE_LIGHT_TD_CASH`
  - `CAGR 2.88%`
  - `Sharpe 0.309`
  - 但 `MaxDD -23.07%`

可归纳为：

- 只在 `LIGHT` 放松承接，并没有把实际部署拉起来
- `LIGHT + CONTROLLED_TRANS_DOWN + cash fallback` 的收益最好，但更像减少防守后的风险暴露提升
- 所有变体仍为 `UNDERDEPLOYED`
- 平均实际暴露仍只有约 `22% ~ 27%`

因此本轮只能证明：

- 这套“统一 Governor + ETF 自有进入退出逻辑”的边界是可实现、可审计的
- 但它还没有证明自己足以替代旧 A0 主研究线

## 验证

已通过：

```bash
pytest tests/unit/test_etf_beta_contract.py tests/unit/test_semantic_config_compiler.py tests/unit/test_cn_etf_beta_signal_provider.py tests/unit/test_research_audit_contract.py -q
python -m backend.cli study_run etf/cn_broad_based_standalone_mainline --dry-run
docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_broad_based_standalone_mainline
openspec validate redefine-cn-etf-as-governed-broad-based-mainline --type change --strict
openspec instructions apply --change "redefine-cn-etf-as-governed-broad-based-mainline"
```

## 风险

- 这条 change 已经改变了 ETF 的正式研究语义，后续如果继续叠加新规则族，很容易把“边界合理化”重新做成“策略大杂烩”
- `MAINLINE_LIGHT_TD_CASH` 的收益提升伴随更差回撤，不能直接当作正式胜出版
- 当前研究仍使用 A0 proxy 宽基池，不是最终标准池

## 回退

若要回退本轮，实现层主要撤回：

- [semantic_config_schema.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py)
- [etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)
- [cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/engine_vector/cn_etf_beta_signal_provider.py)
- [research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
- [cn_broad_based_standalone_mainline.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_standalone_mainline.study.yaml)
- [test_etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_etf_beta_contract.py)
- [test_cn_etf_beta_signal_provider.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_cn_etf_beta_signal_provider.py)
- [test_research_audit_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_research_audit_contract.py)
- [test_semantic_config_compiler.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_semantic_config_compiler.py)

研究产物回退时可删除：

- [study_cn_broad_based_etf_standalone_mainline_20260326](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/outputs/ops/study_cn_broad_based_etf_standalone_mainline_20260326)

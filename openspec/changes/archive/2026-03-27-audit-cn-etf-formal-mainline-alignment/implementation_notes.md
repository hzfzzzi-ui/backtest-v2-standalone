## Summary

本轮实现没有优化 ETF 收益，也没有改 ETF 主交易逻辑；只做了根目录正式文档 [A股ETF子系统策略思路md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股ETF子系统策略思路md) 的对齐审计收口。

本轮新增了 ETF 正式分类真相：

- `formal_mainline`
- `research_only`
- `do_not_promote`

并把该分类下沉到 ETF summary / `run_meta` / `research_audit` 可消费字段里，而不是继续靠文件名或口头说明区分。

## Files Changed

- [backend/core/config/etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)
- [backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
- [backend/api/backtest_v2/semantic_config_schema.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py)
- [research/studies/etf/cn_etf_first_wave_core.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_first_wave_core.study.yaml)
- [research/studies/etf/cn_broad_based_rotation_template_a.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_rotation_template_a.study.yaml)
- [research/studies/etf/cn_broad_based_standalone_mainline.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_standalone_mainline.study.yaml)
- [research/studies/etf/cn_broad_based_governed_exposure_policy.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_governed_exposure_policy.study.yaml)
- [tests/unit/test_etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_etf_beta_contract.py)
- [tests/unit/test_research_audit_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_research_audit_contract.py)

## Formal Alignment Result

当前显式保留为正式主线的 ETF study：

- [research/studies/etf/cn_etf_first_wave_core.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_first_wave_core.study.yaml)
  - `formal_alignment_classification = formal_mainline`

当前显式降级为 `do_not_promote` 的 ETF study：

- [research/studies/etf/cn_broad_based_rotation_template_a.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_rotation_template_a.study.yaml)
- [research/studies/etf/cn_broad_based_standalone_mainline.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_standalone_mainline.study.yaml)
- [research/studies/etf/cn_broad_based_governed_exposure_policy.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_governed_exposure_policy.study.yaml)

当前降级依据包括：

- 使用正式文档明确排除的资产：
  - `511010.SH`
  - `588000.SH`
  - `159915.SZ`
- 使用超出正式口径的信号语义：
  - `broad_based_rotation_template_a`
  - `broad_based_rotation_mainline`
  - `light_and_controlled_trans_down`
- 使用超出正式口径的输出 contract：
  - `template_proxy_map`
  - `proxy_replacement_mode`
  - `core_slot / growth_slot` 风格语义

说明：

- 这次没有给所有历史 ETF study 全量补显式 metadata。
- 未显式标注的历史 study，后续应以 runtime summary / audit 中的正式对齐分类为准，不得自动视为正式主线。

## Runtime / Audit Truth

新增的 ETF 正式对齐字段：

- `formal_alignment_reference`
- `formal_alignment_status`
- `formal_mainline_compatible`
- `formal_alignment_reason_codes`
- `formal_alignment_evidence`

这些字段现在由 [backend/core/config/etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py) 统一生成，并由 [backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py) 统一消费。

对齐判断规则收口为：

- 只要使用正式文档排除资产，直接进入 `do_not_promote`
- 只要使用越界 Governor / signal / output contract 语义，直接进入 `do_not_promote`
- 只有 Phase 1 正式资产池、limited defense candidate 与旧 `etf_beta_v1_control` 边界都满足时，才进入 `formal_mainline`

## Verification

已通过：

```bash
pytest tests/unit/test_etf_beta_contract.py tests/unit/test_research_audit_contract.py -q
python -m py_compile backend/core/config/etf_beta_contract.py backend/core/audit/research_audit.py backend/api/backtest_v2/semantic_config_schema.py
openspec validate audit-cn-etf-formal-mainline-alignment --type change --strict
```

本轮验证覆盖：

- 正式路径能得到 `formal_mainline`
- 含 `159915 / 511010` 的越界路径会得到 `do_not_promote`
- audit 会把 `do_not_promote` ETF path 直接打成 `FAIL`

## Risks

- 当前 formal 对齐仍建立在现有 Phase 1 文档边界上，不代表 ETF 正式主线收益已成立。
- `cn_etf_first_wave_core` 被保留为 `formal_mainline`，只表示口径兼容，不表示收益优先或建议继续优化。
- 历史 ETF studies 仍然较多；本轮只对最关键的正式/研究分支做了显式降级标记。

## Rollback

最小回退文件：

- [backend/core/config/etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/config/etf_beta_contract.py)
- [backend/core/audit/research_audit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/audit/research_audit.py)
- [backend/api/backtest_v2/semantic_config_schema.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/api/backtest_v2/semantic_config_schema.py)
- [research/studies/etf/cn_etf_first_wave_core.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_etf_first_wave_core.study.yaml)
- [research/studies/etf/cn_broad_based_rotation_template_a.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_rotation_template_a.study.yaml)
- [research/studies/etf/cn_broad_based_standalone_mainline.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_standalone_mainline.study.yaml)
- [research/studies/etf/cn_broad_based_governed_exposure_policy.study.yaml](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/research/studies/etf/cn_broad_based_governed_exposure_policy.study.yaml)
- [tests/unit/test_etf_beta_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_etf_beta_contract.py)
- [tests/unit/test_research_audit_contract.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/tests/unit/test_research_audit_contract.py)

最小回归命令：

```bash
pytest tests/unit/test_etf_beta_contract.py tests/unit/test_research_audit_contract.py -q
openspec validate audit-cn-etf-formal-mainline-alignment --type change --strict
```

## Implementation Notes

### Scope

本变更只建立 `cn_etf_research_shadow_pool_v1` 研究池，不修改 `formal_etf_pool_v1`、`CN_STOCK_ETF_FORMAL_V1`、股票 sleeve、账户预算、信号时点或成交时点。

同步修复了一个运行时传参问题：`config_json` 语义配置路径下，显式设置的 `universe.benchmark` 现在会进入 execution overrides。该修复用于避免 `cn_etf` 研究运行在未识别 benchmark 时退回首个 ETF 符号，不改变研究逻辑。

### Three-Window Runs

| Window | Exp ID | CAGR | Sharpe | Max DD | Trades | Turnover | Avg gross exposure | Benchmark | Selected ETFs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 2012-2017 | `exp_20260509_030857319_111c` | 18.64% | 0.845 | -41.12% | 21 | 0.0081 | 0.610 | `510880.SH` | `510880.SH` |
| 2016-2026 | `exp_20260509_030922338_bea2` | 10.37% | 0.793 | -16.20% | 42 | 0.0086 | 0.742 | `510880.SH` | `159845.SZ`, `159915.SZ` |
| 2012-2026 | `exp_20260509_030952412_ada7` | 15.29% | 0.863 | -41.12% | 62 | 0.0093 | 0.688 | `510880.SH` | `159845.SZ`, `159915.SZ` |

Run metadata confirms:

- `pool_version = cn_etf_research_shadow_pool_v1`
- `research_only = true`
- `benchmark_source = run_config.universe.benchmark`
- `shadow_promotion_violation_count = 0`

Research audit outcome is intentionally not promotable:

- `accounting_integrity`: PASS
- `timing_alignment`: PASS
- `universe_lineage`: PASS
- `execution_realism`: UNKNOWN, because fill-bar lookup evidence is unavailable in the current audit artifact
- `result_sanity`: UNKNOWN or WARN depending on window
- `etf_beta_sleeve`: FAIL with `do_not_promote`, because this is a research-only shadow pool

### Candidate Diagnostics

Local data coverage and liquidity proxy from `pams_cn_etf_daily.amount`:

| Symbol | Role | Coverage Start | Rows | Avg Amount 3Y | Avg Amount 1Y | Correlation Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `510880.SH` | value/dividend | 2007-01-18 | 4688 | 0.4m | 0.5m | Correlation with `512890.SH` is 0.89; role overlap is high. |
| `512890.SH` | dividend low-vol overlap | 2019-01-18 | 1766 | 0.4m | 0.6m | High overlap with `510880.SH`; not selected in final windows. |
| `518880.SH` | gold defense | 2013-07-29 | 3104 | 2.7m | 5.5m | Low correlation to equity/growth candidates; better treated as defense-layer research. |
| `159915.SZ` | ChiNext growth | 2012-01-04 | 3479 | 3.1m | 3.9m | Correlation with `588000.SH` is 0.83; growth role overlap is high. |
| `588000.SH` | STAR 50 technology growth | 2020-11-16 | 1326 | 3.7m | 4.2m | Short history; high overlap with `159915.SZ`; not enough hard-window evidence. |
| `159845.SZ` | CSI 1000 replacement | 2021-03-31 | 1235 | 1.1m | 1.2m | Short history; selected in recent/full windows but absent from hard-window evidence. |

Amounts are local DB `amount` values and should be treated as a liquidity proxy until the market-data unit convention is separately audited.

### Promotion Recommendation

Conclusion: do not promote this pool directly into `formal_etf_pool_v1`.

- `510880.SH`: keep shadow. It is the only selected ETF in the hard gate window, but full-window drawdown remains -41.12% and local amount is low. It needs a dividend-role comparison against `512890.SH` before any formal decision.
- `512890.SH`: keep shadow comparison only. It overlaps strongly with `510880.SH` and was not selected by the three-window run.
- `518880.SH`: keep shadow, but move the next decision to the defense/cash-equivalent layer instead of core beta. Its diversification profile is useful, but the semantics are not the same as broad equity beta.
- `159915.SZ`: keep shadow as growth satellite candidate. It is selected in 2016-2026 and 2012-2026, but must be capped and compared against `588000.SH` because growth exposure is concentrated.
- `588000.SH`: defer formal promotion. It has short history and high overlap with `159915.SZ`.
- `159845.SZ`: defer formal promotion. It is selected in recent/full windows, but it has no 2012-2017 hard-window evidence because of short listing history.

Separate future changes are still required for:

- cash / money-market / short-duration bond layer: `511880.SH`, `511260.SH`
- cross-border ETF layer: `513500.SH`, `513100.SH`
- industry / theme ETF research

### Same-Contract Formal Pool Control

为避免把 `baseline_V10_1` 股票主线当成 ETF 扩池对照，补充了 research-only control study：

- Study: `etf/cn_etf_formal_pool_rotation_control_v1`
- Contract: same standalone broad-based rotation contract as `cn_etf_research_shadow_pool_v1`
- Difference: only swaps the pool back to `formal_etf_pool_v1` through `cn_etf_first_wave_core`
- This control is not the formal live ETF baseline and does not modify `formal_etf_pool_v1`.

| Window | Formal Control Exp | Formal CAGR | Formal Sharpe | Formal Max DD | Formal Trades | Shadow Exp | Shadow CAGR | Shadow Sharpe | Shadow Max DD | Shadow Trades |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 2012-2017 | `exp_20260509_032831126_64ae` | -3.43% | -0.094 | -40.85% | 26 | `exp_20260509_030857319_111c` | 18.64% | 0.845 | -41.12% | 21 |
| 2016-2026 | `exp_20260509_032903960_f020` | 4.22% | 0.270 | -69.41% | 56 | `exp_20260509_030922338_bea2` | 10.37% | 0.793 | -16.20% | 42 |
| 2012-2026 | `exp_20260509_032947280_4a51` | 1.73% | 0.214 | -69.45% | 74 | `exp_20260509_030952412_ada7` | 15.29% | 0.863 | -41.12% | 62 |

Same-contract interpretation:

- Shadow pool beats formal control on CAGR and Sharpe in all three windows.
- Modern and full windows show materially better drawdown for shadow: +53.22pct MaxDD improvement in 2016-2026 and +28.33pct in 2012-2026.
- Hard-gate window drawdown is roughly tied: shadow is slightly worse by 0.27pct MaxDD, but CAGR and Sharpe are much better.
- Shadow uses fewer trades in all three windows.

This strengthens the asset-pool-expansion thesis, but it still does not justify direct formal promotion because the selected shadow winners are partly short-history or non-core-beta assets:

- `159845.SZ` has no 2012-2017 evidence.
- `159915.SZ` is growth exposure and overlaps with `588000.SH`.
- `518880.SH` contributes useful defense behavior but belongs more naturally to the defense layer.
- `510880.SH` is the only hard-window selected shadow ETF, but it needs a dividend-role comparison against `512890.SH`.

### Formal Guard

Formal guard evidence:

- `python -m pytest tests/unit/test_experiment_runtime_service.py tests/unit/test_cn_etf_catalog.py tests/unit/test_universe_resolver.py tests/unit/test_etf_beta_contract.py tests/unit/test_research_audit_contract.py tests/unit/test_etf_research_mainline_r1_study.py -q` passed, 76 tests.
- Docker dry-run for `etf/cn_etf_first_wave_core` still emits `cn_etf_first_wave_core` with formal symbols `510300.SH`, `510500.SH`, `510050.SH`, `512100.SH`, `511010.SH`.
- Audit guard rejects shadow symbols when a non-research run claims `formal_etf_pool_v1`.

### Rollback

Rollback does not require baseline migration. Remove:

- `cn_etf_research_shadow_pool_v1` catalog preset and metadata helpers
- shadow pool resolver metadata pass-through
- shadow pool summary/audit fields
- `research/studies/etf/cn_etf_research_shadow_pool_v1.study.yaml`
- tests added for the shadow pool and benchmark pass-through

`outputs/` artifacts are run products and should not be treated as source contracts.

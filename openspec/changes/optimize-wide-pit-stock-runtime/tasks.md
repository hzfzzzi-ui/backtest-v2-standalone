## 1. 合同与剖面

- [x] 1.1 创建 OpenSpec 变更。DoD：proposal/design/spec/tasks 定义 1-4 优化顺序与非目标；验证：`openspec validate optimize-wide-pit-stock-runtime --strict`。
- [x] 1.2 增加运行期复杂度剖面。状态：完成运行侧剖面。`run_profile.json` 和 `run_profile_checkpoint.json` 已暴露 rows、symbols、trading_days、matrix cell estimate、runtime optimization flags、provider precompute checkpoint；内存峰值仍依赖 Docker OOM 状态判断。

## 2. PIT interval pushdown

- [ ] 2.1 增加 membership interval + warmup 行级裁剪。状态：实现后被 parity 否决，正式研究路径已关闭。B0 指标从 CAGR 14.31% 漂移到 11.68%，说明当前行级裁剪会破坏持仓后价格数据或指标 warmup 语义，不能接受。
- [x] 2.2 输出 pushdown 审计。DoD：run_meta.data_bundle 写出 before/after rows、warmup days、dropped rows；验证：B0 pushdown 试运行已写出 before=3,271,326、after=2,193,771、dropped=1,077,555。

## 3. top-k / argpartition

- [x] 3.1 新增稳定 top-k helper。DoD：与全排序 top-k 在分数、tie-break、NaN 行为上等价；验证：unit test。
- [x] 3.2 替换候选排序热路径。DoD：只替换最终 top-k 选择，不改变排序母体和结果；验证：B0 parity 通过。

## 4. candidate-first expensive scoring

- [x] 4.1 将可安全后置的昂贵 scoring 绑定到候选范围。状态：接受范围调整为“跳过当前配置未使用的昂贵评分矩阵”，不改变全 active rank 母体；验证：B0 parity 通过。
- [x] 4.2 对不能安全后置的评分保留原路径并记录原因。状态：optimization notes 已进入 provider precompute checkpoint，可解释 deferred/skip/保留原因。

## 5. streaming rolling state

- [x] 5.1 增加 rolling state 原型/helper。DoD：rolling mean/max/min 单元测试与 pandas rolling 对齐。
- [x] 5.2 在正式路径前加 parity 闸门。DoD：未通过 B0 parity 前不默认替换 full matrix path；当前正式路径未启用 streaming rolling state。

## 6. 验证与重跑

- [x] 6.1 运行相关单测。结果：`39 passed`。
- [x] 6.2 跑 B0 `1626` parity。结果：安全优化版本 `exp_20260510_054904100_3634` 与原 B0 `exp_20260510_045702549_01ea` 指标完全一致，总耗时从 199.967s 降至 118.227s。
- [x] 6.3 若 parity 通过，重跑 A1 `1626`。初次结果：`exp_20260510_055220963_7bfd` 仍 OOM/exit 137，未产生 perf/run_meta/run_profile；后续第 7 阶段解除阻塞。

## 当前验收结论

- 可接受：top-k partial selection、跳过当前配置未使用的昂贵评分矩阵、rolling helper 的非正式原型。
- 不可接受：当前 PIT interval 行级裁剪。它不是等价优化，已关闭。
- 阻塞已解除：A1 `HS300_ZZ500_CSI1000` 主窗口在第 7 阶段跑通。
- 研究结论：A1 主窗口显著弱于 B0，当前 CSI1000 直接扩池方案不建议推进。

## 7. active-set sparse scoring 与失败前 profile

- [x] 7.1 增加失败前 checkpoint profile。DoD：A1 OOM run `exp_20260510_062538038_b180` 留下 `run_profile_checkpoint.json`，最后阶段为 `provider_precompute_start`，包含 phase、symbols、trading_days、rows、matrix cell estimate、runtime optimization flags。
- [x] 7.2 贯通 runtime optimization flags 到 signal provider。DoD：study YAML 的 `runtime_optimization.active_set_sparse_scoring` 已进入 provider precompute；默认无该 flag 时不启用 deferred path。
- [x] 7.3 residual-only 安全子集 deferred row-rank。DoD：只在 residual-only 安全前置条件满足时，不物化 `residual_strength_score/final_score` 全量矩阵；day-signal 阶段从当天 full-rank row 取候选和持仓分数；单测覆盖等价信号分数。
- [x] 7.4 验证。DoD：相关单测 `102 passed`；B0 `1626` parity 通过，`exp_20260510_063251764_5c36` 指标完全一致；A1 `1626` 跑通，`exp_20260510_063616187_0245`，但主窗口表现显著弱于 B0。

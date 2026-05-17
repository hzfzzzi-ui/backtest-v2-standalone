## 1. 实验合同

- [x] 1.1 创建 OpenSpec 变更。DoD：proposal/design/spec/tasks 明确单变量为股票池扩展；验证：`openspec status` 能识别 4 个 artifact；风险：未先锁定口径就直接跑收益。
- [x] 1.2 新增 stock-only study。DoD：`research/studies/v10/hs300_zz500_csi1000_pit_pool_expansion_v1.study.yaml` 可 dry-run，包含 2 个 variant 与 3 个窗口；验证：`study_run --dry-run` 输出 6 个计划项；风险：variant 误改股票逻辑。

## 2. 联合 PIT universe 支撑

- [x] 2.1 新增 `HS300_ZZ500_CSI1000` resolver。DoD：静态 as-of resolver union `000906.SH` 与 `000852.SH`；验证：unit test 覆盖去重与 meta；风险：用静态 CUSTOM 清单造成未来成分泄露。
- [x] 2.2 新增 lineage。DoD：`get_universe_lineage("HS300_ZZ500_CSI1000")` 返回 PIT 成分表与双 index_code 说明；验证：unit test；风险：审计报告无法解释来源。
- [x] 2.3 扩展 `PIT_DYNAMIC` 数据包构建。DoD：动态 membership 能加载两个指数、保留 `index_code` 并 union symbols；验证：unit test；风险：只在 start_date 做静态快照。
- [x] 2.4 单独审计 CSI1000 子集。DoD：联合模式下 CSI1000 static fallback 默认被阻断，provider floor 写入 meta；验证：unit test；风险：CSI800 PIT 形状掩盖 CSI1000 低保真数据。

## 3. 审计与验证

- [x] 3.1 跑本地单测。DoD：新增/相关测试通过；验证：`python -m pytest ... -q`；风险：只跑真实实验漏掉合同漂移。
- [x] 3.2 跑 OpenSpec 校验。DoD：`openspec validate evaluate-csi1000-pit-stock-pool-expansion --strict` 通过；验证：CLI exit 0；风险：spec 不可归档。
- [x] 3.3 在 Docker 内跑 dry-run。DoD：容器内 `study_run` dry-run 生成 6 个计划项；验证：stdout plan；风险：本地路径可用但容器不可用。
- [x] 3.4 输出静态审计。DoD：产物包含 symbol 数、新增/重叠、覆盖、行业、provider floor、表规模和运行时影响；验证：审计 JSON/摘要存在；风险：未审计就解释收益。

## 4. 分阶段回测

- [ ] 4.1 跑 `1626` stock-only 主窗口。DoD：B0 与 A1 均成功并记录 exp_id、耗时、核心指标；验证：`perf.json`、`run_profile.json`、study conclusion；风险：扩池后运行时间不可控。
  - 当前状态：B0 成功，A1 在 `HS300_ZZ500_CSI1000` 全量主窗口运行中被 OOM/exit 137 中断，仅产出 `run_config.json`，需要先处理运行内存/产物规模后再重跑。
- [ ] 4.2 若主窗口可解释，跑 `1217` 硬门槛。DoD：硬门槛窗口输出同窗口比较；验证：exp artifacts；风险：CSI1000 provider floor 导致该窗口只能做部分证据解释。
- [ ] 4.3 若硬门槛不过度恶化，跑 `1226` 全周期。DoD：输出全周期对比和审计；验证：exp artifacts；风险：把不完整 CSI1000 历史误读为完整 PIT。
- [ ] 4.4 形成是否进入 combo 层的结论。DoD：明确继续/拒绝/暂缓，并说明风险、验证和回退；验证：研究日志或报告；风险：收益改善但不可归因。
## 5. A1 负贡献归因

- [x] 5.1 实现只读归因模块，消费 B0/A1 已有 experiment artifacts 和 PIT 数据；DoD：输出 membership/industry/liquidity/market-cap/rank/exit 维度 CSV/JSON；验证：新增 unit tests；风险：不得修改 baseline、策略口径或 outputs 既有实验产物。
- [x] 5.2 在 Docker 内运行 A1 归因；DoD：产物落在 `outputs/studies/v10/hs300_zz500_csi1000_pit_pool_expansion_v1/negative_attribution/`；验证：summary JSON 和 markdown report 存在；风险：数据库连接和符号格式必须审计。
- [x] 5.3 输出研究判断；DoD：明确拖累来自新增 CSI1000 直接交易贡献、排序挤占、流动性/市值/行业暴露或退出阶段；验证：报告包含 top negative groups 和证据路径；风险：只基于 1626 主窗口，不能当作三窗口升级依据。
## 6. A2 CSI1000_new 市值门槛 AB

- [x] 6.1 补充 A2 研究入口；DoD：study plan 新增 `A2_HS300_ZZ500_CSI1000_MCAP100`，且除 `universe.filters.csi1000_new_min_circ_mv_yi=100` 外保持 A1 口径不变；验证：dry-run plan 和 unit test；风险：不得静态删 symbol 或混入排序/退出改动。
- [x] 6.2 实现当日门控；DoD：仅对当日 `csi1000_new` 标的应用 `circ_mv>=100亿元` 买入候选门槛，CSI800 原池和既有退出逻辑不变；验证：data matrix 单测覆盖 csi800_only / csi1000_new / overlap；风险：门槛不得阻断已有持仓退出。
- [x] 6.3 Docker 跑 `1626` A2；DoD：记录 exp_id、耗时、perf、run_profile，并和 B0/A1 同窗比较；验证：study_run `--window 1626 --variant A2_HS300_ZZ500_CSI1000_MCAP100` 成功；风险：若指标仍弱，只能作为失败归因，不得升级 baseline。
- [x] 6.4 输出 A2 判断；DoD：说明 A2 是否修复 A1 的 CSI1000_new 负贡献、回撤和退出亏损；验证：归因/summary 产物存在；风险：仅主窗口结果不能代替三窗口结论。

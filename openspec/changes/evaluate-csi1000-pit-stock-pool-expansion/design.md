## Context

事实：

- 当前 `HS300_ZZ500` resolver 使用 `pit_index_constituents(index_code='000906.SH')`，语义上等价于 CSI800 PIT。
- 当前 `CSI1000` resolver 已存在，使用 `pit_index_constituents(index_code='000852.SH')`。
- `CSI1000` 已有 refresh 侧表审计，且历史 provider floor 早于 2015-07-31 的区间不能伪装成正式 PIT 覆盖。

本轮需要的是“CSI800 + CSI1000 的 PIT 联合股票池”，不是单独把股票池切到 `CSI1000`，也不是 `ALL_A`。

## Goals / Non-Goals

**Goals**

- 增加 `HS300_ZZ500_CSI1000` 联合 PIT universe mode。
- 保持 `membership_mode=PIT_DYNAMIC` 下按窗口动态消费历史成员，而不是 start-date 静态快照。
- 新增 stock-only A/B study，先比较原股票池与扩展股票池。
- 在任何回测结论前先完成静态审计，并显式标注 CSI1000 覆盖下限。

**Non-Goals**

- 不补造 `2012-2015` CSI1000 PIT 历史。
- 不改 alpha、排名、退出、风控、仓位预算、ETF 腿或 combo allocator。
- 不把本轮结果自动升级到 `baseline_V10.1` 或组合基线。
- 不在 `outputs/` 中沉淀核心业务逻辑。

## Decisions

### Decision 1: 新增联合 mode，而不是用 CUSTOM symbols

采用 `HS300_ZZ500_CSI1000`，从两个 index_code 的 PIT 区间表按 as-of 或窗口 overlap union 成员。

原因：

- `CUSTOM` 会退化为静态代码清单，无法表达历史进出，存在未来成分泄露风险。
- 单独 `CSI1000` 会丢掉原本的 HS300/ZZ500 主池，不符合用户要求的“加上 CSI1000”。

### Decision 2: stock-only 先行

第一阶段只跑 `cn_a_equity` 个股腿 A/B：

- `B0_HS300_ZZ500`: 当前股票池。
- `A1_HS300_ZZ500_CSI1000`: 只扩展股票池。

原因：

- 个股池扩展属于 L3。必须先证明个股腿自身可解释，再进入组合层。
- combo 结果可能被 ETF 腿、防守层和账户预算稀释，不能作为第一证据。

### Decision 3: 动态 membership 需要按 index 组合，并单独审计 CSI1000

运行时 `PIT_DYNAMIC` 加载时分别读取：

- `000906.SH`：CSI800 PIT history。
- `000852.SH`：CSI1000 PIT history。

然后 union symbol 并保留 membership_history 中的 `index_code`。审计分两层：

- 整体 union 审计：行数、symbol 数、窗口覆盖、动态成员属性。
- CSI1000 子集审计：refresh sidecar、provider floor、static fallback 阻断。

原因：

- 如果只审计 union，CSI800 的多起点历史可能掩盖 CSI1000 static fallback。
- 如果强迫所有 union 行都有 CSI1000 calendar metadata，CSI800 行会造成误报。

### Decision 4: 三窗口照旧，但结论分阶段

Study 定义包含三窗口：

- `1626`: 主开发窗口。
- `1217`: 硬门槛窗口。
- `1226`: 全周期审计窗口。

执行顺序必须是：

1. 静态审计。
2. dry-run 验证 payload。
3. `1626` stock-only。
4. 若可解释，再跑 `1217`。
5. 若硬门槛不崩，再跑 `1226`。
6. 只有 stock-only 通过后，才讨论 combo 层。

## Risks / Trade-offs

- [Risk] `2012-2015` CSI1000 provider floor 不覆盖。  
  缓解：审计输出 `csi1000_provider_floor_date`，全周期窗口结论不得把该段当作正式 CSI1000 PIT 证据。

- [Risk] 新增小盘池提升收益但同时提升换手、停牌、流动性和回撤。  
  缓解：本轮静态审计和后续回测必须报告新增标的占比、交易数、集中度、行业分布、回撤和退出原因。

- [Risk] 联合 membership 审计掩盖 CSI1000 static fallback。  
  缓解：对子集单独调用 CSI1000 audit，并使用该子集质量决定是否 block。

- [Risk] 运行时间显著增加。  
  缓解：先 dry-run 与最小主窗口，不并行跑三窗口全量；记录运行耗时。

## Migration / Rollback

- 回退方式：删除 `HS300_ZZ500_CSI1000` mode、study YAML、generated script 和相关测试。
- 正式 baseline 与已有 `HS300_ZZ500`、`CSI1000` mode 不迁移、不改名、不重写历史产物。

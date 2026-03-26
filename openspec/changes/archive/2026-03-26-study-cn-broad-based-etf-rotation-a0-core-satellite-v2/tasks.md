## 1. 方案固化

- [x] 1.1 固化 A0 V2 对照组与 AB 矩阵：以 `A0_GEM_TOP2_BOND` 为控制组，定义 `NONE / CSI1000_PROXY_ONLY / DIVIDEND_PROXY_ONLY / FULL_STANDARD_SWAP` 四种替换模式。DoD：proposal/design/specs 与 study 命名一致。验证：`openspec validate`。风险：控制组口径漂移会让后续结果无法对照。
- [x] 1.2 固化槽位边界：明确 `core_slot` 只从宽基/红利/中证1000位选 1 个，`growth_slot` 只从成长位选 1 个。DoD：spec 中有独立 requirement。验证：spec 检查。风险：若边界不清，仍会退回自由 Top2。

## 2. 研究入口与配置链

- [x] 2.1 在研究入口新增 A0 V2 study，保留月频、`MA200 + 12M>0`、`12M/6M/3M`、`511010` fallback 骨架。DoD：新增 `research/studies/etf/*a0*core*satellite*v2*.study.yaml`。验证：`study_run --dry-run`。风险：若同时修改多个规则变量，结果不可归因。
- [x] 2.2 接通 `proxy_replacement_mode` 与 formal replacement pairs 配置编译链。DoD：运行时配置可看到替换模式与替换对。验证：`run_meta.json`。风险：前后端字段漂移。

## 3. Provider 与审计

- [x] 3.1 在 ETF provider 中实现核心槽位 + 成长槽位的独立选择与 reason codes。DoD：`portfolio_daily` / `audit` 可看到两个槽位的选择结果。验证：单测 + 产物抽样。风险：槽位逻辑和旧自由 Top2 混淆。
- [x] 3.2 扩展 Governor / research audit，输出槽位目标暴露、实际暴露和槽位级 under-deploy 原因。DoD：`audit.json`、`run_meta.json` 有最小槽位证据链。验证：单测 + artifact 检查。风险：只输出总暴露会导致问题继续不可解释。

## 4. 实验与结论

- [x] 4.1 运行 A0 V2 最小 AB，并在共同窗口下和 A0 胜出版对照。DoD：生成 `variant_compare.csv` 与 `summary.json`。验证：研究脚本成功完成。风险：直接跨不同覆盖窗口硬比会误导结论。
- [x] 4.2 给出是否值得继续推进的正式结论。DoD：`implementation_notes.md` 写清冠军、对照、风险与回退。验证：人工审阅。风险：把短窗口偶然结果误判成正式主线。

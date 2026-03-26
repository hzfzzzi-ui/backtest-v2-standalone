## 1. 模板定义与研究入口
- [x] 1.1 固化模板 A 的 A0/A1 资产池与角色映射
  DoD：形成可复用的模板定义，明确当前可直跑资产、标准目标资产、proxy 标记与成长位二选一规则。
  验证：模板配置与 research audit 中能显式输出 A0/A1 role map、proxy map、growth seat。
  风险：把代理资产静默写成正式标准池。
- [x] 1.2 新增模板 A 的研究入口与预设
  DoD：形成 A0 直跑 study preset，并为 A1 保留显式待补资产入口。
  验证：`research/studies/etf/cn_broad_based_rotation_template_a.study.yaml` 可被 dry-run 和正式 study 运行。
  风险：入口定义与现有 `cn_etf` preset 语义冲突。

## 2. 规则骨架与最小 AB
- [x] 2.1 实现月频 `Top2` 宽基轮动基础版
  DoD：支持 `12M/6M/3M` 评分、`MA200 + 12M>0` 过滤、`Top2` 等权。
  验证：provider 单测与 `audit.json` 都能看到评分窗口、绝对过滤与选中结果。
  风险：规则实现回落成当前 ETF V1 的短窗口逻辑。
- [x] 2.2 跑成长位对照 `159915` vs `588000`
  DoD：其余条件不变，仅比较成长位差异。
  验证：`outputs/ops/study_cn_broad_based_etf_rotation_template_a_20260326/variant_compare.csv` 有对照结果。
  风险：混入其他变量导致结果不可归因。
- [x] 2.3 跑组合构建对照 `Top1` vs `Top2`
  DoD：其余条件不变，仅比较持仓数差异。
  验证：对比表能看到持仓连续性、换手、回撤与收益差异。
  风险：混入 fallback 或成长位变更。
- [x] 2.4 跑 fallback 对照 `cash` vs `511010`
  DoD：其余条件不变，仅比较 fallback 语义。
  验证：产物能证明 fallback 使用情况与绩效差异。
  风险：把 fallback 误升级成正式防守层。

## 3. 审计与结论收口
- [x] 3.1 补模板 A 的最小 research audit 证据
  DoD：audit 至少能回答 role map、proxy 使用、评分来源、绝对过滤、fallback 使用与未部署原因。
  验证：`audit.json` 的 `research_audit.gates.etf_beta_sleeve.evidence` 出现对应字段。
  风险：结果变化了但无法证明规则真的生效。
- [x] 3.2 形成模板 A 首轮结论
  DoD：输出主开发窗口 compare/summary，明确 A0 当前最优组合与是否值得进入下一轮正式推进。
  验证：`outputs/ops/study_cn_broad_based_etf_rotation_template_a_20260326/variant_compare.csv` 与 `summary.json` 已落盘。
  风险：只给收益，不给部署、风险和审计结论。
- [x] 3.3 明确 A1 后续接入条件
  DoD：列出标准中证1000 / 红利 ETF 补齐后才能做的正式对照步骤。
  验证：`implementation_notes.md` 与 `summary.json` 明确 A1 触发条件。
  风险：A0 和 A1 边界再次混淆。

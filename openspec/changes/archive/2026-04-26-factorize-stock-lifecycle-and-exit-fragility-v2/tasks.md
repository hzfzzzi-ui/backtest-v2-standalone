## 1. Catalog 与 snapshot 合同

- [x] 1.1 新增 stock lifecycle fragility catalog，并把研究对象按 `early fade / weak carry / break-floor / exit-conditional` 分组；DoD: catalog 可被研究层加载并返回完整元数据；验证: 新增对应单测；风险: 与第一批 fragility、Risk Gate 边界重叠。
- [x] 1.2 新增 lifecycle fragility factor snapshot 与 factor score snapshot 输出；DoD: 快照包含 baseline lineage、availability 和组合分数信息；验证: 对 snapshot schema 做单测；风险: 持有期语义与 as-of 对齐错误。

## 2. Study surface

- [x] 2.1 新增 stock lifecycle fragility study runner 入口；DoD: `study_run` 可识别新的 lifecycle 研究类型；验证: 新增 study runner 单测；风险: 与现有 factor study surface 命名冲突。
- [x] 2.2 新增 real mainline 三窗口 study 定义；DoD: 可对当前股票腿基线跑出 `1217 / 1222 / 1226` 三窗口研究输出；验证: `stock_lifecycle_fragility_real_mainline_s1.study.yaml` 与三窗口 `analysis.json` 已落地；风险: 窗口口径与当前主线锚点不一致。

## 3. 结果审计

- [x] 3.1 生成 machine 分析输出，覆盖失败风险 bucket、退出条件分布或 veto 改善指标；DoD: 每个窗口至少产出一份可读 `analysis.json`；验证: 三窗口 `analysis.json` 已落地；风险: 结果字段不足以解释生命周期机制。
- [x] 3.2 回填 change notes 与研究结论边界；DoD: notes 说明哪些结果仅为解释层、哪些值得进入下一轮研究；验证: 已补齐 `notes.md`；风险: 把研究结论误写成策略有效结论。

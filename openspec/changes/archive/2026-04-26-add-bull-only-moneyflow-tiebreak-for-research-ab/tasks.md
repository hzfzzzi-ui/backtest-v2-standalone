## 1. Runtime 接入

- [x] 1.1 在候选计划层增加 `bull_only_tiebreak` moneyflow overlay 模式；DoD：仅 `BULL` 日子应用 tiebreak，非 `BULL` 完全退化为 baseline；验证：单测覆盖 `BULL` / 非 `BULL` 分支；风险：状态字段取值口径错误会导致 gating 落空。
- [x] 1.2 补充最小日级诊断字段；DoD：实验产物能区分 overlay 已启用、`BULL` gate 打开、以及非 `BULL` 抑制；验证：集成流最小回归；风险：候选级 reject reason 仍可能不完整。

## 2. 研究验证

- [x] 2.1 基于当前股票腿基线构造 baseline 与 `bull_only_tiebreak` 输入；DoD：仅改 overlay mode 与其所需研究输入，不改主排序/退出；验证：输入 diff 可审计；风险：误混入其他研究改动。
- [x] 2.2 运行严格 A/B 并汇总 `CAGR / Sharpe / MaxDD / Calmar / Trades` 与 overlay 诊断；DoD：形成可引用的实验目录与结果摘要；验证：实验结果文件存在且可读取；风险：若 overlay 作用面过小，可能出现假阴性。

## 3. 收口

- [x] 3.1 回填 tasks/notes，总结这版接法是否成立；DoD：tasks 全部完成并写清风险与回退；验证：`openspec status --change` 为 complete；风险：把“接法失败”误写成“因子失效”。

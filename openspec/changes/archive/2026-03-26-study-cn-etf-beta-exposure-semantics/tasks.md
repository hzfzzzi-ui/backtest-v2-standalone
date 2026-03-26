## 1. 研究合同收敛

- [x] 1.1 固化 ETF 暴露语义研究输入合同：新增或收敛 `target_exposure`、`min_deployable_exposure`、deployability 研究参数。DoD：proposal/design/spec 对齐且字段边界唯一；验证：`openspec validate --strict`；风险：字段命名再次漂移。
- [x] 1.2 固化 ETF 暴露语义研究输出合同：明确 target vs actual 暴露、deployability gap、under-deploy reason 摘要。DoD：相关 delta spec 完整；验证：spec 审核可直接映射到 run_meta/audit；风险：输出过散导致前后端再次各自解释。

## 2. Governor 暴露语义实现

- [x] 2.1 为 `cn_etf_beta` 增加显式目标暴露与最小可部署暴露输出。DoD：Governor snapshot 与日级产物能同时看到这两个字段；验证：单测 + 产物断言；风险：误影响个股 alpha sleeve。
- [x] 2.2 为 `cn_etf_beta` 增加 deployability gap 与 under-deploy 归因。DoD：能区分预算上限、slot、绝对过滤、fallback；验证：单测 + `portfolio_daily.csv` 样本；风险：reason code 语义不稳定。

## 3. ETF Sleeve 与审计接入

- [x] 3.1 让 ETF sleeve 输出理论暴露、实际暴露和 fallback 暴露组成。DoD：`run_meta` 与 `audit` 可同时读取；验证：研究 smoke + 产物检查；风险：fallback 被错误记入正式 defense 语义。
- [x] 3.2 扩展 research audit，把 ETF 部署质量纳入正式 gate。DoD：审计输出平均暴露、有持仓日暴露、under-deploy 原因和 fallback 摘要；验证：单测 + 研究实验；风险：审计结论与真实仓位不一致。

## 4. 最小 AB 研究

- [x] 4.1 固定当前 ETF 主候选池，建立暴露语义控制组。DoD：控制组不改候选池、不改主规则族；验证：研究定义文件与基线对照；风险：混入其他变量。
- [x] 4.2 比较更合理的 `target_exposure` 与 `min_deployable_exposure`。DoD：至少一组固定暴露候选与一组状态分段候选；验证：实验 compare/summary；风险：结果仍然无法归因。
- [x] 4.3 汇总损失拆解：预算上限、空仓/低仓、fallback、过滤/切换。DoD：生成正式 summary/compare；验证：ops 产物存在且可读；风险：拆解方法与实际执行错位。

## 5. 结论与回退

- [x] 5.1 给出是否值得继续推进 ETF 暴露语义的正式结论。DoD：implementation notes 写清继续/不继续；验证：人工审阅；风险：结论只看收益忽视部署质量。
- [x] 5.2 明确回退路径。DoD：列出受影响文件与回退顺序；验证：implementation notes 完整；风险：后续归档前无法安全回撤。

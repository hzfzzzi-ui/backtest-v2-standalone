## 1. 配置与信号接线

- [ ] 1.1 为 `breakout_trend` 增加默认关闭的 pullback / alpha_ranking 参数，并通过 registry 接入运行时（DoD：未启用时 baseline 结果不变；验证：baseline 单跑配置与结果不漂移；风险：默认值误伤现有 breakout 行为）
- [ ] 1.2 在 `BreakoutTrendProvider` 中实现 `PB1/PB2/PB3` 三个 pullback 变体，并为候选写入 `alpha_source`（DoD：候选可区分 breakout/pullback 来源；验证：`candidate_signals.csv` 样本中能看到不同 `alpha_source`；风险：局部高点/rolling 对齐出错）

## 2. 排序与 PIT 审计

- [ ] 2.1 实现 residual strength 分数并复用现有排序入口完成 Phase 2（DoD：显式启用 residual ranking 后排序结果与分数字段可追溯；验证：`score_diagnostics.csv` 存在 residual 字段；风险：横截面样本混入非候选或未来数据）
- [ ] 2.2 新增 PIT 行业映射加载，并在此基础上实现 `sector_strength_score` 与 `volume_price_quality_score`（DoD：Phase 3 可输出行业/量价质量分数且行业映射按交易日生效；验证：缺失行业时字段为空而非错误回填；风险：行业历史查询成本和穿越风险）
- [ ] 2.3 组合 `final_score` 并支持 3 组小范围权重方案（DoD：`final_score` 可由 residual/sector/quality 组合得到；验证：三组权重都能跑通且写入产物；风险：多处重复实现导致排序与产物不一致）

## 3. 产物与可观测性

- [ ] 3.1 扩展 `candidate_audit` / `portfolio_candidates.csv`，并新增 `candidate_signals.csv`、`alpha_funnel.csv`、`score_diagnostics.csv`（DoD：运行后产物齐全；验证：字段包含用户要求的核心分数与选中标记；风险：fast_mode 下日志被静默裁掉）
- [ ] 3.2 输出 `orders.csv` 并把新增调试产物接入 artifacts/stabilize（DoD：`orders.csv`、`run_meta.json`、manifest 能发现这些文件；验证：计划单可与 trades 对照；风险：订单记录口径与实际成交语义不一致）

## 4. 研究实验与结论

- [ ] 4.1 新增三阶段最小实验脚本，依次运行 baseline、phase1、phase2、phase3，并补充 PB1/PB2/PB3 对照（DoD：脚本一次运行生成所有实验与 `ab_summary.csv`；验证：产物中含对应 `exp_id`；风险：实验矩阵过大拖慢运行）
- [ ] 4.2 完成无未来函数 / 无数据偏移审计与最终研发报告（DoD：报告明确区分事实与推断，并回答哪类增强贡献最大；验证：包含审计清单、三阶段对比、继续/停止建议；风险：只看 headline metrics 忽略回撤或仓位利用率）

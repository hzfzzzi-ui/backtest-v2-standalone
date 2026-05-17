## 1. 规格与静态审计

- [x] 1.1 创建 OpenSpec change，明确 L3 研究边界、禁止事项和三窗口验收。
- [x] 1.2 生成当前 99 ETF 池分类审计，输出跨境剔除、国内 beta、风格/Smart Beta、行业主题、防守仓清单。
- [x] 1.3 将分类审计写入本轮研究目录，作为后续实验输入依据。

## 2. 最小研究配置

- [x] 2.1 新增 research-only ETF study variant：`DOMESTIC_POOL_BASE`，只剔除跨境 ETF，其他参数尽量继承 V2。
- [ ] 2.2 新增 research-only ETF study variant：`DOMESTIC_DEFENSE_TIGHT`，只调整 `TRANS_DOWN / RISK_OFF` 的 ETF 暴露与防守权重。
- [x] 2.3 新增 stock+ETF combo study variant，固定 stock leg，只替换 ETF source。

## 3. 主窗口实验

- [x] 3.1 在 Docker 内运行 `2016-2026` 主窗口，先跑 `DOMESTIC_POOL_BASE`。
- [ ] 3.2 若结果可解释，再跑 `DOMESTIC_DEFENSE_TIGHT`。
- [ ] 3.3 输出主窗口回撤归因：stock leg、ETF leg、combo allocator。

## 4. 硬门槛与全周期

- [ ] 4.1 运行 `2012-2017` 硬门槛窗口。
- [ ] 4.2 运行 `2012-2026` 全周期审计窗口。
- [ ] 4.3 与 `CN_STOCK_ETF_COMBO_BASELINE_V2` 和 `CN_STOCK_ETF_FORMAL_V1` 对比。

## 5. 结论

- [ ] 5.1 输出是否建议升级为 V2.1 candidate。
- [ ] 5.2 若不建议升级，明确失败原因：收益坍塌、回撤未改善、弱状态暴露不可解释或硬门槛失败。
- [ ] 5.3 若建议继续，给出下一轮只允许的一个主改动。

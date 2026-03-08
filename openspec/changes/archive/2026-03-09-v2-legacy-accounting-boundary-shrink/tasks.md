## 1. Fill accounting split

- [x] 1.1 抽出 `fill_accounting.py`，承接开盘成交、现金/仓位/均价更新和 trade row 组装；DoD：`legacy_adapter.py` 不再直接内嵌买卖成交实现；验证：聚焦单测覆盖买卖成交路径；风险：mutation 顺序变化导致 T+1 成交口径漂移。
- [x] 1.2 为 fill accounting 增加聚焦测试；DoD：覆盖 SELL 清仓、BUY 加仓、provider side-effect 清理和 trade row 字段；验证：定向 harness 或单测通过；风险：测试夹具过度简化，漏掉 provider 状态更新。

## 2. Daily snapshot and result bridge split

- [x] 2.1 抽出 `daily_accounting.py`，承接 NAV snapshot、turnover/exposure、top holdings 和 daily row 组装；DoD：`ensure_day(...)` 只保留时序组织和 helper 委托；验证：聚焦单测比较 daily row 关键字段；风险：`prev_nav/peak_nav/_traded_value_today` 更新时点漂移。
- [x] 2.2 抽出 `result_bridge.py`，承接 DataFrame 组装、`_compute_metrics(...)` 桥接和 metrics augment；DoD：`to_backtest_result()` 只保留委托；验证：定向测试比较 `PortfolioBacktestResult.metrics` 关键字段；风险：metrics 类型或缺省字段变化。
- [x] 2.3 更新 `legacy_adapter.py` 冻结边界；DoD：adapter 仅保留编排、route/day-control 和 helper 调用；验证：代码审阅和冻结文档一致；风险：残余 helper 责任继续长回单体文件。

## 3. Verification and freeze

- [x] 3.1 运行 accounting 相关聚焦测试与 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`；DoD：锁定基线 `exp_20260308_021045840_cde0` 的核心产物继续 `PASS`；验证：baseline compare 输出；风险：出现隐蔽的 daily/perf 口径漂移。
- [x] 3.2 补充收敛冻结文档，明确 accounting、daily snapshot、result bridge 的新归属和 `legacy_adapter.py` 的剩余责任；DoD：文档可直接作为下一条 change 的边界输入；验证：文档落盘并与实现一致；风险：冻结范围定义不清，后续又往 adapter 回填逻辑。

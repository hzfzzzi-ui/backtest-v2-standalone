## 1. 报告口径合同与数据来源收敛

- [x] 1.1 在 `backend/core/report/report_generator.py` 落地“字段来源优先级合同”（区间/基准/Universe/绩效/漏斗）；DoD: 同一 `exp_id` 的 `report.html` 与 `run_config/perf/funnel` 对齐；验证: 对 `exp_20260306_211811` 重生成并逐项比对；风险: 历史实验缺失产物导致字段为空。
- [x] 1.2 在 `backend/api/endpoints/backtest_v2_artifacts.py` 修正 `run_meta.data.start/end/benchmark` 来源为最终运行配置；DoD: `run_meta.data` 与 `run_config.universe` 一致；验证: 新跑实验检查两个文件字段相同；风险: 旧逻辑依赖 `overrides` 的调用方可能出现行为变化。
- [x] 1.3 在 `run_meta` 增加报告关键字段来源标记与 fallback 触发标记；DoD: `run_meta.json` 可见来源与冲突策略；验证: 构造冲突请求（`config_id`+`workbench_config`）并检查标记存在；风险: 字段命名不规范引发后续消费歧义。

## 2. 服务端报告可读性与策略摘要修复

- [x] 2.1 清理 `report_generator.py` 中乱码中文常量并统一 UTF-8 可读文案；DoD: 报告标题/章节/表头无乱码；验证: 打开 `/api/backtest_v2/experiments/{exp_id}/report` 人工检查 + 关键字符串断言；风险: 批量替换引入个别文案遗漏。
- [x] 2.2 修复 BREAKOUT 策略摘要映射（展示 breakout_window/entry_confirm_mode/entry_delay_mode/portfolio_mode）；DoD: BREAKOUT 报告不再显示 MA 快慢线为主参数；验证: 读取冠军配置实验报告确认字段；风险: 其他策略分支回归。
- [x] 2.3 统一漏斗指标优先级（`funnel.csv` > `run_meta.counters`）；DoD: 报告漏斗与 `funnel.csv` 一致；验证: 对存在冲突样本比较两者并确认采用 `funnel.csv`；风险: 无 `funnel.csv` 时 fallback 显示解释不充分。

## 3. 前端报告映射对齐

- [x] 3.1 在 `frontend/assets/js/report.js` 对齐与服务端相同的字段优先级合同；DoD: 前端生成报告与后端 `report.html` 关键字段一致；验证: 同一 `exp_id` 对比两份报告的区间/标的数量/CAGR-Sharpe-MDD；风险: 双端逻辑再次分叉。
- [x] 3.2 为前端报告增加最小来源诊断展示（或调试字段）以支持复核；DoD: 出现冲突时可在页面或导出内容看到来源信息；验证: 冲突请求样本中来源可见；风险: UI 文案过多影响可读性。

## 4. 回归验证与文档沉淀

- [x] 4.1 编写回归检查脚本/用例，覆盖“区间一致、Universe 一致、绩效一致、漏斗一致”；DoD: 至少覆盖 2 个历史问题实验与 1 个新实验；验证: 自动化输出 pass/fail 清单；风险: 旧实验产物不完整导致误报。
- [x] 4.2 更新本次 change 说明文档，明确口径修复生效时间与 legacy 差异；DoD: 文档包含迁移说明、验证步骤、已知限制；验证: 文档可直接指导人工复验；风险: 文档与实现偏离。
- [x] 4.3 产出最终验收记录（字段对齐对照表 + 示例 exp_id）；DoD: 提供可追溯的验收附件；验证: 用户可按 exp_id 复查；风险: 验收样本代表性不足。

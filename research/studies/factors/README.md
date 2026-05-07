# Factors Studies

当前 `research/studies/factors/` 不应再被理解成“所有文件都平级的因子池”，而应按**研究角色**理解。

## 1. 正式 factor surface 研究

这类 study 对应 `backend/research/*_catalog.py + *_snapshots.py + *_study.py` 三件套，属于当前正式研究面。

### 1.1 正向选股 / 排序增强

- `stock_alpha_factor_real_mainline_s1.study.yaml`
- `moneyflow_factor_real_mainline_s1.study.yaml`
- `positive_quality_factor_real_mainline_s1.study.yaml`
- `industry_second_stage_factor_real_mainline_s1.study.yaml`

### 1.2 风险门 / 负向上下文

- `negative_conditional_context_real_mainline_s1.study.yaml`
- `risk_gate_factor_real_mainline_s1.study.yaml`
- `execution_pressure_factor_real_mainline_s1.study.yaml`

### 1.3 持有期 / 退出脆弱性

- `exit_fragility_factor_real_mainline_s1.study.yaml`
- `stock_lifecycle_fragility_real_mainline_s1.study.yaml`

### 1.4 元层组合

- `final_score_composition_real_mainline_s1.study.yaml`

## 2. Demo / 研究入口示例

这类 study 不是正式主研究锚点，只是 surface 接口是否可跑通的最小入口。

- `stock_alpha_factor_surface_demo.study.yaml`
- `moneyflow_factor_surface_demo.study.yaml`

规则：

- demo 只用于最小样本、最小窗口、最小符号集验证
- demo 结果不能直接引用为正式研究结论
- 后续若继续增 demo，命名统一为 `<theme>_surface_demo.study.yaml`

## 3. 历史单题研究

这类 study 仍在主目录，但角色上不属于当前“成体系 factor surface”。

- `a_share_moneyflow_divergence_min10.study.yaml`

它本质上是旧式“单题研究脚本 study”，不是按 `catalog/snapshots/study` 三件套组织的正式 factor family。

后续方向：

- 若保留：应明确降级为 legacy one-off study
- 若已有 surface 替代：应优先归档，而不是继续和正式 factor surface 并列

## 4. 研究总结文档

- `2026-04-12_stock_sleeve_factor_research_summary.md`

这类文件只承载结论，不是可执行 study。

## 5. 当前推荐理解方式

不要再按文件名逐个理解，而按下面四类看：

- `alpha / quality / industry / moneyflow`：正向研究面
- `risk_gate / negative_context / execution_pressure`：风险与否决研究面
- `exit_fragility / lifecycle_fragility`：持有期和退出研究面
- `final_score_composition`：元层组合研究面

## 6. 命名规则

### 6.1 正式研究面

统一使用：

- `<theme>_real_mainline_sN.study.yaml`

含义：

- `theme`：研究主题
- `real_mainline`：基于当前正式真实样本或正式主线派生样本
- `sN`：该主题的研究序列号

### 6.2 Demo

统一使用：

- `<theme>_surface_demo.study.yaml`

### 6.3 总结

统一使用：

- `<date>_<topic>_summary.md`

## 7. 后续清理原则

- 不再新增平级“单题 study”，优先挂到已有 factor surface family 下
- 若一个主题已经有 `*_real_mainline_s1.study.yaml`，就不要再在同目录新增另一份语义重复的 study
- `demo`、`legacy one-off`、`summary` 不能和正式 factor surface 在语义上混用

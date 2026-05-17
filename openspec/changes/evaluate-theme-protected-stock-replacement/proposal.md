## Why

上一轮 V3 行业/主题归因和 B0.1 保护规则已经证明“主题错位 + 现金不足”有可研究空间，但目前证据仍停留在临时 shadow 产物里，不能作为正式 study 被前端、registry 和研究日志稳定追踪。

本变更把 B0.1 保护替换纪律固化为 research-only formal study：先正式审计触发频率、保护规则命中、三窗口覆盖和证据链，再决定是否进入真实 B1 回测实现。

## What Changes

- 新增 `cn_stock_etf/cn_stock_etf_theme_protected_replacement_v1` study 定义。
- 新增 research-only runner，用 V3 行业/主题归因产物作为输入，重新汇总 B0.1 保护替换证据。
- 输出机器可读摘要、人工可读报告、study conclusion registry 记录和 study journal round。
- 明确该 study 不成交、不重算 NAV、不修改 baseline、不改股票池、不改排序主因子、不改 ETF 腿。
- 对 `1626`、`1217`、`1226` 和现代诊断窗口分别给出结论；其中早期窗口必须标注 ETF 主题代理覆盖不足风险。

## Capabilities

### New Capabilities

- `cn-stock-etf-theme-protected-replacement-study`: 受研究纪律约束地评估 stock 腿主题保护替换 shadow 规则，并把结果接入 study runner、conclusion registry 和前端研究日志。

### Modified Capabilities

- 无。

## Impact

- 影响范围：
  - `backend/research/theme_protected_replacement_study.py`
  - `backend/research/study_runner.py`
  - `research/studies/cn_stock_etf/cn_stock_etf_theme_protected_replacement_v1.study.yaml`
  - `research/study_journal/rounds/*`
  - `tests/unit/*`
  - `openspec/changes/evaluate-theme-protected-stock-replacement/*`
- 不影响范围：
  - `CN_STOCK_ETF_COMBO_BASELINE_V3`
  - `baseline_V10.1`
  - 真实回测 runtime、信号时点、成交时点、排序主因子、股票池、ETF 池、组合权重和防守仓定义。

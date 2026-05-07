# Baseline 当前状态摘要

## 当前结论

- `baseline_V10.1` 是当前正式主线 baseline
- `A_STOCK_ETF_V1` 是当前已验证的 replay anchor
- baseline 回放必须先解析为唯一 `execution_contract`
- `component_source_contract` 只保留为来源说明，不再是统一组合的正式执行真相
- 已废弃组合源字段不再作为主合同
- 历史实验产物只能作为审计参考，不得回写为主路径定义

## 当前验收锚点

- 最小正式回归通过
- 生产同环境 replay 锁定到当前验证结果
- baseline 与 unified combo 的主路径口径一致

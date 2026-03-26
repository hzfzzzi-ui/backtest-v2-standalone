## 1. 规则与配置收敛
- [x] 1.1 固定 ETF 稳定器 V2 的正式主候选池，只使用 `510300/510050`，并把 `511010` 标记为 fallback 研究资产。
- [x] 1.2 调整 ETF 稳定器 V2 的默认并持语义，支持 `max_selected_symbols = 2`，并在产物中显式暴露目标并持数量与未部署原因。

## 2. Governor 预算语义
- [x] 2.1 为 ETF 稳定器 V2 增加独立部署语义：`target_exposure`、`min_deployable_exposure`、`fallback_allowed`、`under_deploy_reason_codes`。
- [x] 2.2 让 ETF 研究入口与审计产物能够解释 `RISK_ON / NEUTRAL` 下的 ETF 实际暴露，不再只留下“长期平均接近不部署”的黑箱结果。

## 3. fallback 与部署证据
- [x] 3.1 实现 ETF 稳定器 V2 的正式 fallback 口径，支持 `cash` 对照和 `511010` fallback，并在 orders/run_meta/audit 中显式区分。
- [x] 3.2 为 ETF 稳定器输出实际部署指标：平均实际暴露、有持仓日平均暴露、持仓天数、fallback 使用情况、under-deploy 主因摘要。

## 4. 最小 AB
- [x] 4.1 跑完 ETF 稳定器 V2 最小 AB：`cash fallback` vs `511010 fallback`，以及 `max_selected_symbols = 1` vs `2`。
- [x] 4.2 与当前正式 ETF 对照组 `DM_BASIC_CASH_MA120` 做统一 compare，回答收益差是否主要由部署不足导致。

## 5. 收口结论
- [x] 5.1 形成 ETF 稳定器 V2 统一结论，输出 compare 表和 summary。
- [x] 5.2 明确回退与不推进口径：若 V2 仍不值得推进，记录弃用理由与回退文件列表。

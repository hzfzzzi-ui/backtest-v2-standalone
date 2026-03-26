## 1. Selector 与配置入口
- [x] 1.1 新增 `cn_etf_beta` 的最小 selector/provider 路径
  DoD: `asset_scope=cn_etf` 不再复用股票 breakout 候选
  验证: route/provider 定向单测通过
  风险: 误伤股票主线
- [x] 1.2 定义 ETF beta 的周频调仓、绝对过滤和相对强弱最小规则
  DoD: 正式候选池、排序和调仓日逻辑可独立运行
  验证: selector 单测与 debug 断言通过
  风险: 规则过严仍然无交易

## 2. Governor 与可观测性
- [x] 2.1 为 `cn_etf_beta` 接入独立 deployability map
  DoD: 五状态下 ETF beta 的 slot cap/预算不再复用股票 `trade_mode`
  验证: Governor 定向测试通过，日级 `governor_budget_json` 与 `run_meta/audit` 真值一致
  风险: 预算映射与 stock alpha 语义冲突
- [x] 2.2 补齐 ETF beta 的 reason codes 和诊断字段
  DoD: `run_meta/audit/reason_codes` 能解释无仓位和选中原因
  验证: 产物断言与 smoke 产物核对通过
  风险: 字段多但解释不闭环

## 3. Research Audit 与 Smoke
- [x] 3.1 为 `research_audit` 增加 ETF beta 最小可交易 smoke gate
  DoD: 路径真值、解释链和非零交易证据被统一评估
  验证: `research_audit` 定向单测通过
  风险: gate 过严导致 Phase 1 长期红灯
- [x] 3.2 重跑 `etf/cn_etf_first_wave_core` 的 `1626` smoke
  DoD: `orders > 0`、`trades > 0` 且 ETF 相关 gate 通过
  验证: 新 experiment `exp_20260325_033455780_6f37`
  风险: 若仍为 `0 trades`，则 change 不得宣告完成

## 4. 回归与收口
- [x] 4.1 跑定向单测和 change 校验
  DoD: 相关 `pytest` 与 `openspec validate` 通过
  验证: 命令输出留存
  风险: ETF route 牵连既有主线 contract
- [x] 4.2 close-out 说明受影响文件、风险、验证和回退路径
  DoD: 结论能区分“路径打通”和“策略可交易”
  验证: 本轮 close-out 明确说明 smoke 已有成交，但策略表现仍仅属 Phase 1
  风险: 把路径通过误写成策略有效

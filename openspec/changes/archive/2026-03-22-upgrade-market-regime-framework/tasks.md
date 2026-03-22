## 1. 合同与配置链

- [x] 1.1 定义 `regime_engine` 配置枚举与前后端透传链；DoD：semantic config、runtime config、run_meta 都能区分 `ma200_legacy` 与 `market_regime_framework`；验证：编译链单测 + `run_meta.json` 快照；风险：字段漂移导致前后端口径不一致
- [x] 1.2 定义正式 regime framework 的参数 schema（趋势/风险/广度/参与度/persistence/fallback）；DoD：配置可完整序列化与反序列化；验证：配置 round-trip 测试；风险：参数分层不清导致后续实现无法归因
- [x] 1.3 定义 fallback 行为与 `feature_availability` 合同；DoD：特征不足时可明确进入 `ma200_legacy` 或停用并产出原因；验证：缺特征场景单测；风险：静默回退掩盖真实数据问题

## 2. 后端状态机与路由

- [x] 2.1 抽象正式 regime engine 输入接口，支持趋势/风险/广度/参与度四类特征；DoD：precompute 阶段可接入多因子特征而非单一 MA200；验证：特征装配单测；风险：与现有向量化矩阵接口耦合过深
- [x] 2.2 实现状态、置信度、持续天数与切换原因输出；DoD：`market_state`、`regime_confidence`、`regime_duration_bars`、`regime_transition_reason` 可随日度输出；验证：provider 单测 + 产物样本；风险：状态抖动或切换原因不可解释
- [x] 2.3 让 RegimeRouter 消费正式 regime 输出并保留 legacy 兼容；DoD：`trade_mode` 由状态、置信度和 persistence 联合生成；验证：router 回归测试；风险：打破现有 `baseline_V10.1` 路由行为

## 3. 审计与产物协议

- [x] 3.1 扩展 `portfolio_daily.csv` 与诊断产物字段；DoD：daily 行含正式 regime 字段，统计层含状态天数、切换次数、低置信度占比；验证：artifact golden 或 CSV 断言；风险：产物字段增加导致旧前端兼容问题
- [x] 3.2 输出最小 regime 审计报表；DoD：至少能回答“为什么今天是这个状态、为什么切换”；验证：生成样例 report/debug CSV；风险：输出过重影响运行性能
- [x] 3.3 建立新旧状态机对照回归脚本；DoD：可在三窗口下比较 `ma200_legacy` 与新框架的状态分布和切换差异；验证：研究脚本可复现运行；风险：对照口径不一致导致结论失真

## 4. 前端展示与工作台

- [x] 4.1 更新结果图蒙版与图例以识别正式框架/legacy；DoD：结果图能展示颜色语义、framework 类型与状态图例；验证：前端截图/人工验收；风险：展示层自行推导状态造成第二真相源
- [x] 4.2 更新配置工作台 regime 面板；DoD：UI 能选择 `regime_engine`，并按输入块展示正式框架参数；验证：前端配置 round-trip；风险：旧实验加载失败
- [x] 4.3 保持旧实验兼容显示；DoD：旧 `baseline_V10.1` 与现有实验仍可正常加载并显示 legacy 标签；验证：手工加载旧实验；风险：默认入口被新框架破坏

## 5. 回归验证与切换准备

- [x] 5.1 在 `2016-2026` 主开发窗口完成新旧框架对照；DoD：输出收益、回撤、状态分布、切换次数和关键差异样本；验证：正式对照页；风险：单窗口结论误导主线决策
- [x] 5.2 在 `2007-2017` 与 `2007-2026` 完成门槛窗口审计；DoD：三窗口结果完整且可复现；验证：三窗口报告；风险：只在主开发窗口表现好
- [x] 5.3 输出切换建议与回退方案；DoD：明确何时继续使用 `ma200_legacy`、何时可试运行新框架；验证：最终审计报告与回退文档；风险：过早替换正式主线

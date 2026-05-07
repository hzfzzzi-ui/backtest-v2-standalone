## 1. ETF 正式合同收敛

- [x] 1.1 在 `etf_beta_contract.py` 中拆出 ETF `formal view / research view` 生成路径（DoD：正式视图只保留最终目标与正式摘要；验证：新增/更新单测覆盖正式字段白名单；风险：误删当前正式依赖字段）
- [x] 1.2 在 `cn_etf_beta_signal_provider.py` 中改为只向共享执行链透传 ETF 正式视图，并把预算/节奏/缺口字段下沉到研究视图（DoD：共享执行输入不再依赖 ETF 研究字段；验证：provider 合同回归与执行合同回归通过；风险：运行时元数据消费方断裂）

## 2. 正式审计与研究诊断分层

- [x] 2.1 更新 `daily_accounting.py`，只把 ETF 正式摘要写入正式日表与正式审计真相（DoD：正式产物不再保留 ETF 研究中间字段；验证：正式 audit/portfolio daily 合同测试通过；风险：历史报表字段兼容性变化）
- [x] 2.2 更新 `research_audit.py`，改为只消费 ETF 研究视图解释预算、节奏和缺口，不再把历史 `sleeve_budget` 或等价别名当正式证据（DoD：ETF 研究解释与正式审计边界清楚；验证：research audit 合同测试通过；风险：旧研究脚本引用字段失效）

## 3. 文档、回归与漂移验证

- [x] 3.1 同步 `docs/02_系统架构设计/全系统架构设计.md` 与 `docs/01_系统接口模块定义/共享层/A股子系统接口模块定义.md` 的 ETF 边界表述（DoD：文档与 change specs 一致；验证：人工核对正式路径/研究路径描述；风险：文档与代码再次脱节）
- [x] 3.2 补齐 ETF 正式合同、正式审计、research audit 和共享运行时边界的回归测试（DoD：新增断言覆盖 formal/research 分层；验证：相关 pytest 通过；风险：遗漏跨模块消费者）
- [x] 3.3 重跑 ETF 正式实验并至少回归一次 `baseline_V10.1`，确认边界收敛不引入共享层漂移（DoD：ETF 产物字段符合新边界且 baseline 无漂移；验证：实验指标与基线锚点对账；风险：边界改动误伤共享执行链）

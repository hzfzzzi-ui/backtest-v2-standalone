## ADDED Requirements

### Requirement: 系统必须按主瓶颈顺序研究宽基ETF独立主线
系统 MUST 将宽基 ETF 独立主线的下一轮正式研究收口为三条主瓶颈：

- `absolute_filter`
- `candidate_pool`
- `selection_chain`

系统 MUST 以顺序化研究方式处理这三条瓶颈，而不是把新的暴露语义、行业 ETF 或个股 alpha 组合变量再次绑入同一轮实验。

#### Scenario: 本轮研究只打三条主瓶颈
- **WHEN** 系统展开宽基 ETF 独立主线的正式 study
- **THEN** study MUST 只围绕 `absolute_filter`、`candidate_pool`、`selection_chain` 三条线展开
- **THEN** study SHALL NOT 同时引入新的 exposure policy family、行业 ETF 或个股 alpha 组合变量

### Requirement: 系统必须保持统一Governor边界不变
在主瓶颈研究期间，系统 MUST 继续消费同一个 Governor/CTA 真相源，并保持当前 Governor 边界语义不变。宽基 ETF 主线本轮 MAY 拥有不同的过滤、入池和选择链路，但 SHALL NOT 通过重新定义 Governor 暴露语义来掩盖主瓶颈。

#### Scenario: 主瓶颈研究不重新定义 Governor
- **WHEN** 用户运行宽基 ETF 主线瓶颈 study
- **THEN** 系统 MUST 维持既有 Governor 边界模式作为控制条件
- **THEN** 系统 SHALL NOT 把新的 target exposure 或 controlled accumulation family 当作本轮主研究变量

### Requirement: 系统必须为每条瓶颈输出可归因的实验矩阵
系统 MUST 为三条主瓶颈分别定义最小 AB 矩阵，并保证每一组实验只改一个主变量。系统 MUST 为每组实验输出统一的 compare 与 summary，以便判断真正的主矛盾位于哪一层。

#### Scenario: 每组实验只改一个主变量
- **WHEN** 系统生成宽基 ETF 主线瓶颈 study 矩阵
- **THEN** `absolute_filter` 组 MUST 固定候选池和选择链路
- **THEN** `candidate_pool` 组 MUST 固定过滤 profile 和选择链路
- **THEN** `selection_chain` 组 MUST 固定过滤 profile 和候选池

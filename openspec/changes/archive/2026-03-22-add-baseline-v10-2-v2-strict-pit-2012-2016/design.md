## Context

`baseline_V10.1` 当前是正式主线，但其正式 baseline 锚点只覆盖 `2016-2026`。用户要求新增 `baseline_V10.2`，并明确约束为：

- 策略同 `V10.1`
- 时间窗口 `2012-01-04 ~ 2016-12-30`
- 数据库使用最新 `V2 canonical`
- 股票池使用 `HS300_ZZ500 + PIT_DYNAMIC`

主引擎当前已经支持：

- `data_source.data_role = v2_canonical`
- `membership_mode = PIT_DYNAMIC`

且 `PIT_DYNAMIC` 在主引擎数据装载链里就是严格历史成员，不需要再引入研究脚本级静态名单回放。

## Goals / Non-Goals

**Goals:**

- 新增一条正式 baseline 版本锚点 `baseline_V10.2`
- 保证它与 `baseline_V10.1` 的唯一区别是窗口和数据底座
- 生成正式 linked experiment，并登记到 baseline 索引
- 提供一条可复现的注册路径，避免手工复制产物

**Non-Goals:**

- 不修改 `V10.1` 策略逻辑
- 不修改风险预算、执行时点、退出逻辑
- 不替换 `baseline_V10.1` 为主线
- 不引入新的研究信号或额外风格过滤

## Decisions

### 决策 1：沿用 `baseline_V10.1` 配置，最小化变更

做法：

- 以 `outputs/baselines/baseline_V10_1/config.json` 作为唯一配置来源
- 仅修改：
  - `universe.start`
  - `universe.end`
  - `data_source.data_role`

原因：

- 用户要求“策略同 10.1”
- 最小化修改能避免把窗口变化和策略变化绑在一起

备选方案：

- 直接新写一份独立配置：会增加字段漂移风险，不采用

### 决策 2：严格历史 PIT 直接复用主引擎的 `PIT_DYNAMIC`

做法：

- `membership_mode` 继续使用 `PIT_DYNAMIC`
- 不再另写研究脚本级 strict PIT 适配层

原因：

- 主引擎 `data_bundle_builder` 中的 `PIT_DYNAMIC` 已经按历史窗口加载 PIT 成员
- 用主引擎正式口径，才能让 baseline 真正可对照

备选方案：

- 用研究脚本构造 strict PIT 名单再喂主引擎：会造成 baseline 和主线运行链分叉，不采用

### 决策 3：新增一支 ops 注册脚本，而不是把一次性操作留在手工命令里

做法：

- 新增一支 `backend/scripts/ops` 脚本
- 负责：
  - 复制 `baseline_V10.1` 配置
  - 写入 `baseline_V10_2` 配置
  - 运行正式 experiment
  - 调用 `baseline_access.write_baseline_record()` 登记 baseline

原因：

- baseline 版本锚点必须可复现
- 手工多步操作难审计，也不利于回滚

备选方案：

- 只手工写 `outputs/baselines`：可复现性差，不采用

## Risks / Trade-offs

- [风险] `v2_canonical` 与 `v1` 底座不同，结果会与历史 `V10.1` 锚点不可直接横比  
  → Mitigation：在产物和 baseline 元数据里明确这是 `V2 canonical` 版本锚点

- [风险] `2012-2016` 上 warmup 后有效起点可能晚于窗口起点  
  → Mitigation：正式记录 `effective_execution_start_date`

- [风险] 如果 `baseline_V10.1` 配置后续再变，`V10.2` 的复现脚本需要保持当下快照  
  → Mitigation：明确以当前 `baseline_V10.1/config.json` 快照为来源，并把生成后的 `config.json` 固化到 `outputs/baselines/baseline_V10_2/`

## Migration Plan

1. 创建 `baseline_V10.2` change 并补齐 specs/tasks
2. 新增 ops 脚本，按 `baseline_V10.1` 快照生成 `baseline_V10.2` 配置
3. 跑正式 experiment
4. 写入 `outputs/baselines/baseline_V10_2/`
5. 更新 baseline 索引
6. 校验前端和 API 列表可见

回退：

- 删除 `outputs/baselines/baseline_V10_2/`
- 从 `outputs/baselines/index.json` 重新写索引
- 保留实验目录但不再作为正式 baseline 引用

## Open Questions

- 无新增开放问题；本轮以当前 `baseline_V10.1` 配置快照为正式来源。

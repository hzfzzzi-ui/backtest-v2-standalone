## Context

当前 unified combo 的入口位于 `runner_config_bundle.py`。它发现 `cn_stock_etf_v1` 后，会把同一个 workbench config 深拷贝两次，再分别关掉 stock/ETF 开关，最终得到 stock sleeve 和 ETF sleeve。这个实现有两个直接问题：

1. stock sleeve 并没有继承正式 `baseline_V10.1` 的 residual ranking、PIT_DYNAMIC 窗口和风险退出口径。
2. ETF sleeve 并没有继承正式 `etf/cn_etf_first_wave_core` study 的窗口、资产池和 stabilizer contract。

因此 unified combo 现在只能代表“research template 50/50 拼接器”，不能代表正式组件组合。当前用户需要的是先把组件来源收敛到正式锚点，再判断 combo 结果。

## Goals / Non-Goals

**Goals:**
- 让 unified combo 的 stock sleeve 固定来自正式 `baseline_V10_1`。
- 让 unified combo 的 ETF sleeve 固定来自正式 `etf/cn_etf_first_wave_core` 的主窗口和 `CORE` variant。
- 保持 unified combo 当前 `research_combo_only` 语义不变。
- 在 compiled plan 与 run_meta 中写明组件来源，便于后续追责和对比。
- 用回归测试锁住“官方组件来源”这条合同。

**Non-Goals:**
- 不把 unified combo 改造成真实多 sleeve Governor 联合执行。
- 不修改 stock 主策略逻辑，不修改 ETF stabilizer 主策略逻辑。
- 不改变当前 combo 的固定 `50/50` 拼接公式。
- 不在这次改动里引入动态配比、再平衡优化或收益优化。

## Decisions

### 1. Stock sleeve 直接从 baseline 记录物化

统一组合的 stock sleeve 将通过 `baseline_access.load_baseline_record("baseline_V10_1")` 读取正式 baseline 快照，并直接使用其中的 `config_json` 作为 semantic config。

原因：
- `baseline_V10.1` 已经是当前正式主线，且窗口已重挂到 `2012-01-04`。
- baseline 记录本身就是官方配置真相，比继续维护一份 unified template stock 副本更稳。

备选方案：
- 继续维护 unified template 的 stock 配置副本。否决，因为会继续漂移。
- 直接读取某个历史 exp 的 `config.json`。否决，因为 exp 不是官方锚点接口。

### 2. ETF sleeve 通过 study definition 物化

统一组合的 ETF sleeve 将通过 `study_loader.load_study_definition("etf/cn_etf_first_wave_core")` 加载 study，再用 `study_runner.build_request_payload(...)` 物化 `CORE` variant 与主窗口对应的 `config_json`。

原因：
- ETF 正式入口已经定义在 study 中，包含窗口、资产池、stabilizer contract 和数据源。
- study 本身比手工拼接 ETF workbench config 更接近正式研究入口真相。

备选方案：
- 直接读取某个 ETF exp 的 `config.json`。否决，因为 exp 仍然是产物，不是官方研究入口。
- 继续从 unified template 深拷贝并修补 ETF 字段。否决，因为会继续漂移。

### 3. 保持 combo 为 research-only，但显式暴露组件来源

本次不改 unified combo 的 `50/50` 固定拼接公式，也不把其升级为正式多 sleeve 运行。相反，系统会继续把它标成 `research_combo_only`，同时新增 `component_source_mode=official_sleeve_anchors` 等元数据。

原因：
- 这次任务的目标是先解决“组件来源错误”，不是顺手重写组合执行合同。
- 先保留拼接语义，才能清晰比较“错误组件来源”和“正式组件来源”的差异。

备选方案：
- 直接把 unified combo 升级为正式多 sleeve Governor 运行。否决，因为 scope 明显超出本次问题。

### 4. 只在 unified runtime compile/service 层补元数据

组件来源元数据会写入 `compiled_plan.unified_runtime.combo_context`，并在 unified combo 运行完成后写入 `run_meta.combo_context` / `run_meta.research_combo`。

原因：
- 这是当前最小可审计落点。
- 不需要为这次改动扩大到 `research_audit` 主合同。

## Risks / Trade-offs

- [风险] baseline 或 study 锚点未来改名，导致 unified combo compile 失败。
  - 缓解：将 baseline id、study id、window key、variant name 固定成常量，并在失败时抛出明确错误。
- [风险] stock 与 ETF 官方窗口不同，组合仍然只能在重叠区间计算。
  - 缓解：保留当前“重叠 NAV 窗口”逻辑，并在元数据中显式写出组件窗口。
- [风险] 这次改动后 combo 收益会显著变化。
  - 缓解：这是预期行为，必须通过重跑前后对比证明组合器之前吃错了组件，而不是策略自然退化。
- [风险] compile 过程引入 baseline/study 读取依赖，单测容易变脆。
  - 缓解：测试只断言关键合同字段，不绑定整份配置全文。

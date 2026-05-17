## Decision

### 1. 升格范围

本次只升格 **A 股 stock-only 正式 baseline**，不碰 combo baseline。

- baseline id: `baseline_V10_1`
- linked exp: `exp_20260512_063520440_82bb`
- asset scope: `cn_a_equity`
- effective period: `cn_a_equity:2012-2026`
- primary variable: `high_chase` 范围内 D5 deep-only immediate half-exit

### 2. 为什么重挂 `baseline_V10_1`

当前仓库里所有 stock 正式入口、默认引用和历史审计都已经围绕 `baseline_V10_1` 构建。对这类正式锚点，最小改动不是新建 `baseline_V10_3`，而是在用户明确批准后直接重挂既有 baseline id，并把这次 promotion 作为一条可审计的 official rebase / promotion 记录保留。

这样做的代价是：`baseline_V10.1` 的“历史含义”会从旧逻辑切到 D7 deep-only 逻辑。但该风险可接受，因为：

1. 用户已明确要求直接升格。
2. 旧锚点本地实验目录已缺失，继续保留旧 `linked_exp_id` 的治理价值有限。
3. baseline ledger、promotion note 和预先备份可以提供清晰回退路径。

### 3. 配置与法源

正式法源仍然只认：

- `outputs/baselines/baseline_V10_1/baseline.json.linked_exp_id`

展示层文件如：

- `outputs/baselines/index.json`
- `outputs/baselines/baseline_V10_1/machine/latest_champion.json`

都只作为 display / audit 附件，不得反向充当 baseline truth。

### 4. 产物策略

本次 promotion 除了写 `baseline.json` / `config.json` 外，还要从候选实验复制一组核心产物到 `outputs/baselines/baseline_V10_1/`，至少包括：

- `perf.json`
- `manifest.json`
- `execution_contract.json`
- `run_meta.json`
- `run_profile.json`
- `run_config.json`
- `resolved_config.json`
- `nav.csv`
- `orders.csv`
- `portfolio_trades.csv`
- `reason_codes.csv`
- `symbol_performance.csv`
- `stage_summary.json`
- `audit.json`

这样 baseline 目录本身就足以支撑基本读回、审计和人工回看，不依赖旧的缺失实验目录。

### 5. 回退

回退方式：

1. 用本次写出的 promotion 前备份恢复 `baseline_V10_1/baseline.json` 与 `config.json`。
2. 从 baseline ledger/report 中删除本次 promotion 追加记录，或显式追加一条 revert 记录。
3. 刷新 `outputs/baselines/index.json`。
4. 如需完全撤回，可同时删除本次复制进 baseline 目录的 D7 核心产物。

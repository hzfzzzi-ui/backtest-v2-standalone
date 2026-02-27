## Context

当前数据库 `pams_ohlcv_daily` 存储**不复权价格** + `adj_factor`（后复权因子，99.8% 行非空）。VECTOR 引擎在信号计算和成交执行中均直接使用不复权价格，且完全忽略 `adj_factor` 列。这导致除权除息日的价格跳空（如平安银行 19.24→11.93）使均线、ATR 等技术指标产生虚假信号。

数据库证据：
- 13,616,793 行数据，13,583,617 行有 adj_factor（33,176 行 NULL 为最新未补全数据）
- adj_factor 随时间递增（首日多为 1.0，最新日最大值 10,055.64）
- 除权日 adj_factor 发生跳变，open 价格 = prev_close / AF_ratio（确认为不复权）

前端 `wbPriceAdj` 控件已有 HTML（qfq/hfq/none 三档按钮），但仅在 ATR 说明文字中显示，未传递到后端。

## Goals / Non-Goals

**Goals:**
- 在信号计算路径中使用复权价格，消除除权除息导致的指标断裂
- 支持用户在前端切换三种复权模式（qfq/hfq/none）
- 成交执行保持使用不复权价格（真实市场价）
- 在 run_meta 中记录复权模式，确保实验可复现

**Non-Goals:**
- 不修改数据库表结构或数据导入流程
- 不修改 benchmark 数据的复权处理（benchmark 已独立加载）
- 不在前端可视化复权/不复权价格切换（仅影响引擎计算）
- 不修改已有的 cost_cfg（交易成本）逻辑

## Decisions

### Decision 1: 复权转换在 experiment_runner 层执行，而非引擎内部

**选择**: 在 `experiment_runner.run_experiment()` 中，`history` 加载之后、传入引擎之前，调用 `apply_price_adjustment()` 生成信号用的复权 history。同时保留原始 raw history 用于成交执行。

**替代方案**: 在引擎 `portfolio_simulator_strict.py` 内部做复权转换。

**理由**:
- 引擎已假设输入的 history 就是最终价格，修改引擎内部逻辑需要改动两条路径（SMA 和 generic signals），影响面大
- experiment_runner 是"配置编译层"，负责将用户配置转化为引擎运行时参数，复权转换属于这一层的职责
- 保持引擎的单一职责：引擎只负责接收价格矩阵并执行策略

### Decision 2: 引擎需要同时接收信号价格和成交价格

**选择**: 向引擎传递两个 DataFrame：`history`（复权后，用于信号计算）和 `raw_history`（不复权，用于成交执行）。引擎新增 `raw_history` 参数。

**替代方案 A**: 只传复权 history，引擎内部用 adj_factor 反算不复权价。

**替代方案 B**: 传复权 history + 一个 `price_adj_mode` 字符串，引擎内部判断。

**理由**:
- 方案 A 需要引擎知道复权公式细节，违反单一职责
- 方案 B 同上，且引擎需要持有 adj_factor 列做计算
- 传两个 DataFrame 语义最清晰：信号用 history，成交用 raw_history
- 当 mode="none" 时两者相同，可用同一引用（无额外开销）

### Decision 3: 默认复权模式为 hfq（后复权）

**选择**: 当用户未显式选择时，默认使用 `"hfq"`。

**理由**:
- 后复权数据稳定（不随新除权事件变化），无未来函数，无负价格风险
- 量化回测社区的共识最佳实践
- 前复权有隐含的未来信息（以最新 AF 为基准），不适合严格回测

### Decision 4: 前端 wbPriceAdj 控件复用已有 HTML，采用 segmented button 读值

**选择**: 复用 `index.html` 中已有的 `wbPriceAdj` select 元素或 segmented buttons。在 `buildConfigDraft()` 中读取其值并写入 `draft.universe.price_adj`。在 `runPayloadFromDraft()` 中提取为顶级字段 `price_adj`。

**理由**: 控件 HTML 已存在，只需 JS 侧接通即可。

### Decision 5: open_idx / close_idx 使用 raw_history 构建

**选择**: 引擎中 `open_idx` 和 `close_idx` 字典（用于成交执行和日终市值估算）改为从 `raw_history` 构建。信号矩阵 `mx` 仍由复权后的 `history` 构建。

**理由**:
- `open_idx` 用于计算实际成交价格和现金变动，必须是不复权价
- `close_idx` 用于日终持仓市值估算，也应使用不复权价（因为持仓数量 × 不复权价 = 真实市值）
- 信号矩阵只用于技术指标计算和信号生成，使用复权价

## Risks / Trade-offs

**[Risk] adj_factor NULL 导致复权价异常** → 在 `load_ohlcv_daily` 中将 NULL 填充为 1.0（等同于不复权），避免乘以 NaN 导致全列为 NaN。

**[Risk] 前复权模式下历史价格不稳定** → 文档说明：前复权以最新 adj_factor 为基准，每次新除权事件后所有历史价格改变，同一时段不同日期运行结果可能不同。run_meta 记录模式以供追溯。

**[Risk] mode="none" 时回归到当前行为** → 当 mode="none" 时，`history` 和 `raw_history` 指向同一 DataFrame，引擎行为与改动前完全一致，确保向后兼容。

**[Trade-off] 内存翻倍（两份 history）** → 对于 5000 标的 × 3000 交易日的场景，每份 DataFrame 约 150MB，两份共 300MB，在现代服务器可接受。当 mode="none" 时只需一份。

# A股市场快照运行说明（2026-03-11）

## 1. 产物位置

市场快照独立写入：

```text
outputs/market_snapshots/YYYY-MM-DD/
```

首轮固定产物：

- `market_snapshot.json`
- `market_brief.md`

不写入：

- `run_meta.json`
- baseline 目录
- experiment 目录


## 2. 运行命令

### 2.1 容器内运行

推荐在 `backtest-v2-standalone` 容器内执行，避免宿主机直接解析不到 `pams-postgres`：

```bash
docker exec backtest-v2-standalone python /app/backend/scripts/build_market_snapshot.py --trade-date 2026-03-10
```

若要写到指定目录：

```bash
docker exec backtest-v2-standalone python /app/backend/scripts/build_market_snapshot.py --trade-date 2026-03-10 --output-dir /app/outputs/market_snapshots/2026-03-10
```

### 2.2 本地运行

仅当本地 Python 能连到同一 PostgreSQL 网络时使用：

```bash
python backend/scripts/build_market_snapshot.py --trade-date 2026-03-10
```


## 3. 字段口径

六层固定结构：

- `index_layer`
- `style_layer`
- `breadth_layer`
- `liquidity_layer`
- `sentiment_layer`
- `risk_layer`

每层都包含：

- `sources`
- `coverage`
- `warnings`

关键约束：

- 所有 rolling / zscore / quantile 仅使用 `t` 及以前历史
- 不使用全样本标准化
- 不做 `bfill`
- 若请求日期超出本地价量库覆盖，按各层最近可用日生成，并写入 `effective_as_of` / `field_as_of` / `warnings`


## 4. 数据源优先级

首轮优先级如下：

1. `pit_index_daily`
2. `pams_ohlcv_daily`
3. `pams_sentiment_state`

说明：

- 指数层 / 风格层主要依赖 `pit_index_daily`
- 广度、流动性、风险主要由 `pams_ohlcv_daily` 派生
- `pams_sentiment_state` 用于补官方情绪分数与广度计数
- 若同层字段来自不同日期，会在 `coverage.field_as_of` 中显式记录


## 5. 审计说明

### 5.1 时点

- 市场快照是收盘后描述性产物
- 首轮不接入策略交易逻辑
- 若后续有策略消费，默认只能在 `t+1` 生效

### 5.2 缺失处理

- 缺字段保留 `null`
- 不静默补零
- 不把未来值回填到历史

### 5.3 日期处理

- 主市场价量层按 `pams_ohlcv_daily` 最新可用交易日锚定
- 指数层允许独立滞后，并单独告警
- 情绪表若比价量表更新，会与行为型派生字段并存显示


## 6. 当前已知限制

截至 `2026-03-11` 本地库的已知现状：

- `pams_ohlcv_daily` 最新 CN_A 交易日为 `2026-02-13`
- `pit_index_daily` 中主指数日线未覆盖到 `2026-03-10`
- `pams_sentiment_state` 已有 `2026-03-10` 记录

因此：

- 对 `2026-03-10` 执行构建时，预期得到 `partial` 状态
- 情绪/广度计数可能比价量层更新
- `warnings` 中应出现 stale / mixed-date 类告警

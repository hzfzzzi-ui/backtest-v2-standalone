## Context

压力测试显示 OHLCV 数据加载（PostgreSQL → pandas DataFrame）占回测总耗时的 66-76%。具体数据：

| 测试场景 | OHLCV 行数 | 加载耗时 | 总耗时 | OHLCV 占比 |
|---------|-----------|---------|-------|-----------|
| 1,631 sym × 16yr | 5,975,152 | 69s | 91s | 76% |
| 5,369 sym × 6yr | 6,985,684 | 78s | 106s | 73% |
| 5,369 sym × 8yr | 8,687,324 | 94s | 141s | 66% |

当前 `PostgresDataProvider.load_ohlcv_daily()` 每次调用都执行完整的 SQL 查询（含 `ANY(symbols)` 过滤 + `ORDER BY`），即使 symbols 和日期范围与上次完全相同。历史行情数据不可变，重复查询是纯浪费。

## Goals / Non-Goals

**Goals:**
- 连续调参场景（同一容器内多次回测）OHLCV 加载耗时从 ~94s 降至 ~2-4s
- 零侵入现有 `PostgresDataProvider` 代码
- 零运维（无 TTL、无手动清缓存、无 cron）

**Non-Goals:**
- 不缓存 benchmark / calendar / ST 数据（体量小，不是瓶颈）
- 不做跨容器持久化缓存（数据一致性成本太高）
- 不做增量更新（全表 dump 足够简单可靠）
- 不优化首次加载耗时（受限于 DB 查询速度，无法绕过）

## Decisions

### Decision 1: Wrapper 模式（而非继承或 mixin）

**选择**: `CachedDataProvider` 包装 `PostgresDataProvider`，实现 `DataProvider` 接口

**替代方案**:
- 继承 `PostgresDataProvider` 并 override `load_ohlcv_daily` — 耦合过紧，父类内部变更会影响子类
- 在 `pg_provider.py` 内部加缓存逻辑 — 职责不清，测试困难
- 独立缓存中间件 — 过度抽象，只有一个调用点

**理由**: Wrapper 模式职责单一、可独立测试、不修改现有代码一行。`experiment_runner.py` 只需改实例化处。

### Decision 2: 全表 dump（而非按查询缓存）

**选择**: 首次调用时 dump 整个 `pams_ohlcv_daily` 表到单个 Parquet 文件

**替代方案**:
- 按 (symbols, start, end) hash 缓存 — 换参数就 miss，命中率低
- 按 symbol 分文件 — 5,000+ 文件管理复杂，合并 IO 开销大
- 按年分区 — 合理但增加复杂度，当前全表 ~300MB 可接受

**理由**: 全表 dump 保证任意 symbols × 日期组合都命中。13.6M 行 Parquet 压缩后 ~300-400 MB，读取 ~2-4s。简单性远胜于优化首次 dump 的 3 秒额外开销。

### Decision 3: `/tmp` 作为缓存位置

**选择**: 缓存文件写入 `/tmp/ohlcv_cache.parquet`

**替代方案**:
- Docker volume 持久化 — 需要处理数据版本、失效、跨容器竞争
- 内存缓存（进程级 dict/DataFrame）— 不在持久文件中，无法跨进程共享
- `/app/cache/` 目录 — 同样非持久化，但语义不如 `/tmp` 明确

**理由**: `/tmp` 是容器临时空间的标准位置，容器重启自动清空，天然实现"进程级生命周期"。同容器内多个进程（如 Web server + 异步 worker）可以共享同一文件。

### Decision 4: Snappy 压缩 + date 排序写入

**选择**: `to_parquet(compression="snappy")`, 数据按 `(date, symbol)` 排序写入

**理由**: Snappy 压缩率适中（~4:1）、解压速度最快；按 date 排序使 Parquet 的 row group statistics 能有效支持日期范围的 predicate pushdown。

### Decision 5: 原子性写入

**选择**: 先写临时文件 `/tmp/ohlcv_cache.parquet.tmp`，完成后 `os.replace()` 到目标路径

**理由**: 避免并发进程读到写入中的不完整文件。`os.replace()` 在 Linux 上是原子操作。

## Risks / Trade-offs

- **[首次加载无加速]** 第一次回测仍需全表查询（~56s），比当前按 symbols 过滤的查询（~94s）反而更快（无 IN 过滤开销），但无法避免 → 可接受，首次是一次性成本
- **[内存峰值]** 全表 dump 时需要加载 13.6M 行到内存（~1.8 GB DataFrame）→ 在 16GB 环境下可能 OOM → 缓解：全表查询不做 `ORDER BY`，减少 DB 端排序内存；写入后立即释放 DataFrame
- **[磁盘空间]** 需要 ~300-400 MB `/tmp` 空间 → 容器通常有足够 `/tmp` 空间，风险低
- **[Symbol 格式]** DB 存 internal format（sh600000），缓存需存 canonical format → 在 dump 时做一次 `to_canonical()` 转换，后续读取无需再转

## Open Questions

- 如果 `/tmp` 磁盘空间不足，是否需要 fallback 到无缓存模式？（建议：try/except 包裹写入，失败时 fallback）

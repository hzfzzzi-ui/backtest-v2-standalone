## Context

当前回测产物流程：`run_experiment()` → `stabilize_experiment_result()` → 写入 8-11 个文件到 `outputs/experiments/exp_*` 目录 → 前端通过 `/api/backtest_v2/artifacts/read` 逐文件加载渲染。报告 HTML 只在前端 `generateReport()` 中用字符串拼接生成，不持久化。

前端 `generateReport()` 依赖的数据全部已落盘（perf.json, nav.csv, portfolio_trades.csv, portfolio_daily.csv, config.json, run_meta.json, funnel.csv），仅两个 gap：
1. `stockNames`（中文股票名）— 通过 `/api/backtest_v2/stock_names` 实时查 DB
2. `tier`（策略评级）— 只存在于 job payload，未写入磁盘

## Goals / Non-Goals

**Goals:**
- 每次回测自动生成持久化 `report.html`，无需用户手动操作
- 维护 `index.json` 实验索引，支持快速浏览
- 前端新增 History 面板，可浏览/回载/查看报告/删除实验
- 前端「导出报告」统一读后端 report.html，只维护一份模板
- 清空所有旧实验数据

**Non-Goals:**
- 不做实验对比（A/B diff）功能
- 不做报告的自定义模板/主题
- 不做实验标签手动编辑
- 不做分页/搜索（单用户，实验量不会太大）

## Decisions

### 决策 1：Python 端 report_generator.py 生成 report.html

新建 `backend/core/report/report_generator.py`，用 Python f-string / 字符串模板生成与前端 `generateReport()` 相同结构的 HTML。

```
generate_report(results_dir: str) -> str
  1. 读 perf.json, run_meta.json, config.json, portfolio_daily.csv,
     portfolio_trades.csv, funnel.csv, stock_names.json
  2. 计算 §2 月度收益、§3 回撤分析、§4 交易分析、§5 持仓分析
  3. 渲染 §6 策略参数（从 config.json 的 wc/bc 两层读取）
  4. 渲染 §7 交易明细附录
  5. 内联 CSS，返回完整 HTML 字符串
  6. 写入 results_dir/report.html
```

选择 Python 而非 Jinja2 模板：因为当前前端也是纯字符串拼接，逻辑对等移植最简单，且无额外依赖。

**前端 `generateReport()` 的处置：** 改为 fetch 后端 `report.html` 并在新标签页展示。不再前端拼接。如果后端 report.html 不存在（旧实验），fallback 到前端本地生成。

### 决策 2：stock_names.json 在 stabilize 阶段落盘

在 `ensure_standard_artifacts()` 中，从 portfolio_trades.csv 提取 symbol 列表，调用现有的 `resolve_stock_names()` 查 DB，写入 `stock_names.json`：

```json
{"600519.SH": "贵州茅台", "000001.SZ": "平安银行"}
```

这样 report_generator 可直接读取，无需再查 DB。

### 决策 3：index.json 结构与维护

每次 `stabilize_experiment_result()` 完成后追加到 `outputs/experiments/index.json`：

```json
[
  {
    "exp_id": "exp_20260227_143022",
    "label": "SMA_CROSS 5/20 | CUSTOM 2只 | HFQ | 2024-01~06",
    "created_at": "2026-02-27T14:30:22",
    "status": "OK",
    "total_return": -0.0023,
    "max_drawdown": -0.0023,
    "sharpe": -2.02,
    "trades": 6,
    "has_report": true
  }
]
```

label 生成规则：
```
{strategy_name} {fast}/{slow} | {universe_mode} {N}只 | {price_adj} | {start}~{end月}
```

单用户场景，直接读写 JSON 文件，无并发锁。

### 决策 4：4 个新 API 端点

| 方法 | 路径 | 实现 |
|------|------|------|
| GET | `/api/backtest_v2/experiments` | 读 index.json，返回列表（最新在前） |
| GET | `/api/backtest_v2/experiments/{exp_id}/report` | 返回 report.html（`Response(media_type="text/html")`） |
| DELETE | `/api/backtest_v2/experiments/{exp_id}` | 删除实验目录 + 从 index.json 移除 |
| DELETE | `/api/backtest_v2/experiments` | 清空 experiments 目录 + 重置 index.json 为 `[]` |

### 决策 5：History 面板 UI

Rail 新增第 5 个图标（时钟/历史图标），Drawer 新增 `data-module="history"` section。

```
┌──────────────────────────────────┐
│  实验历史                [清空]   │
├──────────────────────────────────┤
│  ┌────────────────────────────┐  │
│  │ SMA_CROSS 5/20             │  │ ← .card 样式
│  │ CUSTOM 2只 | HFQ           │  │
│  │ 2024-01-01 ~ 2024-06-01   │  │
│  │                            │  │
│  │ 收益 -0.23%  夏普 -2.02    │  │ ← .wb-stat-row 样式
│  │ 回撤 -0.23%  交易 6       │  │
│  │                            │  │
│  │ [查看报告]  [加载结果]      │  │ ← .wb-action-btn
│  │ 2026-02-27 03:51           │  │
│  └────────────────────────────┘  │
│  (按时间倒序排列)                 │
└──────────────────────────────────┘
```

- **查看报告**: `window.open('/api/backtest_v2/experiments/{exp_id}/report', '_blank')`
- **加载结果**: 调用 `loadActiveArtifacts()` 用该实验的 results_dir，覆盖 `state.active_artifacts` 和 `state.active_result`，然后 `renderRightInspector()` 刷新工作台

### 决策 6：tier 持久化

在 `stabilize_experiment_result()` 中将 `tier` 写入 `run_meta.json` 的顶层字段。当前 tier 在 `_job_payload()` 中默认为 `"T0"`，直接传入即可。

## Risks / Trade-offs

**[维护] 前后端报告模板同步** → 后端 Python 模板与前端 JS 模板生成相同 HTML。采用「前端不再生成、统一读后端」策略消除漂移风险。保留前端 fallback 仅用于 report.html 不存在的旧实验。

**[性能] stock_names 查 DB** → 每次 stabilize 多一次 DB 查询。但 symbols 数量有限（通常 <50），且是回测结束后的一次性查询，开销可忽略。

**[数据] index.json 一致性** → 如果手动删除实验目录，index.json 会有孤儿记录。可在 GET /experiments 时做一次存在性校验（lazy cleanup）。

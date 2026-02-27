## 架构概述

```
前端 (backtest_v2.js)                    后端
┌─────────────────────┐          ┌──────────────────────┐
│ 模式按钮 click      │          │ API 层               │
│   ↓                 │          │   BacktestV2Request   │
│ wbUniverseMode      │  POST    │   + universe_mode     │
│ + industries[]      │ ───────→ │   + industries[]      │
│ + symbols[]         │          │       ↓               │
│   ↓                 │          │ experiment_runner     │
│ buildConfigDraft()  │          │       ↓               │
│   ↓                 │          │ universe_resolver     │
│ 运行按钮            │          │   resolve_symbols()   │
└─────────────────────┘          │       ↓               │
                                 │ ┌───────────────────┐ │
      GET /industries            │ │ ALL_A:            │ │
      ←──────────────────────────│ │   pit_security_   │ │
      行业列表                    │ │   master + ohlcv  │ │
                                 │ │                   │ │
                                 │ │ HS300_ZZ500:      │ │
                                 │ │   pit_index_      │ │
                                 │ │   constituents    │ │
                                 │ │                   │ │
                                 │ │ INDUSTRY:         │ │
                                 │ │   pit_industry_   │ │
                                 │ │   history         │ │
                                 │ │                   │ │
                                 │ │ CUSTOM:           │ │
                                 │ │   直接用 symbols  │ │
                                 │ └───────────────────┘ │
                                 └──────────────────────┘
```

## 设计决策

### D1: 数据导入脚本位置
**决策**: 新建 `backend/core/universe/ingest_universe.py`，作为 CLI 可执行模块。
**理由**: 与已有的 `hs300_csi500.py` 同目录，职责内聚。

### D2: industry_code 到 L1 行业名映射
**决策**: 在导入脚本中内嵌固定映射表（31 个 code 前2位→行业名），从 AKShare `sw_index_first_info()` + `index_component_sw()` 验证后写入代码。
**理由**: 这是申万2021版标准，变更极低频。运行时不依赖外部 API，确保离线可用。

### D3: end_date 推算
**决策**: 对同一只股票的多条行业记录，按 `start_date` 排序，前一条的 `end_date` = 下一条的 `start_date`。最后一条 `end_date = NULL`。
**理由**: AKShare 不直接提供 end_date，需要从多条记录推算。NULL 表示"当前仍有效"，是 SCD Type 2 的标准做法。

### D4: 指数成分表结构
**决策**: `pit_index_constituents(index_code, symbol, start_date, end_date, source, created_at)`，使用 `CREATE TABLE IF NOT EXISTS`。
**理由**: 复用 PIT 表的 start/end 模式，与 `pit_industry_history` 一致。end_date 当前全部为 NULL（AKShare 无移出数据），未来 Tushare 权限升级后可补充。

### D5: universe resolver 函数签名
**决策**: `resolve_universe_by_mode(mode, as_of, db, runtime, industries=None, symbols=None, universe_limit=None) -> (list[str], dict)`
**理由**: 返回 `(symbols, meta)` 与已有的 `resolve_universe_symbols()` 保持一致。meta 记录来源信息供 run_meta 使用。

### D6: API 层变更
**决策**: 在 `BacktestV2ExperimentRequest` 中新增 `universe_mode: str = "CUSTOM"` 和 `industries: list[str] = []`，默认 CUSTOM 以保持向后兼容。
**理由**: 现有请求不传 universe_mode 时，行为与之前完全一致（用 symbols 列表）。

### D7: 行业选择器 UI
**决策**: 用 checkbox chip 组件渲染 31 个行业，从 `GET /api/backtest_v2/industries` 动态加载。
**理由**: 不硬编码行业列表，未来行业标准变更时只需重新导入数据。

## 关键文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/core/universe/ingest_universe.py` | 新建 | 数据导入 CLI 脚本 |
| `backend/core/universe/universe_resolver.py` | 新建 | 4 模式 resolver |
| `backend/core/universe/hs300_csi500.py` | 复用 | ALL_A 模式复用 `load_constituents_from_db()` |
| `backend/api/endpoints/backtest_v2.py` | 修改 | 请求模型 + 行业列表 API |
| `backend/core/tools/experiment_runner.py` | 修改 | 集成 resolver |
| `frontend/assets/js/backtest_v2.js` | 修改 | 按钮绑定 + 行业选择器 + config draft |

## 数据流

### 导入流程
```
AKShare API
  ├─ stock_industry_clf_hist_sw() → 12,717 条
  │    ↓ code前2位映射 + end_date推算
  │    → pit_industry_history (TRUNCATE + INSERT)
  │    → pit_security_master.industry (UPDATE)
  │
  └─ index_stock_cons('000906') → ~800 条
       ↓ normalize_stock_symbol
       → pit_index_constituents (TRUNCATE + INSERT)
```

### 回测流程
```
前端 POST {universe_mode, industries, symbols, start_date, ...}
  → API 解析请求
  → experiment_runner
  → resolve_universe_by_mode(mode, as_of=start_date, ...)
  → 返回 (symbols, meta)
  → symbols 传入引擎执行回测
  → meta 写入 run_meta.json
```

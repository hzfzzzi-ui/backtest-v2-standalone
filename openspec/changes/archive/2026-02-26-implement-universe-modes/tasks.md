## 1. 数据库表与导入脚本

- [x] 1.1 新建 `backend/core/universe/ingest_universe.py`，实现 `--industry` 模式：调用 AKShare `stock_industry_clf_hist_sw()` 拉取全量申万行业分类历史，按 code 前2位映射到31个L1行业名，推算 end_date（SCD Type 2），TRUNCATE + INSERT 写入 `pit_industry_history` 表
- [x] 1.2 在 `ingest_universe.py` 中实现 `--index` 模式：调用 AKShare `index_stock_cons('000906')` 拉取中证800成分，CREATE TABLE IF NOT EXISTS `pit_index_constituents`，TRUNCATE + INSERT 写入，symbol 经 `normalize_stock_symbol` 标准化
- [x] 1.3 在 `ingest_universe.py` 中实现 `--update-master` 逻辑：用每只股票最新行业分类更新 `pit_security_master.industry` 字段（当前全部为 NULL）
- [x] 1.4 在 Docker 容器中运行导入脚本，验证 `pit_industry_history` 写入 12,000+ 条、`pit_index_constituents` 写入 ~800 条、`pit_security_master.industry` 非 NULL 数量 > 5,000

## 2. Universe Resolver 后端

- [x] 2.1 新建 `backend/core/universe/universe_resolver.py`，实现 `resolve_universe_by_mode(mode, as_of, db, runtime, industries=None, symbols=None, universe_limit=None) -> (list[str], dict)`，包含 ALL_A / HS300_ZZ500 / INDUSTRY / CUSTOM 四种模式分支
- [x] 2.2 实现 ALL_A 模式：复用 `hs300_csi500.py` 中 `load_constituents_from_db()` 逻辑，返回截至 as_of 全部活跃 CN_A 股票
- [x] 2.3 实现 HS300_ZZ500 模式：查询 `pit_index_constituents` 表，条件 `start_date <= as_of AND (end_date IS NULL OR end_date > as_of)`，表空时抛出 `UniverseLoadError`
- [x] 2.4 实现 INDUSTRY 模式：接收 industries 参数（L1 行业名列表），查询 `pit_industry_history` 表做 PIT 过滤，返回多行业并集，表空时抛出 `UniverseLoadError`
- [x] 2.5 实现 CUSTOM 模式：直接使用 symbols 列表，经 `normalize_stock_symbol` 标准化后返回
- [x] 2.6 所有模式返回 `(symbols, meta)` 元组，meta 包含 `universe_mode`、`symbols_source`、`raw_count`、模式相关信息（如 industries 列表）

## 3. API 层与 experiment_runner 集成

- [x] 3.1 在 `backend/api/endpoints/backtest_v2.py` 的 `BacktestV2ExperimentRequest` 中新增 `universe_mode: str = "CUSTOM"` 和 `industries: list[str] = []` 字段
- [x] 3.2 新增 `GET /api/backtest_v2/industries` 端点，查询 `pit_industry_history` 表返回去重的 `industry_l1` 列表，表空返回空列表
- [x] 3.3 修改 `backend/core/tools/experiment_runner.py`，在执行回测前调用 `resolve_universe_by_mode()` 解析 symbols，将 universe_mode 和 industries 从请求透传到 resolver
- [x] 3.4 将 resolver 返回的 meta 写入 `run_meta.json` 的 `universe` 字段

## 4. 前端 UI 绑定

- [x] 4.1 在 `backtest_v2.js` 中为 4 个 Universe 模式按钮绑定 click 事件：更新 `wbUniverseMode` hidden select、切换 active 样式、调用 `updateUniverseInputVisibility()`
- [x] 4.2 页面加载时默认 ALL_A 模式为 active 状态
- [x] 4.3 实现行业选择器：切换到 INDUSTRY 模式时调用 `GET /api/backtest_v2/industries` 获取行业列表，渲染为可勾选的 checkbox chip 组件到 `wbIndustryPicker` 容器
- [x] 4.4 修改 `buildConfigDraft()`：根据 `universe_mode` 构建不同配置字段 — ALL_A/HS300_ZZ500 仅传 mode，INDUSTRY 传 mode + industries，CUSTOM 传 mode + symbols

## 5. 端到端验证

- [x] 5.1 Docker rebuild，从前端分别测试 ALL_A、HS300_ZZ500、INDUSTRY（选"银行"）、CUSTOM 四种模式的回测请求，验证 resolver 正确解析 symbols 并写入 run_meta

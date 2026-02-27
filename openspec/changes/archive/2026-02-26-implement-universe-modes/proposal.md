## Why

前端 Universe 面板已有 4 个模式按钮（全A股/沪深300+中证500/自选行业/个股），但只有"个股"模式能正常工作。其余三个模式的按钮没有绑定事件，后端也没有根据 `universe_mode` 解析股票池的逻辑。用户无法选择不同的回测范围，严重限制了系统的实用性。

## What Changes

- 编写数据导入脚本，从 AKShare 拉取申万行业分类历史和中证800（沪深300+中证500）成分数据，写入数据库
- 新建 `pit_index_constituents` 表存储指数成分（含纳入日期，支持 point-in-time 查询，防止未来函数）
- 填充已有的 `pit_industry_history` 表（12,717 条申万行业变更记录，回溯至 2010 年）
- 后端新增 universe resolver 模块，根据 `universe_mode` + 回测日期解析出 point-in-time 的股票列表
- API 请求模型新增 `universe_mode` 字段，透传到 experiment runner
- 前端绑定 4 个模式按钮的点击事件，填充行业选择器（31 个申万一级行业），模式切换联动显示/隐藏

## Capabilities

### New Capabilities
- `universe-data-ingest`: 数据导入脚本 — 从 AKShare 拉取行业分类历史 + 指数成分数据，写入 PIT 表，含 point-in-time 防未来函数设计
- `universe-resolver`: 后端 universe 解析器 — 根据 mode + as_of 日期从 DB 查询出 symbols 列表，支持 ALL_A / HS300_ZZ500 / INDUSTRY / CUSTOM 四种模式
- `universe-ui-binding`: 前端 UI 绑定 — 模式按钮交互、行业选择器填充、config draft 联动

### Modified Capabilities

（无现有 spec 需要修改）

## Impact

- **数据库**: 新建 `pit_index_constituents` 表；填充 `pit_industry_history` 表（当前 0 行）；更新 `pit_security_master.industry` 字段
- **后端 API**: `BacktestV2ExperimentRequest` 新增 `universe_mode` + `industries` 字段
- **后端核心**: `experiment_runner.py` 调用 universe resolver 替代硬编码 symbols
- **前端**: `backtest_v2.js` 的按钮事件绑定 + 行业选择器 + config draft 构建
- **依赖**: AKShare（已安装 v1.18.28）

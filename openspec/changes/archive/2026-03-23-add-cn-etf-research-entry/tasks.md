## 1. 数据库与数据链

- [x] 1.1 设计并落地 `pit_cn_etf_master`、`pams_cn_etf_daily`、`cn_etf_data_coverage_daily` 的 DDL 与文档；DoD：三张表和字段合同可创建且文档齐全；验证：DDL dry-run + schema contract 检查；风险：字段设计过早泛化导致后续实现变重。
- [x] 1.2 实现首波 9 只 ETF 的受控目录导入链；DoD：目录表只写入指定 ETF，包含批次与暴露类别；验证：单测 + SQL 断言白名单数量为 9；风险：symbol 标准化与交易所后缀不一致。
- [x] 1.3 实现 ETF 日线最小刷新/导入链与覆盖摘要；DoD：独立 ETF 日线表能写入 OHLCV 且同步更新 coverage 摘要；验证：导入集成测试 + summary 产物；风险：价格口径与分红语义不完整。

## 2. 运行时与研究入口

- [x] 2.1 在资产边界中新增 `cn_etf` profile，并补齐运行时 `assetContext` 传递；DoD：请求、compile、manifest、run_meta 均能稳定暴露 `cn_etf`；验证：资产上下文单测 + runtime contract 测试；风险：默认 A 股回退逻辑误伤 ETF。
- [x] 2.2 为 `cn_etf` 实现 `CUSTOM` 解析与 ETF 白名单校验；DoD：resolver 仅接受目录内 ETF，拒绝目录外 symbol；验证：resolver 单测；风险：现有股票 resolver 分支被错误复用。
- [x] 2.3 实现 `cn_etf_single_asset_template`、`cn_etf_first_wave_core`、`cn_etf_first_wave_all` 三个最小研究 preset；DoD：preset 能编译成标准运行配置且不改 `baseline_V10.x` 主逻辑；验证：study/compile 测试 + 产物快照；风险：preset 展开与 ETF 目录失配。
- [x] 2.4 为 ETF 运行补齐研究元信息与口径提示；DoD：`run_meta.json` 暴露 `etf_symbols`、`etf_batch`、`coverage_start/end`、`daily_table`、`price_series_semantics`；验证：实验产物断言；风险：页面和产物口径不一致。

## 3. 前端页面与交互

- [x] 3.1 在研究台配置页新增 `cn_etf` 资产入口与 ETF 专属文案切换；DoD：资产切换后页面从“股票池”切到 ETF 语义；验证：前端状态测试 + 手动页面检查；风险：旧壳 fallback 继续写死 A 股股票文案。
- [x] 3.2 为 ETF 资产隐藏或禁用股票专属过滤控件，并新增首波 ETF 预设入口；DoD：ST、行业、PIT 等股票控件在 `cn_etf` 下不再作为有效输入，页面可一键填充 core/all 预设；验证：前端交互测试；风险：禁用只停留在 UI 层，后端仍收到脏字段。
- [x] 3.3 扩展 ResultsWorkbenchSnapshot 与结果页摘要，显示 ETF 名单、批次、覆盖窗口和价格语义； DoD：ETF 结果页不再显示股票 PIT 文案；验证：snapshot 构建测试 + 页面渲染测试；风险：旧组件仍从 A 股字段反推资产类型。

## 4. 验收与回归

- [x] 4.1 补齐数据库、runtime、resolver、前端的最小回归测试；DoD：新增测试覆盖 `cn_etf` 入口主路径和失败路径；验证：定向 pytest/node 测试通过；风险：只测 happy path，遗漏目录外 ETF 与空覆盖窗口。
- [x] 4.2 准备一轮首波 ETF smoke run 与 A/B 验收脚本；DoD：能至少跑通单只 `512100.SH` 和 `cn_etf_first_wave_core` 的研究入口，并产出标准 artifacts；验证：实验目录产物完整；风险：数据库覆盖不足导致 smoke run 只在编译层通过。
- [x] 4.3 输出回退说明与研究口径提示；DoD：变更说明包含回退步骤、数据表影响、价格语义限制；验证：design/docs 自检；风险：实现完成后无人知道 ETF 结果是否可与股票总收益直接比较。

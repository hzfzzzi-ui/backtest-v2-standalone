## Why

当前 A 股个股腿正式股票池是 `HS300_ZZ500 + PIT_DYNAMIC`，实际含义是通过 `pit_index_constituents(index_code='000906.SH')` 消费中证 800 PIT 成分，覆盖沪深 300 与中证 500。这个口径解释性强、流动性更稳，但也让个股腿长期偏大中盘 beta。

用户希望开启 `HS300 + ZZ500 + CSI1000 PIT` 股票池扩展研究。本轮研究的核心问题不是“多加小盘后收益是否更高”，而是：

- 在 PIT 纪律下扩展到中证 1000 后，个股腿是否获得更好的机会宽度；
- 新增标的是否带来不可接受的数据质量、流动性、换手、回撤或硬门槛风险；
- 是否值得进入 stock-only 三窗口回测，再决定是否进入 stock+ETF 组合层验证。

## What Changes

- 新增 research-only 的联合 PIT 股票池口径：`HS300_ZZ500_CSI1000`。
- 联合口径只 union `000906.SH` 与 `000852.SH` 的 PIT 成分历史，不使用静态当前成分股清单。
- 新增 stock-only study：基线 `HS300_ZZ500 + PIT_DYNAMIC`，实验组 `HS300_ZZ500_CSI1000 + PIT_DYNAMIC`。
- 先输出静态审计：窗口内 symbol 数、CSI800/CSI1000 新增与重叠、OHLCV 覆盖、ST/停牌/退市过滤风险、行业覆盖、数据库规模和运行时影响。
- 不修改排序因子、信号时点、成交时点、退出规则、资金预算、ETF 池、防守层或正式 baseline。

## Capabilities

### New Capabilities

- `csi1000-pit-stock-pool-expansion-research`: 受控研究 `HS300_ZZ500_CSI1000` PIT 联合股票池，并要求 stock-only 先行、三窗口审计和可回退产物。

### Modified Capabilities

- `universe-resolver`: 增加一个 research-only 可用的 A 股个股联合 PIT universe mode。

## Impact

- 影响范围：
  - `backend/core/universe/*`
  - `backend/core/tools/data_bundle_builder.py`
  - `research/studies/v10/*`
  - `backend/scripts/generated/*`
  - `tests/unit/*`
  - 本 change 目录
- 不影响范围：
  - `baseline_V10.1`
  - `CN_STOCK_ETF_COMBO_BASELINE_V3`
  - stock 排序/入场/退出逻辑
  - ETF 腿、组合权重、防守仓定义
  - 前端回测页面默认口径
- 产物范围：
  - 静态审计和真实回测结果只写入 `outputs/`，不作为源码主路径。

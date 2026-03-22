# Tasks

## 1. Spec

- [x] 1.1 补充 `ma200-market-state` delta spec，声明 legacy 长均线窗口可配置，以及 `TRANS_UP / TRANS_DOWN` multiplier 可拆分
- [x] 1.2 补充 `regime-router` delta spec，声明 `freeze_trans_up_entries` 启用时 `TRANS_UP` 不得产生新买入信号
- [x] 1.3 补充 `legacy-market-filter-ab` capability spec，声明 `AB1 / AB2 / AB3` 的最小实验合同

## 2. Implementation

- [x] 2.1 为 `MarketFilterConfig` 增加 `long_ma_window` 和 `freeze_trans_up_entries`
- [x] 2.2 完成 schema / compiler / runtime 对新字段的透传
- [x] 2.3 将 legacy 长均线从硬编码 `200` 改为配置驱动
- [x] 2.4 在信号后处理层接入 `TRANS_UP` 禁新开仓逻辑

## 3. Verification

- [x] 3.1 补充和更新单测，覆盖 legacy 长均线窗口可配置、`TRANS_UP / TRANS_DOWN` multiplier 拆分、`freeze_trans_up_entries`
- [x] 3.2 运行定向单测与语法检查

## 4. AB

- [x] 4.1 新增 AB 脚本，按顺序运行 `AB1 / AB2 / AB3`
- [x] 4.2 生成 `summary / report / performance_comparison`
- [x] 4.3 明确 intended diff、风险、验证与回退路径

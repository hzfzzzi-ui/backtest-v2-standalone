## 1. 数据模型与入库

- [x] 1.1 为 `pams_ohlcv_daily` 设计并落地 nullable 流动性字段，保持 `turnover=成交额` 语义不变
- [x] 1.2 新增官方 `daily_basic` 导入/回填脚本，按 `symbol + trade_date` 幂等更新

## 2. 运行时透传与配置

- [x] 2.1 扩展 provider / mapping / cache，将 daily_basic 字段作为 optional extras 透传到 history frame
- [x] 2.2 在 `universe.filters` 增加独立的换手率过滤配置键，默认关闭
- [x] 2.3 在股票池过滤逻辑中实现基于历史 20 日平均换手率的可选过滤，并对缺字段场景 fail-fast

## 3. 校验、审计与测试

- [x] 3.1 扩展 `validate_data` 审计链路，对启用态换手率过滤执行字段存在性、非负性与覆盖率检查
- [x] 3.2 补齐 provider、data bundle、universe filter、semantic compile、validate 相关单测

## 4. 研究接入说明

- [x] 4.1 更新配置样例与 change 说明，明确 `turnover` 与 `turnover_rate*` 语义，并给出最小启用示例
- [x] 4.2 给出最小可证伪实验模板，只比较 amount-based filter 与 turnover-rate-based filter

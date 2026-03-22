## 1. 后端过滤链路

- [ ] 1.1 在 `backend/core/universe/hs300_csi500.py` 增加科创板识别与过滤支持，完成定义：`exclude_star_market` 可被解析、候选集可生成 `is_star_market`、开启后写入 `EXCLUDE_STAR_MARKET` 计数；验证方式：后端单元测试覆盖默认关闭与开启过滤；风险点：symbol 格式不一致导致误判。
- [ ] 1.2 在 `backend/core/tools/data_bundle_builder.py` 与 `backend/core/tools/runtime_data_access.py` 接入共享 symbol 级科创板过滤 helper，完成定义：dynamic universe 路径与静态路径口径一致；验证方式：定向单元测试检查 dynamic 路径下科创板被排除；风险点：两条路径元数据更新不一致。

## 2. 配置协议与前端绑定

- [ ] 2.1 扩展后端 universe schema 与 runtime compile，完成定义：`universe.filters.exclude_star_market` 能通过语义校验并透传到 canonical runtime config；验证方式：编译相关单元测试断言字段保留，缺省时不改变旧行为；风险点：字段在 facade 或 partial merge 中丢失。
- [ ] 2.2 在前端基础过滤区新增科创板 checkbox，并打通草稿构建与配置回填，完成定义：UI 勾选状态与 `universe.filters.exclude_star_market` 往返一致；验证方式：frontend harness / workbench 回归测试；风险点：DOM id、默认值或回填逻辑不一致导致字段漂移。

## 3. 回归验证与审计

- [ ] 3.1 补充后端与前端定向测试并执行，完成定义：至少覆盖默认关闭、开启过滤、dynamic 路径、schema compile、UI 回填五类场景；验证方式：运行 pytest 与前端测试命令并记录结果；风险点：测试夹具未覆盖实际 symbol 格式。
- [ ] 3.2 复核可观测性与回退路径，完成定义：确认 `filters_config` / `excluded_counts` 能反映开关生效，并整理回退方法；验证方式：检查测试断言与最终说明；风险点：实现生效但元数据未同步，导致审计不可见。

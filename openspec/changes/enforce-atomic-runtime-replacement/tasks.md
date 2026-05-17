## 1. Implementation

- [x] 1.1 在执行内核中拆分普通卖单与 `ROTATION_REPLACE` 卖单，禁止 replacement 卖单提前落单。
- [x] 1.2 为 replacement 候选增加同 pass 买入可执行性检查，买入可执行时同时写入卖买订单。
- [x] 1.3 买入不可执行时同时取消 pair，并在 `debug_plan` / candidate audit 中记录原因。
- [x] 1.4 将 `rotation_replace_count` 口径改为最终执行 pair 数，并新增 planned/executed/cancelled 审计字段。
- [x] 1.5 在严格向量 runtime 的 T+1 fill 前增加 replacement pair 二次过滤，防止 fill 阶段留下孤立卖单。

## 2. Tests

- [x] 2.1 增加单测：replacement 买单可执行时输出一卖一买。
- [x] 2.2 增加单测：replacement 买单不可执行时不输出孤立卖单。
- [x] 2.3 增加单测：replacement 关闭时普通订单行为不变。
- [x] 2.4 增加单测：fill 口径下买入现金不足时，pending replacement pair 被整体移除。

## 3. Validation

- [x] 3.1 `openspec validate enforce-atomic-runtime-replacement --strict`
- [x] 3.2 `python -m pytest tests/unit/test_multi_alpha_order_planning.py -q`
- [x] 3.3 Docker 内对 B1 study 做 dry-run，确认 runtime_config_json 仍为执行真相。
- [x] 3.4 Docker 内跑 `1626` 主窗口，并审计 `orders.csv` 中 replacement sell/buy 配平。

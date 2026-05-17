## 1. Study 合同

- [x] 1.1 创建 proposal/design/spec/tasks，DoD：OpenSpec 能识别 4 类 artifact；验证：`openspec status --change evaluate-theme-protected-stock-replacement --json`；风险：未先锁范围就把 shadow 当真实回测。
- [x] 1.2 新增 study YAML，DoD：dry-run 能生成窗口和 variant；验证：`python -m backend.cli study_run cn_stock_etf/cn_stock_etf_theme_protected_replacement_v1 --dry-run`；风险：variant 名称误导为 baseline。

## 2. Runner 实现

- [x] 2.1 新增 `theme_protected_replacement_study` runner，DoD：读取 B0.1 source bundle 并输出 machine/human summary；验证：unit test；风险：把 `outputs/` 临时脚本当源码。
- [x] 2.2 接入 `study_runner` 分发，DoD：metadata runner_mode 能正确调用新 runner；验证：unit test；风险：影响其他 study runner。
- [x] 2.3 输出 formal verdict，DoD：覆盖不足窗口为 inconclusive，主窗口只确认“值得进入 B1 AB”；验证：unit test 检查 verdict；风险：误把 hard gate PASS 当研究接受。

## 3. 验证与运行

- [x] 3.1 跑新增单测，DoD：相关 unit tests 通过；验证：`python -m pytest ... -q`；风险：只跑真实 study 漏掉合同回归。
- [x] 3.2 跑 OpenSpec 校验，DoD：strict validate 通过；验证：`openspec validate evaluate-theme-protected-stock-replacement --strict`；风险：spec 不可归档。
- [x] 3.3 运行正式 study，DoD：输出 study artifacts 和 conclusion registry；验证：study_run stdout 与输出文件；风险：registry 未被前端 journal 匹配。

## 4. 前端登记与结论

- [x] 4.1 创建 study journal round，DoD：前端研究页能看到本轮 study；验证：round json 存在并包含 evidence；风险：只生成 outputs 但前端无入口。
- [x] 4.2 输出详细中文分析，DoD：明确事实、推断、结论、风险、下一步；验证：对话框结论；风险：把 shadow 触发频率解释成收益。

## 1. 前端旧控制器收缩

- [x] 1.1 继续把 `backtest_v2.js` 和 `ui-controls.js` 中剩余的高耦合职责拆到 `frontend/assets/js/pages/*`，并把旧文件降成薄壳。DoD：新增页面模块接管活跃实现，旧文件不再保留同名活跃函数；验证：`node --check` + `tests/unit/test_frontend_runtime_boundaries.py`；风险：全局依赖和脚本装载顺序。
- [x] 1.2 删除一轮 `_legacy...MovedTo...` 过渡函数，至少覆盖已由页面模块稳定接管的职责。DoD：旧文件过渡函数数量明显下降且页面行为不变；验证：静态边界测试 + 页面基本操作烟测；风险：误删仍被 HTML 或全局事件引用的函数。
- [x] 1.3 继续压低 `artifacts.js` 的兼容分支和错误噪音，确保可选接口失败只做静默降级。DoD：可选行情接口失败不污染状态中心；验证：静态测试与浏览器控制台核验；风险：把真正的关键错误误当成可选错误吞掉。

## 2. API 兼容层收缩

- [x] 2.1 梳理 `backend/api/endpoints/*` 与 `backend/api/backtest_v2/*` / `backend/api/mobile/*` 的反向依赖，列出仍然由旧目录承载的重型实现。DoD：形成可执行的清单；验证：代码扫描结果与 import 路径核对；风险：误判 path 兼容层与真实实现层。
- [x] 2.2 将至少一批旧 `endpoints/*` 文件压成薄 shim，禁止其继续承载重型编排逻辑。DoD：旧目录保留 path 兼容但主逻辑转移到新目录或 service；验证：API 单测与旧 path 冒烟；风险：旧 path 兼容被误伤。
- [x] 2.3 清除新实现对 compat module 的反向 import，尤其是 mobile/backtest 实现中的 compat 回跳。DoD：依赖方向变成“compat 依赖新实现”而不是反过来；验证：静态搜索与 API 单测；风险：遗漏隐藏调用点。

## 3. 执行 compat shim 收缩

- [x] 3.1 审计 `foundation_shell`、strict shim、`portfolio_builder.py`、`legacy_loop.py` 当前仍承担的活跃职责，并标出可继续外提的部分。DoD：形成职责矩阵；验证：代码阅读与调用链核对；风险：低估执行链隐式依赖。
- [x] 3.2 在不改变执行语义的前提下，继续压薄 compat shim，禁止新逻辑进入这些文件。DoD：职责外提后 compat 文件仅保留过渡包装；验证：单测 + 执行链 smoke；风险：价格型信号时点漂移。
- [x] 3.3 每次触及执行 compat 文件后复核 `baseline_V10_1 -> exp_20260314_144548534_7db9` 的 `total_return/max_drawdown/cagr/sharpe/calmar/trades/turnover`。DoD：清理前后指标一致；验证：固定回归脚本或 TestClient 快照；风险：误把环境噪音当成口径漂移。

## 4. 脚本面与工作区治理

- [x] 4.1 继续压薄已迁移的顶层脚本，确保 study/CLI 迁移完成后的脚本只剩 thin wrapper。DoD：顶层脚本不再包含正式业务逻辑；验证：`tests/unit/test_script_surface_governance.py`；风险：破坏已有人工使用入口。
- [x] 4.2 继续更新 `backend/scripts/inventory.json`、根目录 `README.md` 和 archive 标签，保证脚本分类与真实状态一致。DoD：inventory 覆盖全部顶层脚本；验证：治理单测；风险：清单与实际文件漂移。
- [x] 4.3 清理并忽略本地临时目录、调试截图、浏览器 profile 与 `tmp_*` 文件。DoD：工作区不再出现明显临时噪音；验证：`git status`；风险：误删用户需要保留的人工报告。

## 5. 验证与收口

- [x] 5.1 为前端边界、API shim、脚本治理补齐静态或单测覆盖。DoD：新增测试覆盖本 change 触及的边界；验证：`pytest`；风险：测试只验证字符串存在，不验证真实调用关系。
- [x] 5.2 统一运行本 change 的最小验证集合：前端 `node --check`、治理/边界测试、`V10.1` 回归快照。DoD：所有检查通过；验证：命令输出与回归指标记录；风险：验证集过窄遗漏隐蔽问题。

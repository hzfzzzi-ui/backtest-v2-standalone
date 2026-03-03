## Context

经过 explore 模式的深度代码分析，发现代码库中约 29% 是死代码（~6,500 行），两个核心文件超过 2,000 行，且存在函数重复定义。三阶段清理：Phase 1 删除死代码、Phase 2 拆分巨型文件、Phase 3 去重。

当前活跃调用链（不可触碰）：
```
前端 → API routes (backtest_v2.py)
         → experiment_runner.py
           → portfolio_builder.py
             → portfolio_simulator_strict.py (engine_vector)
         → backtest_v2_artifacts.py
           → symbol_performance.py (analytics)
```

## Goals / Non-Goals

**Goals:**
- 删除所有零引用文件和函数，减少 ~4,500 行死代码
- 将 `backtest_v2.py`（2346 行）拆分为 7 个模块，主文件 ≤ 800 行
- 将 `backtest_v2.js`（2651 行）拆分为 6 个模块，主文件 ≤ 600 行
- 消除 `sanitize_json` 和 `_results_root` 的重复定义

**Non-Goals:**
- 不改变任何 API 路由路径或请求/响应格式
- 不重构业务逻辑（引擎、策略、产物协议）
- 不添加新功能或新测试
- 不迁移前端到 ES modules / bundler（保持 `<script>` 标签方式）

## Decisions

### D1: 后端拆分使用 FastAPI sub-router 模式

**选择：** 每个子模块创建自己的 `sub_router = APIRouter()`，主文件通过 `router.include_router(sub_router)` 注册。

**备选方案：** 保持单一 router，只提取辅助函数。
**理由：** Sub-router 模式让路由定义和处理函数在同一文件中，更符合"高内聚"原则。同时 FastAPI 的 `include_router` 支持 prefix/tags，方便未来按功能分组。

### D2: 前端保持全局函数模式，不引入模块系统

**选择：** 拆分为多个 `<script>` 文件，函数通过全局作用域共享。

**备选方案：** 使用 ES modules (`import/export`)。
**理由：** 当前项目无 bundler（Vite/webpack），浏览器原生 ES module 对 CORS 有要求，Docker 内静态文件服务可能需要额外配置。保持简单 `<script>` 标签是最低风险的拆分方式。全局 `state` 对象由主文件定义，其他模块通过参数或直接访问 `window.state`。

### D3: 执行顺序 — Phase 1 先于 Phase 2

**选择：** 先删死代码，再拆分文件。

**理由：** 先删 630 行孤立函数让 `backtest_v2.py` 从 2346 行降到 ~1716 行，拆分时代码量更小、边界更清晰。如果先拆分再删除，需要在多个新文件中分别定位和删除死代码。

### D4: _utils.py 承担去重职责

**选择：** `sanitize_json` 在 `_utils.py` 中定义一次，`backtest_v2.py` 和 `backtest_v2_artifacts.py` 都从此处 import。使用 `backtest_v2.py` 中更完整的版本（支持 Decimal 和 numpy）。

**备选方案：** 在 `backtest_v2_artifacts.py` 中保留独立版本。
**理由：** 两个版本语义相同但实现略有差异（artifacts 版不处理 Decimal），统一到完整版可避免未来漂移。

### D5: 前端 report.js 最先拆出

**选择：** `generateReport()` 是最自包含的模块（零外部 state 依赖），作为第一个拆出的 JS 模块。

**理由：** 降低拆分风险 — 如果这个最独立的模块拆出后没问题，说明全局函数共享模式可行。

## Risks / Trade-offs

- **[import 路径错误]** → 每个子模块拆出后立即 Docker rebuild + curl 测试全部路由
- **[JS 全局函数顺序依赖]** → `<script>` 标签严格按依赖顺序排列：api-client → ui-controls → charts → artifacts → report → main
- **[registry.py 中 sma_cross_multifactor 的 raise]** → 删除文件后需同步删除 registry 中的对应分支（如有）
- **[analytics/__init__.py 可能有 re-export]** → 已确认 `__init__.py` 为空文件，无 re-export 风险

## Open Questions

（无 — explore 阶段已充分验证所有依赖链）

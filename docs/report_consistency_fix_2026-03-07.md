# 报告口径一致性修复说明（2026-03-07）

## 变更背景

本次修复针对回测报告出现的三类问题：
- 报告区间/基准/标的数量与实际运行配置不一致；
- 服务端 `report.html` 出现中文乱码；
- BREAKOUT 策略摘要展示 MA 参数，导致策略语义错误。

对应 OpenSpec change：`v2-report-consistency-fix`。

## 生效范围

- 后端报告生成：`backend/core/report/report_generator.py`
- 产物稳定化与 run_meta 写入：`backend/api/endpoints/backtest_v2_artifacts.py`
- 前端本地报告兜底：`frontend/assets/js/report.js`
- 回归检查脚本：`backend/scripts/report_consistency_check.py`

## 口径合同（摘要）

1. 区间/基准来源优先级：
- `run_config.json.universe`
- `config.overrides.original_workbench_config.universe`
- `run_meta.data`

2. 标的数量来源优先级：
- `run_meta.universe.raw_count`
- `run_meta.universe.after_filters_symbols`
- 配置层 symbols 数量

3. 绩效口径：
- 统一使用 `perf.json`

4. 漏斗口径：
- 优先 `funnel.csv`
- 缺失时回退 `run_meta.counters`

5. 冲突可观测：
- `run_meta.report_consistency` 增加 `sources/fallbacks/config_source/config_conflict_policy`

## 与 legacy 结果差异

- 历史实验目录中已存在的 `run_meta.json` 可能仍是旧口径，不含 `report_consistency`。
- 新口径对旧实验可通过重新执行 `ensure_standard_artifacts` 或重跑实验生效。
- 报告展示优先级已在 `report_generator.py` 修复，即使旧 `run_meta.data` 不正确，报告仍会优先读取 `run_config` 并展示正确区间。

## 复现与验证

### 1) 重建单个实验报告

```bash
python -c "from backend.core.report.report_generator import generate_report; print(generate_report('outputs/experiments/exp_20260306_211811'))"
```

### 2) 运行一致性检查

```bash
python -m backend.scripts.report_consistency_check
```

检查产物：`docs/report_consistency_check_2026-03-07.csv`

## 已知限制

- 若运行服务仍是旧容器镜像，API 直接产出的 `run_meta` 仍可能是旧逻辑；需确保部署加载本次代码。
- 前端本地报告为后端报告兜底，优先建议使用后端 `report.html` 作为最终归档版本。

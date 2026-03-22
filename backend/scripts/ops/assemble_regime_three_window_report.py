from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class WindowBundle:
    summary_path: Path
    window_key: str
    label: str
    mode: str


DEFAULT_BUNDLES: tuple[WindowBundle, ...] = (
    WindowBundle(
        summary_path=ROOT / "outputs" / "ops" / "compare_regime_2016_2026_full_20260320" / "summary.json",
        window_key="2016_2026",
        label="2016-2026",
        mode="full_experiment",
    ),
    WindowBundle(
        summary_path=ROOT / "outputs" / "ops" / "compare_regime_2007_2017_full_20260320" / "summary.json",
        window_key="2007_2017",
        label="2007-2017",
        mode="full_experiment",
    ),
    WindowBundle(
        summary_path=ROOT / "outputs" / "ops" / "compare_regime_2007_2026_lightweight_20260320" / "summary.json",
        window_key="2007_2026",
        label="2007-2026",
        mode="state_only",
    ),
)

DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "ops" / "compare_regime_engines_three_windows_apply_20260320"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_json_map(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["state_day_counts"] = _parse_json_map(str(row.get("state_day_counts_json") or ""))
    item["trade_mode_day_counts"] = _parse_json_map(str(row.get("trade_mode_day_counts_json") or ""))
    item["transition_reason_counts"] = _parse_json_map(str(row.get("transition_reason_counts_json") or ""))
    item["switch_count"] = int(row.get("switch_count") or 0)
    item["transition_event_count"] = int(row.get("transition_event_count") or 0)
    item["low_confidence_days"] = int(row.get("low_confidence_days") or 0)
    item["feature_unavailable_days"] = int(row.get("feature_unavailable_days") or 0)
    item["regime_confidence_mean"] = float(row.get("regime_confidence_mean") or 0.0)
    item["low_confidence_ratio"] = float(row.get("low_confidence_ratio") or 0.0)
    return item


def _load_bundles(bundles: tuple[WindowBundle, ...]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    deltas: list[dict[str, Any]] = []
    for bundle in bundles:
        payload = _read_json(bundle.summary_path)
        bundle_rows = [_normalize_row(row) for row in payload.get("rows", [])]
        bundle_deltas = [dict(row) for row in payload.get("delta_rows", [])]
        rows.extend(bundle_rows)
        deltas.extend(bundle_deltas)
    return rows, deltas


def _find_engine(rows: list[dict[str, Any]], window_key: str, engine: str) -> dict[str, Any]:
    for row in rows:
        if row.get("window_key") == window_key and row.get("regime_engine") == engine:
            return row
    raise KeyError(f"missing row for window={window_key}, engine={engine}")


def _build_summary(rows: list[dict[str, Any]], deltas: list[dict[str, Any]]) -> dict[str, Any]:
    windows: list[dict[str, Any]] = []
    for bundle in DEFAULT_BUNDLES:
        legacy = _find_engine(rows, bundle.window_key, "ma200_legacy")
        formal = _find_engine(rows, bundle.window_key, "market_regime_framework")
        delta = next((row for row in deltas if row.get("window_key") == bundle.window_key), {})
        windows.append(
            {
                "window_key": bundle.window_key,
                "window_label": bundle.label,
                "mode": bundle.mode,
                "legacy": {
                    "exp_id": legacy.get("exp_id"),
                    "switch_count": legacy["switch_count"],
                    "transition_event_count": legacy["transition_event_count"],
                    "low_confidence_days": legacy["low_confidence_days"],
                    "feature_unavailable_days": legacy["feature_unavailable_days"],
                    "regime_confidence_mean": legacy["regime_confidence_mean"],
                    "latest_state": legacy.get("latest_state"),
                    "latest_trade_mode": legacy.get("latest_trade_mode"),
                },
                "formal": {
                    "exp_id": formal.get("exp_id"),
                    "switch_count": formal["switch_count"],
                    "transition_event_count": formal["transition_event_count"],
                    "low_confidence_days": formal["low_confidence_days"],
                    "feature_unavailable_days": formal["feature_unavailable_days"],
                    "regime_confidence_mean": formal["regime_confidence_mean"],
                    "latest_state": formal.get("latest_state"),
                    "latest_trade_mode": formal.get("latest_trade_mode"),
                },
                "delta": {
                    "switch_count": int(delta.get("delta_switch_count") or 0),
                    "transition_event_count": int(delta.get("delta_transition_event_count") or 0),
                    "low_confidence_days": int(delta.get("delta_low_confidence_days") or 0),
                    "feature_unavailable_days": int(delta.get("delta_feature_unavailable_days") or 0),
                    "regime_confidence_mean": float(delta.get("delta_regime_confidence_mean") or 0.0),
                },
            }
        )
    return {
        "generated_at": datetime.now().isoformat(),
        "comparison_name": "upgrade_market_regime_framework_apply_report",
        "windows": windows,
        "recommendation": {
            "default_engine": "ma200_legacy",
            "formal_framework_status": "shadow_or_opt_in_only",
            "rollback_engine": "ma200_legacy",
        },
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_comparison_csv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for bundle in DEFAULT_BUNDLES:
        for engine in ("ma200_legacy", "market_regime_framework"):
            row = _find_engine(rows, bundle.window_key, engine)
            output.append(
                {
                    "window_key": bundle.window_key,
                    "window_label": bundle.label,
                    "compare_mode": row.get("compare_mode"),
                    "regime_engine": engine,
                    "exp_id": row.get("exp_id"),
                    "switch_count": row["switch_count"],
                    "transition_event_count": row["transition_event_count"],
                    "low_confidence_days": row["low_confidence_days"],
                    "low_confidence_ratio": row["low_confidence_ratio"],
                    "feature_unavailable_days": row["feature_unavailable_days"],
                    "regime_confidence_mean": f"{row['regime_confidence_mean']:.6f}",
                    "latest_state": row.get("latest_state"),
                    "latest_trade_mode": row.get("latest_trade_mode"),
                    "state_day_counts_json": json.dumps(row["state_day_counts"], ensure_ascii=False, sort_keys=True),
                    "trade_mode_day_counts_json": json.dumps(row["trade_mode_day_counts"], ensure_ascii=False, sort_keys=True),
                    "transition_reason_counts_json": json.dumps(row["transition_reason_counts"], ensure_ascii=False, sort_keys=True),
                }
            )
    return output


def _build_delta_csv_rows(deltas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for bundle in DEFAULT_BUNDLES:
        delta = next(row for row in deltas if row.get("window_key") == bundle.window_key)
        output.append(
            {
                "window_key": bundle.window_key,
                "window_label": bundle.label,
                "delta_switch_count": int(delta.get("delta_switch_count") or 0),
                "delta_transition_event_count": int(delta.get("delta_transition_event_count") or 0),
                "delta_low_confidence_days": int(delta.get("delta_low_confidence_days") or 0),
                "delta_feature_unavailable_days": int(delta.get("delta_feature_unavailable_days") or 0),
                "delta_regime_confidence_mean": f"{float(delta.get('delta_regime_confidence_mean') or 0.0):.6f}",
            }
        )
    return output


def _report_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Regime Framework Three-Window Apply Report",
        "",
        "## 结论",
        "",
        "- 这是一页 regime 框架切换审计，不是策略 alpha 排名页。",
        "- `market_regime_framework` 在三个窗口里都显著提高了状态切换次数；`2007-2026` 全周期还暴露出明显的低置信度与 feature-unavailable 天数。",
        "- 当前更合理的动作是：保留 `ma200_legacy` 为默认主线，把正式框架限制为 shadow / opt-in 研究模式。",
        "",
        "## 三窗口总览",
        "",
        "| Window | Mode | Legacy Switch | Formal Switch | dSwitch | Formal LowConf | Formal FeatureUnavailable | Formal MeanConf |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary["windows"]:
        formal = item["formal"]
        legacy = item["legacy"]
        delta = item["delta"]
        lines.append(
            f"| {item['window_label']} | `{item['mode']}` | {legacy['switch_count']} | {formal['switch_count']} | "
            f"{delta['switch_count']} | {formal['low_confidence_days']} | {formal['feature_unavailable_days']} | "
            f"{formal['regime_confidence_mean']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- `2016-2026`：正式框架切换次数由 `99` 提高到 `310`，主开发窗口已能稳定跑通，但切换明显更激进。",
            "- `2007-2017`：正式框架切换次数由 `122` 提高到 `310`，硬门槛窗口同样可复现，但早期窗口没有显示出更平稳的状态机行为。",
            "- `2007-2026`：全周期使用 `state_only` 轻量审计，以避免 full experiment OOM；在这个口径下，正式框架出现 `2055` 个低置信度日和 `219` 个 feature-unavailable 日。",
            "",
            "## 切换建议",
            "",
            "- 默认继续使用 `ma200_legacy`。",
            "- `market_regime_framework` 仅用于 shadow / opt-in 研究，继续收敛 persistence、confidence_floor 与 feature availability。",
            "- 当正式框架至少满足：全周期低置信度占比明显下降、切换次数收敛、feature-unavailable 天数可解释，才建议考虑替换默认主线。",
            "",
            "## 回退方案",
            "",
            "- 配置层将 `regime_engine.engine` 设回 `ma200_legacy`。",
            "- 保留当前 artifacts 中的扩展字段，但前端默认继续展示 legacy 语义。",
            "- 研究工作台继续保留正式框架参数面板，只作为显式 opt-in 功能，不作为默认入口。",
        ]
    )
    return "\n".join(lines) + "\n"


def _switch_recommendation_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Switch Recommendation",
            "",
            "## Recommendation",
            "",
            "- 默认主线：继续使用 `ma200_legacy`。",
            "- 新框架：`market_regime_framework` 仅用于 shadow / opt-in 试运行。",
            "",
            "## Facts",
            "",
            "- `2016-2026`：formal switch `310` vs legacy `99`。",
            "- `2007-2017`：formal switch `310` vs legacy `122`。",
            "- `2007-2026`：formal switch `586` vs legacy `216`，formal low confidence `2055` days，feature unavailable `219` days。",
            "",
            "## Why not switch now",
            "",
            "- 全周期仍存在较高的低置信度占比，说明 persistence / confidence 规则尚未稳定。",
            "- formal 框架当前对 feature availability 更敏感，默认替换会把 fallback 风险带入主线。",
            "- 主开发窗口已可运行，但尚不足以覆盖硬门槛窗口与全周期切换稳定性要求。",
            "",
            "## Rollback",
            "",
            "- 将 `regime_engine.engine` 设置为 `ma200_legacy`。",
            "- 前端继续保留 legacy 图例与兼容入口。",
            "- 研究层保留 formal 审计产物，不影响正式主线。",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    rows, deltas = _load_bundles(DEFAULT_BUNDLES)
    summary = _build_summary(rows, deltas)

    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(
        output_dir / "window_regime_comparison.csv",
        _build_comparison_csv_rows(rows),
        [
            "window_key",
            "window_label",
            "compare_mode",
            "regime_engine",
            "exp_id",
            "switch_count",
            "transition_event_count",
            "low_confidence_days",
            "low_confidence_ratio",
            "feature_unavailable_days",
            "regime_confidence_mean",
            "latest_state",
            "latest_trade_mode",
            "state_day_counts_json",
            "trade_mode_day_counts_json",
            "transition_reason_counts_json",
        ],
    )
    _write_csv(
        output_dir / "window_regime_delta.csv",
        _build_delta_csv_rows(deltas),
        [
            "window_key",
            "window_label",
            "delta_switch_count",
            "delta_transition_event_count",
            "delta_low_confidence_days",
            "delta_feature_unavailable_days",
            "delta_regime_confidence_mean",
        ],
    )
    (output_dir / "report.md").write_text(_report_markdown(summary), encoding="utf-8")
    (output_dir / "switch_recommendation.md").write_text(_switch_recommendation_markdown(summary), encoding="utf-8")


if __name__ == "__main__":
    main()

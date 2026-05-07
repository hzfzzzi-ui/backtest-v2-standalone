from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class FactorStudySource:
    family: str
    study_id: str
    variant_name: str
    use_mode: str


WINDOW_KEYS: tuple[str, ...] = ("1217", "1222", "1226")

STOCK_SLEEVE_SOURCES: tuple[FactorStudySource, ...] = (
    FactorStudySource(
        family="stock_alpha",
        study_id="factors/stock_alpha_factor_real_mainline_s1",
        variant_name="B0_EQUAL",
        use_mode="rank_long",
    ),
    FactorStudySource(
        family="moneyflow",
        study_id="factors/moneyflow_factor_real_mainline_s2",
        variant_name="A_H20_CONTROL",
        use_mode="rank_long",
    ),
    FactorStudySource(
        family="positive_quality",
        study_id="factors/positive_quality_factor_real_mainline_s1",
        variant_name="B0_EQUAL",
        use_mode="rank_long",
    ),
    FactorStudySource(
        family="industry_second_stage",
        study_id="factors/industry_second_stage_factor_real_mainline_s1",
        variant_name="B0_EQUAL",
        use_mode="rank_long",
    ),
    FactorStudySource(
        family="negative_conditional_context",
        study_id="factors/negative_conditional_context_real_mainline_s1",
        variant_name="B0_EQUAL",
        use_mode="veto_high",
    ),
    FactorStudySource(
        family="risk_gate",
        study_id="factors/risk_gate_factor_real_mainline_s1",
        variant_name="B0_EQUAL",
        use_mode="veto_high",
    ),
    FactorStudySource(
        family="execution_pressure",
        study_id="factors/execution_pressure_factor_real_mainline_s1",
        variant_name="B0_EQUAL",
        use_mode="veto_high",
    ),
    FactorStudySource(
        family="exit_fragility",
        study_id="factors/exit_fragility_factor_real_mainline_s1",
        variant_name="B0_EQUAL",
        use_mode="veto_high",
    ),
    FactorStudySource(
        family="stock_lifecycle_fragility",
        study_id="factors/stock_lifecycle_fragility_real_mainline_s1",
        variant_name="B0_EQUAL",
        use_mode="veto_high",
    ),
    FactorStudySource(
        family="final_score_composition",
        study_id="factors/final_score_composition_real_mainline_s1",
        variant_name="B0_EQUAL",
        use_mode="rank_long",
    ),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _analysis_path(source: FactorStudySource, *, window_key: str) -> Path:
    parts = [part for part in source.study_id.replace("\\", "/").split("/") if part]
    return (
        _repo_root()
        / "outputs"
        / "studies"
        / Path(*parts)
        / window_key
        / source.variant_name
        / "machine"
        / "analysis.json"
    ).resolve()


def _load_analysis(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("analysis"), dict):
        return dict(payload["analysis"])
    return dict(payload)


def _factor_rows(analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    single_factor = analysis.get("single_factor")
    if isinstance(single_factor, dict):
        return {str(key): dict(value or {}) for key, value in single_factor.items()}
    factors = analysis.get("factors")
    if isinstance(factors, dict):
        return {str(key): dict(value or {}) for key, value in factors.items()}
    return {}


def _flatten_factor_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, dict) and key.startswith("horizon_"):
            horizon = key.removeprefix("horizon_")
            for subkey, subvalue in value.items():
                flat[f"{subkey}_{horizon}"] = subvalue
        else:
            flat[key] = value
    return flat


def _infer_analysis_style(metrics: dict[str, Any]) -> str:
    if any(key.startswith("horizon_") and isinstance(value, dict) for key, value in metrics.items()):
        return "veto_surface"
    if any(
        key.startswith("mean_observation_ic_")
        or key.startswith("mean_top_bottom_spread_")
        or key in {"mean_daily_ic", "ic_ir"}
        for key in metrics
    ):
        return "rank_surface"
    return "unknown"


def _choose_rank_primary(flat: dict[str, Any]) -> tuple[str | None, Any, str | None, Any, int | None]:
    ranked_candidates: tuple[tuple[str, str | None, int | None], ...] = (
        ("mean_observation_ic_20d", "mean_top_bottom_spread_20d", 20),
        ("mean_observation_ic_10d", "mean_top_bottom_spread_10d", 10),
        ("mean_observation_ic_5d", "mean_top_bottom_spread_5d", 5),
        ("mean_observation_ic_1d", "mean_top_bottom_spread_1d", 1),
        ("mean_daily_ic", "mean_top_bottom_spread_1d", 1),
        ("mean_top_bottom_spread_20d", None, 20),
        ("mean_top_bottom_spread_10d", None, 10),
        ("mean_top_bottom_spread_5d", None, 5),
        ("mean_top_bottom_spread_1d", None, 1),
    )
    for primary_name, secondary_name, horizon_days in ranked_candidates:
        primary_value = flat.get(primary_name)
        if primary_value is None or pd.isna(primary_value):
            continue
        secondary_value = flat.get(secondary_name) if secondary_name else None
        if secondary_value is not None and pd.isna(secondary_value):
            secondary_value = None
        return primary_name, primary_value, secondary_name, secondary_value, horizon_days
    return None, None, None, None, None


def _choose_veto_primary(flat: dict[str, Any]) -> tuple[str | None, Any, str | None, Any, int | None]:
    ranked_candidates: tuple[tuple[str, str | None, int | None], ...] = (
        ("veto_top20_improvement_20d", "high20_mean_return_20d", 20),
        ("veto_top20_improvement_10d", "high20_mean_return_10d", 10),
        ("veto_top20_improvement_5d", "high20_mean_return_5d", 5),
        ("veto_top20_improvement_1d", "high20_mean_return_1d", 1),
        ("score_forward_corr_20d", "top20_mean_forward_return_20d", 20),
        ("score_forward_corr_10d", "top20_mean_forward_return_10d", 10),
        ("score_forward_corr_5d", "top20_mean_forward_return_5d", 5),
    )
    for primary_name, secondary_name, horizon_days in ranked_candidates:
        primary_value = flat.get(primary_name)
        if primary_value is None or pd.isna(primary_value):
            continue
        secondary_value = flat.get(secondary_name) if secondary_name else None
        if secondary_value is not None and pd.isna(secondary_value):
            secondary_value = None
        return primary_name, primary_value, secondary_name, secondary_value, horizon_days
    return None, None, None, None, None


def _build_window_matrix() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source in STOCK_SLEEVE_SOURCES:
        for window_key in WINDOW_KEYS:
            path = _analysis_path(source, window_key=window_key)
            analysis = _load_analysis(path)
            for factor_id, metrics in _factor_rows(analysis).items():
                flat = _flatten_factor_metrics(metrics)
                analysis_style = _infer_analysis_style(metrics)
                if source.use_mode == "rank_long":
                    primary_name, primary_value, secondary_name, secondary_value, primary_horizon = _choose_rank_primary(flat)
                else:
                    primary_name, primary_value, secondary_name, secondary_value, primary_horizon = _choose_veto_primary(flat)
                row: dict[str, Any] = {
                    "family": source.family,
                    "study_id": source.study_id,
                    "variant_name": source.variant_name,
                    "window_key": window_key,
                    "factor_id": factor_id,
                    "use_mode": source.use_mode,
                    "analysis_style": analysis_style,
                    "primary_metric_name": primary_name,
                    "primary_metric_value": primary_value,
                    "secondary_metric_name": secondary_name,
                    "secondary_metric_value": secondary_value,
                    "primary_horizon_days": primary_horizon,
                }
                row.update(flat)
                rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    duplicate_counts = frame.groupby("factor_id")["family"].nunique().rename("factor_id_family_count")
    frame = frame.merge(duplicate_counts, on="factor_id", how="left")
    frame["is_projection_family"] = frame["family"].eq("final_score_composition")
    return frame.sort_values(["family", "factor_id", "window_key"]).reset_index(drop=True)


def _build_stability_matrix(window_matrix: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if window_matrix.empty:
        return pd.DataFrame(rows)
    grouped = window_matrix.groupby(["family", "factor_id", "use_mode", "analysis_style"], sort=True)
    for (family, factor_id, use_mode, analysis_style), group in grouped:
        window_lookup = {str(row["window_key"]): row for row in group.to_dict("records")}
        ordered_values = [window_lookup.get(window_key, {}).get("primary_metric_value") for window_key in WINDOW_KEYS]
        non_null_values = [value for value in ordered_values if value is not None and not pd.isna(value)]
        positive_count = sum(1 for value in non_null_values if value > 0)
        negative_count = sum(1 for value in non_null_values if value < 0)
        if not non_null_values:
            direction = "no_signal"
        elif positive_count == len(non_null_values):
            direction = "positive"
        elif negative_count == len(non_null_values):
            direction = "negative"
        else:
            direction = "mixed"
        row: dict[str, Any] = {
            "family": family,
            "factor_id": factor_id,
            "use_mode": use_mode,
            "analysis_style": analysis_style,
            "study_id": str(group.iloc[0]["study_id"]),
            "variant_name": str(group.iloc[0]["variant_name"]),
            "factor_id_family_count": int(group.iloc[0]["factor_id_family_count"]),
            "is_projection_family": bool(group.iloc[0]["is_projection_family"]),
            "window_count": int(len(group)),
            "non_null_primary_window_count": int(len(non_null_values)),
            "positive_window_count": int(positive_count),
            "negative_window_count": int(negative_count),
            "direction": direction,
            "mean_primary_metric": float(sum(non_null_values) / len(non_null_values)) if non_null_values else None,
            "current_primary_metric_name": window_lookup.get("1226", {}).get("primary_metric_name"),
            "current_primary_metric_value": window_lookup.get("1226", {}).get("primary_metric_value"),
        }
        for window_key in WINDOW_KEYS:
            window_row = window_lookup.get(window_key, {})
            row[f"primary_metric_name_{window_key}"] = window_row.get("primary_metric_name")
            row[f"primary_metric_value_{window_key}"] = window_row.get("primary_metric_value")
            row[f"secondary_metric_name_{window_key}"] = window_row.get("secondary_metric_name")
            row[f"secondary_metric_value_{window_key}"] = window_row.get("secondary_metric_value")
            row[f"coverage_ratio_{window_key}"] = window_row.get("coverage_ratio")
        rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(["family", "current_primary_metric_value", "factor_id"], ascending=[True, False, True]).reset_index(drop=True)


def _top_lines(stability: pd.DataFrame, *, use_mode: str, title: str) -> list[str]:
    subset = stability.loc[
        stability["use_mode"].eq(use_mode)
        & stability["current_primary_metric_value"].notna()
    ].copy()
    if subset.empty:
        return [f"## {title}", "", "- no data", ""]
    subset = subset.sort_values(
        ["positive_window_count", "current_primary_metric_value", "mean_primary_metric"],
        ascending=[False, False, False],
    ).head(10)
    lines = [f"## {title}", ""]
    for _, row in subset.iterrows():
        lines.append(
            "- `{family}/{factor_id}`: 1226 `{metric}`=`{value:.6f}`, "
            "mean=`{mean_value:.6f}`, direction=`{direction}`, positive_windows=`{positive_windows}`".format(
                family=row["family"],
                factor_id=row["factor_id"],
                metric=row["current_primary_metric_name"],
                value=float(row["current_primary_metric_value"]),
                mean_value=float(row["mean_primary_metric"]) if row["mean_primary_metric"] is not None else float("nan"),
                direction=row["direction"],
                positive_windows=int(row["positive_window_count"]),
            )
        )
    lines.append("")
    return lines


def _write_human_summary(path: Path, *, meta: dict[str, Any], stability: pd.DataFrame) -> None:
    lines = [
        "# Stock Sleeve 单因子分析矩阵",
        "",
        "## 结论",
        "",
        "这份矩阵统一汇总了当前 active A 股 stock sleeve factor studies 的单因子输出，",
        "但它不是一张“所有因子都完全同口径可直接排序”的表。",
        "",
        "- `rank_long` 家族主要看 IC / spread",
        "- `veto_high` 家族主要看 veto_top20_improvement 或 pressure corr",
        "- `moneyflow` 当前采用 `moneyflow_factor_real_mainline_s2/A_H20_CONTROL`，不是旧的 `s1`",
        "- `stock_alpha` 当前仍是 `1d` 输出，其它多数 family 带 `5/10/20d`",
        "",
        "## 规模",
        "",
        f"- families: `{meta['family_count']}`",
        f"- family-factor rows: `{meta['family_factor_count']}`",
        f"- unique factor ids: `{meta['unique_factor_id_count']}`",
        f"- factor-window rows: `{meta['factor_window_row_count']}`",
        "",
    ]
    lines.extend(_top_lines(stability, use_mode="rank_long", title="Rank Long Top 10"))
    lines.extend(_top_lines(stability, use_mode="veto_high", title="Veto High Top 10"))
    mixed = stability.loc[stability["direction"].eq("mixed")].copy()
    lines.extend(["## Mixed Direction Watchlist", ""])
    if mixed.empty:
        lines.append("- none")
    else:
        mixed = mixed.sort_values(["family", "factor_id"]).head(15)
        for _, row in mixed.iterrows():
            lines.append(
                "- `{family}/{factor_id}`: 1217=`{v1217}`, 1222=`{v1222}`, 1226=`{v1226}`".format(
                    family=row["family"],
                    factor_id=row["factor_id"],
                    v1217=row["primary_metric_value_1217"],
                    v1222=row["primary_metric_value_1222"],
                    v1226=row["primary_metric_value_1226"],
                )
            )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _output_root() -> Path:
    return (_repo_root() / "outputs" / "studies" / "factors" / "stock_sleeve_single_factor_matrix").resolve()


def build_stock_sleeve_single_factor_matrix(*, write_outputs: bool = True) -> dict[str, Any]:
    window_matrix = _build_window_matrix()
    stability_matrix = _build_stability_matrix(window_matrix)
    meta = {
        "family_count": len(STOCK_SLEEVE_SOURCES),
        "family_factor_count": int(len(stability_matrix)),
        "unique_factor_id_count": int(window_matrix["factor_id"].nunique()) if not window_matrix.empty else 0,
        "factor_window_row_count": int(len(window_matrix)),
        "window_keys": list(WINDOW_KEYS),
        "source_studies": [
            {
                "family": source.family,
                "study_id": source.study_id,
                "variant_name": source.variant_name,
                "use_mode": source.use_mode,
            }
            for source in STOCK_SLEEVE_SOURCES
        ],
    }
    output_refs: dict[str, str] = {}
    if write_outputs:
        root = _output_root()
        machine_dir = (root / "machine").resolve()
        human_dir = (root / "human").resolve()
        machine_dir.mkdir(parents=True, exist_ok=True)
        human_dir.mkdir(parents=True, exist_ok=True)
        window_matrix_csv = machine_dir / "factor_window_matrix.csv"
        stability_matrix_csv = machine_dir / "factor_stability_matrix.csv"
        meta_json = machine_dir / "summary.json"
        summary_md = human_dir / "summary.md"
        window_matrix.to_csv(window_matrix_csv, index=False, encoding="utf-8-sig")
        stability_matrix.to_csv(stability_matrix_csv, index=False, encoding="utf-8-sig")
        meta_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_human_summary(summary_md, meta=meta, stability=stability_matrix)
        output_refs = {
            "window_matrix": str(window_matrix_csv),
            "stability_matrix": str(stability_matrix_csv),
            "summary_json": str(meta_json),
            "summary_md": str(summary_md),
        }
    return {
        "meta": meta,
        "window_matrix": window_matrix,
        "stability_matrix": stability_matrix,
        "output_refs": output_refs,
    }


def main() -> None:
    result = build_stock_sleeve_single_factor_matrix(write_outputs=True)
    meta = result["meta"]
    print(
        "built stock sleeve single-factor matrix: "
        f"families={meta['family_count']} "
        f"family_factor_rows={meta['family_factor_count']} "
        f"window_rows={meta['factor_window_row_count']}"
    )


if __name__ == "__main__":
    main()

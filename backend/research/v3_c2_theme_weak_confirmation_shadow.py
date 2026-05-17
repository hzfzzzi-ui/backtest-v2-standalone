from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROUND_ID = "sr_20260511_v3_c2_theme_weak_confirmation_shadow"
STUDY_ID = "cn_stock_etf/v3_c2_theme_weak_confirmation_shadow_v1"
BASELINE_ID = "CN_STOCK_ETF_COMBO_BASELINE_V3"
VARIANT_NAME = "C2_THEME_WEAK_CONFIRMATION_SHADOW"

SOURCE_LOSS_AUDIT_DIR = Path("outputs/studies/cn_stock_etf/sr_20260511_v3_loss_top30_exit_reason_audit")
SOURCE_C1_DIR = Path("outputs/studies/cn_stock_etf/cn_stock_etf_theme_health_shadow_v1")
OUT_DIR = Path("outputs/studies/cn_stock_etf") / ROUND_ID
JOURNAL_PATH = Path("research/study_journal/rounds") / f"{ROUND_ID}.json"

WINDOWS = {
    "1626": ("2016-01-01", "2026-05-08"),
    "2020_2026": ("2020-01-01", "2026-05-08"),
    "2024_2026": ("2024-01-01", "2026-05-08"),
    "2025_2026": ("2025-01-01", "2026-05-08"),
    "2025_12_2026_04": ("2025-12-01", "2026-04-30"),
    "2026_03": ("2026-03-01", "2026-03-31"),
}

WEAK_MARKET_STATES = {"TRANS_DOWN", "RISK_OFF", "BEAR", "DEFENSIVE"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _abs(path: Path) -> Path:
    return (_repo_root() / path).resolve()


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(_abs(path), encoding="utf-8-sig", low_memory=False)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _fmt_pct(value: Any) -> str:
    num = _safe_float(value)
    return "-" if num is None else f"{num * 100:.2f}%"


def _fmt_money(value: Any) -> str:
    num = _safe_float(value)
    return "-" if num is None else f"{num:,.0f}"


def _md_cell(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).replace("\n", " ").replace("|", "\\|")


def _load_theme_health(window_key: str) -> pd.DataFrame:
    path = SOURCE_C1_DIR / window_key / "C1_THEME_HEALTH_SHADOW" / "machine" / "theme_health_daily.csv"
    frame = _read_csv(path)
    if frame.empty:
        return pd.DataFrame(columns=["date", "theme", "theme_health_label"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for col in ["theme_health_score", "weak_flag_count", "proxy_max_ret20", "proxy_max_ret60", "proxy_rank_pct"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    keep = [
        "date",
        "theme",
        "theme_health_label",
        "theme_health_score",
        "weak_flag_count",
        "proxy_available_bool",
        "theme_proxy",
        "proxy_max_ret20",
        "proxy_max_ret60",
        "proxy_rank_pct",
        "candidate_rows",
        "selected_rows",
        "candidate_visible_trailing_days",
        "held_examples",
    ]
    return frame.loc[:, [col for col in keep if col in frame.columns]].copy()


def _split_themes(theme_tags: Any) -> list[str]:
    if theme_tags is None or pd.isna(theme_tags):
        return []
    text = str(theme_tags).strip()
    if not text or text.lower() in {"nan", "none"} or text in {"未映射", "未分类", "无"}:
        return []
    for sep in ["，", "、", "；", ";", ","]:
        text = text.replace(sep, "|")
    out: list[str] = []
    for raw in text.split("|"):
        item = raw.strip()
        if item and item not in out and item.lower() not in {"nan", "none"} and item not in {"未映射", "未分类", "无"}:
            out.append(item)
    return out


def _build_health_lookup(health: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    if health.empty:
        return out
    frame = health.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"])
    frame["theme"] = frame["theme"].fillna("").astype(str).str.strip()
    frame = frame.loc[frame["theme"].ne("")]
    for theme, grp in frame.groupby("theme"):
        out[str(theme)] = grp.sort_values("date").reset_index(drop=True)
    return out


def _lookup_theme_record(
    health_lookup: dict[str, pd.DataFrame],
    theme: str,
    date_key: pd.Timestamp,
    *,
    max_lookback_days: int = 10,
) -> dict[str, Any] | None:
    history = health_lookup.get(theme)
    if history is None or history.empty:
        return None
    eligible = history.loc[history["date"] <= date_key]
    if eligible.empty:
        return None
    hit = eligible.iloc[-1].to_dict()
    asof_date = pd.Timestamp(hit.get("date")).normalize()
    lag_days = int((date_key - asof_date).days)
    if lag_days > max_lookback_days:
        return None
    hit["theme_evidence_asof_date"] = asof_date.strftime("%Y-%m-%d")
    hit["theme_evidence_lag_days"] = lag_days
    return hit


def _theme_evidence_for(row: pd.Series, health_lookup: dict[str, pd.DataFrame]) -> dict[str, Any]:
    themes = _split_themes(row.get("theme_tags"))
    if not themes:
        return {
            "theme_evidence_status": "no_theme_tag",
            "theme_weak_label": "no_theme_tag",
            "theme_weak_bool": False,
            "theme_watch_or_weak_bool": False,
            "theme_evidence": "",
            "theme_evidence_asof_date": "",
            "theme_evidence_lag_days": None,
        }

    date_key = pd.Timestamp(row["exit_date"]).normalize()
    priority = {"confirmed_weak": 3, "watch": 2, "healthy": 1}
    hits: list[dict[str, Any]] = []
    missing: list[str] = []
    for theme in themes:
        hit = _lookup_theme_record(health_lookup, theme, date_key)
        if hit is None:
            missing.append(theme)
            continue
        hits.append(hit)

    if not hits:
        return {
            "theme_evidence_status": "missing_theme_health",
            "theme_weak_label": "missing",
            "theme_weak_bool": False,
            "theme_watch_or_weak_bool": False,
            "theme_evidence": "; ".join(f"{theme}:missing" for theme in themes),
            "theme_evidence_asof_date": "",
            "theme_evidence_lag_days": None,
        }

    best = sorted(hits, key=lambda item: priority.get(str(item.get("theme_health_label")), 0), reverse=True)[0]
    label = str(best.get("theme_health_label") or "missing")
    parts: list[str] = []
    for hit in hits:
        parts.append(
            f"{hit.get('theme')}:{hit.get('theme_health_label')}"
            f"/asof={hit.get('theme_evidence_asof_date')}"
            f"/score={_safe_float(hit.get('theme_health_score'))}"
            f"/flags={_safe_float(hit.get('weak_flag_count'))}"
            f"/ret20={_fmt_pct(hit.get('proxy_max_ret20'))}"
        )
    for theme in missing:
        parts.append(f"{theme}:missing")

    return {
        "theme_evidence_status": "covered" if not missing else "partial",
        "theme_weak_label": label,
        "theme_weak_bool": label == "confirmed_weak",
        "theme_watch_or_weak_bool": label in {"confirmed_weak", "watch"},
        "theme_evidence": "; ".join(parts),
        "theme_evidence_asof_date": str(best.get("theme_evidence_asof_date") or ""),
        "theme_evidence_lag_days": _safe_float(best.get("theme_evidence_lag_days")),
    }


def _post_sell_outcome(row: pd.Series) -> str:
    post20 = _safe_float(row.get("stock_post_sell_20d_return"))
    post60 = _safe_float(row.get("stock_post_sell_60d_return"))
    if post20 is None and post60 is None:
        return "post_unknown"
    if (post20 is not None and post20 <= -0.02) or (post60 is not None and post60 <= -0.05):
        return "continued_weak"
    if (post20 is not None and post20 >= 0.05) or (post60 is not None and post60 >= 0.10):
        return "rebounded"
    return "neutral"


def _c2_verdict(row: pd.Series) -> str:
    outcome = str(row.get("post_sell_outcome"))
    if outcome == "post_unknown":
        return "inconclusive_no_post_data"
    if bool(row.get("stock_weak_bool")) and bool(row.get("theme_watch_or_weak_bool")) and outcome == "continued_weak":
        return "confirmed_exit_stock_theme_weak"
    if bool(row.get("stock_weak_bool")) and bool(row.get("industry_weak_bool")) and outcome == "continued_weak":
        return "confirmed_exit_stock_industry_weak"
    if not bool(row.get("stock_weak_bool")) and outcome == "continued_weak":
        return "protected_profit"
    if bool(row.get("theme_watch_or_weak_bool")) and outcome == "rebounded":
        return "mixed_theme_weak_but_rebounded"
    if bool(row.get("industry_weak_bool")) and outcome == "rebounded":
        return "mixed_industry_weak_but_rebounded"
    if not bool(row.get("industry_weak_bool")) and not bool(row.get("theme_watch_or_weak_bool")) and outcome == "rebounded":
        return "suspected_overkill_theme_not_weak"
    if outcome == "neutral":
        return "neutral_after_exit"
    return "inconclusive"


def _window_filter(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    dates = pd.to_datetime(frame["exit_date"], errors="coerce")
    return frame.loc[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))].copy()


def _group_summary(frame: pd.DataFrame, by: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, grp in frame.groupby(by, dropna=False):
        rows.append(
            {
                by: str(key),
                "count": int(len(grp)),
                "pnl_sum": float(grp["realized_pnl"].sum()),
                "avg_realized_return": float(pd.to_numeric(grp["realized_return"], errors="coerce").mean()),
                "continued_weak_count": int(grp["post_sell_outcome"].eq("continued_weak").sum()),
                "rebounded_count": int(grp["post_sell_outcome"].eq("rebounded").sum()),
                "neutral_count": int(grp["post_sell_outcome"].eq("neutral").sum()),
                "avg_post20": float(pd.to_numeric(grp["stock_post_sell_20d_return"], errors="coerce").mean()),
                "avg_post60": float(pd.to_numeric(grp["stock_post_sell_60d_return"], errors="coerce").mean()),
            }
        )
    return sorted(rows, key=lambda item: abs(float(item["pnl_sum"] or 0.0)), reverse=True)


def _summarize_rows(frame: pd.DataFrame, *, window_key: str) -> dict[str, Any]:
    if frame.empty:
        return {
            "window_key": window_key,
            "risk_off_exit_count": 0,
            "total_pnl": 0.0,
            "winning_exit_count": 0,
            "losing_exit_count": 0,
            "theme_evidence_coverage_ratio": 0.0,
            "market_state_weak_count": 0,
            "broad_indices_weak_count": 0,
            "industry_weak_count": 0,
            "theme_confirmed_weak_count": 0,
            "theme_watch_or_weak_count": 0,
            "stock_weak_count": 0,
            "post_outcome_summary": [],
            "verdict_summary": [],
            "theme_label_summary": [],
            "theme_summary": [],
            "industry_summary": [],
        }

    return {
        "window_key": window_key,
        "risk_off_exit_count": int(len(frame)),
        "total_pnl": float(frame["realized_pnl"].sum()),
        "winning_exit_count": int((frame["realized_pnl"] > 0).sum()),
        "losing_exit_count": int((frame["realized_pnl"] <= 0).sum()),
        "theme_evidence_coverage_ratio": float(frame["theme_evidence_status"].isin({"covered", "partial"}).mean()),
        "market_state_weak_count": int(frame["market_state_weak_bool"].sum()),
        "broad_indices_weak_count": int(frame["broad_indices_weak_bool"].sum()),
        "industry_weak_count": int(frame["industry_weak_bool"].sum()),
        "theme_confirmed_weak_count": int(frame["theme_weak_bool"].sum()),
        "theme_watch_or_weak_count": int(frame["theme_watch_or_weak_bool"].sum()),
        "stock_weak_count": int(frame["stock_weak_bool"].sum()),
        "post_outcome_summary": _group_summary(frame, "post_sell_outcome"),
        "verdict_summary": _group_summary(frame, "c2_verdict"),
        "theme_label_summary": _group_summary(frame, "theme_weak_label"),
        "theme_summary": _group_summary(frame, "theme_tags"),
        "industry_summary": _group_summary(frame, "sw_l1_industry"),
    }


def _build_shadow_for_window(risk_exits: pd.DataFrame, window_key: str, start: str, end: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    health = _load_theme_health(window_key)
    health_lookup = _build_health_lookup(health)
    frame = _window_filter(risk_exits, start, end).copy()
    if frame.empty:
        summary = _summarize_rows(frame, window_key=window_key)
        summary["theme_health_source_rows"] = int(len(health))
        summary["theme_health_source_window"] = window_key
        return frame, summary

    evidence_rows = frame.apply(lambda row: _theme_evidence_for(row, health_lookup), axis=1, result_type="expand")
    frame = pd.concat([frame.reset_index(drop=True), evidence_rows.reset_index(drop=True)], axis=1)

    numeric_cols = [
        "realized_pnl",
        "realized_return",
        "sse_return_holding",
        "hs300_return_holding",
        "zz500_return_holding",
        "chinext_return_holding",
        "industry_index_return_holding",
        "stock_post_sell_20d_return",
        "stock_post_sell_60d_return",
    ]
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    state = frame.get("exit_account_budget_effective_state_5", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["market_state_weak_bool"] = state.isin(WEAK_MARKET_STATES)

    broad_down_flags = []
    for col in ["sse_return_holding", "hs300_return_holding", "zz500_return_holding", "chinext_return_holding"]:
        if col in frame.columns:
            broad_down_flags.append(pd.to_numeric(frame[col], errors="coerce").lt(0).rename(col))
        else:
            broad_down_flags.append(pd.Series(False, index=frame.index, name=col))
    broad_down_count = pd.concat(broad_down_flags, axis=1).sum(axis=1)
    frame["broad_indices_down_count"] = broad_down_count
    frame["broad_indices_weak_bool"] = broad_down_count >= 3

    frame["industry_weak_bool"] = pd.to_numeric(frame.get("industry_index_return_holding"), errors="coerce").lt(0)
    frame["stock_weak_bool"] = pd.to_numeric(frame.get("realized_pnl"), errors="coerce").le(0)
    frame["post_sell_outcome"] = frame.apply(_post_sell_outcome, axis=1)
    frame["c2_verdict"] = frame.apply(_c2_verdict, axis=1)
    frame["c2_supports_exit_bool"] = frame["c2_verdict"].isin(
        {"confirmed_exit_stock_theme_weak", "confirmed_exit_stock_industry_weak", "protected_profit"}
    )
    frame["c2_suspected_overkill_bool"] = frame["c2_verdict"].isin(
        {"suspected_overkill_theme_not_weak", "mixed_theme_weak_but_rebounded", "mixed_industry_weak_but_rebounded"}
    )

    summary = _summarize_rows(frame, window_key=window_key)
    summary["theme_health_source_rows"] = int(len(health))
    summary["theme_health_source_window"] = window_key
    summary["theme_lookup_mode"] = "asof_on_or_before_exit_date_with_10_calendar_day_limit"
    return frame, summary


def _write_report(matrix: list[dict[str, Any]], detail_1626: pd.DataFrame, out_dir: Path) -> None:
    by_window = {item["window_key"]: item for item in matrix}
    main = by_window.get("1626", {})
    recent = by_window.get("2025_2026", {})

    lines: list[str] = []
    lines.append("# C2 主题转弱确认 Shadow")
    lines.append("")
    lines.append("## 结论")
    lines.append(
        f"- C2 只审计 V3 股票腿 `RISK_OFF_EXIT`，不改 NAV、仓位、卖出规则或 baseline。"
        f"主窗口 2016-2026 共 {main.get('risk_off_exit_count', 0)} 笔风险退出。"
    )
    lines.append(
        f"- 主窗口主题证据覆盖率 {main.get('theme_evidence_coverage_ratio', 0.0):.1%}；"
        f"theme confirmed weak {main.get('theme_confirmed_weak_count', 0)} 笔，"
        f"watch/weak {main.get('theme_watch_or_weak_count', 0)} 笔。"
    )
    lines.append(
        f"- 2025-2026 共 {recent.get('risk_off_exit_count', 0)} 笔风险退出，"
        f"主题证据覆盖率 {recent.get('theme_evidence_coverage_ratio', 0.0):.1%}。"
    )
    lines.append("- 事实结论：主题层可以辅助解释部分卖出，但当前不能单独升级为运行时卖出条件。")
    lines.append("- 推断结论：更值得推进的是 C3 反事实，专门测试“疑似误杀样本”是否适合延迟/分批退出。")
    lines.append("")
    lines.append("## 口径")
    lines.append("- 大盘弱：账户状态为 TRANS_DOWN/RISK_OFF/BEAR/DEFENSIVE；另记录四个宽基中至少 3 个为负的辅助标记。")
    lines.append("- 行业弱：卖出持仓期对应申万 L1 行业指数收益为负。")
    lines.append("- 主题弱：复用 C1 `theme_health_daily.csv`；`confirmed_weak` 为严格弱，`watch|confirmed_weak` 为宽口径弱。")
    lines.append("- 主题证据匹配：按卖出日向前取最近主题健康记录，最多回看 10 个自然日，避免卖出当日持仓已被清掉导致误判缺证。")
    lines.append("- 个股弱：该笔风险退出已实现盈亏 <= 0。")
    lines.append("- 卖后验证：卖后 20 日 <= -2% 或 60 日 <= -5% 为继续弱；卖后 20 日 >= 5% 或 60 日 >= 10% 为反弹。")
    lines.append("")
    lines.append("## 窗口摘要")
    lines.append("|窗口|风险退出|PnL|主题覆盖|主题 weak|主题 watch/weak|行业弱|个股弱|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for item in matrix:
        lines.append(
            f"|{item['window_key']}|{item.get('risk_off_exit_count', 0)}|{_fmt_money(item.get('total_pnl'))}|"
            f"{item.get('theme_evidence_coverage_ratio', 0.0):.1%}|{item.get('theme_confirmed_weak_count', 0)}|"
            f"{item.get('theme_watch_or_weak_count', 0)}|{item.get('industry_weak_count', 0)}|{item.get('stock_weak_count', 0)}|"
        )
    lines.append("")
    lines.append("## 主窗口 C2 Verdict")
    lines.append("|verdict|笔数|PnL|继续弱|反弹|卖后20日|卖后60日|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for row in main.get("verdict_summary", []):
        lines.append(
            f"|{row.get('c2_verdict')}|{row.get('count')}|{_fmt_money(row.get('pnl_sum'))}|"
            f"{row.get('continued_weak_count')}|{row.get('rebounded_count')}|"
            f"{_fmt_pct(row.get('avg_post20'))}|{_fmt_pct(row.get('avg_post60'))}|"
        )
    lines.append("")
    if not detail_1626.empty:
        candidates = detail_1626.loc[detail_1626["c2_suspected_overkill_bool"]].copy()
        candidates["abs_post20"] = pd.to_numeric(candidates["stock_post_sell_20d_return"], errors="coerce").abs()
        candidates = candidates.sort_values(["stock_post_sell_20d_return", "realized_pnl"], ascending=[False, True]).head(15)
        lines.append("## 疑似误杀样本")
        lines.append("|股票|卖出日|PnL|主题|行业|主题证据|卖后20日|卖后60日|verdict|")
        lines.append("|---|---|---:|---|---|---|---:|---:|---|")
        for row in candidates.itertuples(index=False):
            stock_label = f"{row.symbol} {getattr(row, 'name', '')}"
            lines.append(
                f"|{_md_cell(stock_label)}|{pd.Timestamp(row.exit_date).strftime('%Y-%m-%d')}|"
                f"{_fmt_money(row.realized_pnl)}|{_md_cell(getattr(row, 'theme_tags', ''))}|{_md_cell(getattr(row, 'sw_l1_industry', ''))}|"
                f"{_md_cell(getattr(row, 'theme_evidence', ''))}|{_fmt_pct(getattr(row, 'stock_post_sell_20d_return', None))}|"
                f"{_fmt_pct(getattr(row, 'stock_post_sell_60d_return', None))}|{getattr(row, 'c2_verdict', '')}|"
            )
        lines.append("")
    lines.append("## 决策")
    lines.append("- C2 保持 shadow，不进入 runtime。")
    lines.append("- 下一步建议做 C3：只对 `RISK_OFF_EXIT` 的疑似误杀样本做延迟/分批退出反事实审计。")
    lines.append("- 只有 C3 能跨窗口减少误杀且不显著放大亏损，才值得进入正式 AB。")

    human_dir = out_dir / "human"
    human_dir.mkdir(parents=True, exist_ok=True)
    (human_dir / "c2_theme_weak_confirmation_shadow.md").write_text("\n".join(lines), encoding="utf-8")


def _find_verdict(summary: dict[str, Any], verdict: str) -> dict[str, Any]:
    for row in summary.get("verdict_summary", []):
        if row.get("c2_verdict") == verdict:
            return row
    return {"count": 0, "pnl_sum": 0.0}


def _write_journal(summary: dict[str, Any]) -> None:
    now = summary["generated_at"]
    windows = {item["window_key"]: item for item in summary["windows"]}
    main = windows.get("1626", {})
    protected = _find_verdict(main, "protected_profit")
    overkill = _find_verdict(main, "suspected_overkill_theme_not_weak")
    mixed_industry = _find_verdict(main, "mixed_industry_weak_but_rebounded")

    journal = {
        "round_id": ROUND_ID,
        "title": "V3 C2 主题转弱确认 Shadow",
        "status": "audited",
        "study_id": STUDY_ID,
        "asset_scope": "cn_stock_etf",
        "baseline_id": BASELINE_ID,
        "primary_question": "V3 股票腿 RISK_OFF_EXIT 是否能被大盘、行业、主题和卖后表现共同解释，哪些卖出疑似误杀？",
        "primary_variable": "read-only C2 shadow labels over V3 stock-leg risk-off exits",
        "fixed_assumptions": [
            "CN_STOCK_ETF_COMBO_BASELINE_V3 fixed",
            "stock_alpha_core risk-off exits only; ETF sleeve excluded",
            "no runtime, NAV, signal, pool, ranking, execution, or exit-rule changes",
            "theme health reused from C1 and matched as-of on or before exit date with 10-calendar-day limit",
        ],
        "windows": list(WINDOWS.keys()),
        "variants": [VARIANT_NAME],
        "evidence": [
            {
                "kind": "report",
                "study_id": STUDY_ID,
                "window_key": "1626",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "human" / "c2_theme_weak_confirmation_shadow.md"),
                "note": "human C2 shadow report",
                "linked_at": now,
            },
            {
                "kind": "summary",
                "study_id": STUDY_ID,
                "window_key": "multi",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "machine" / "summary.json"),
                "note": "machine summary with window and verdict breakdowns",
                "linked_at": now,
            },
            {
                "kind": "table",
                "study_id": STUDY_ID,
                "window_key": "1626",
                "variant_name": VARIANT_NAME,
                "path": str(OUT_DIR / "machine" / "risk_off_exit_c2_detail_1626.csv"),
                "note": "per-trade risk-off exit C2 labels",
                "linked_at": now,
            },
        ],
        "key_findings": [
            (
                f"Main window has {main.get('risk_off_exit_count', 0)} risk-off exits; "
                f"theme evidence coverage is {main.get('theme_evidence_coverage_ratio', 0.0):.1%}."
            ),
            (
                f"Protected-profit exits count={protected.get('count', 0)}, "
                f"pnl={_fmt_money(protected.get('pnl_sum'))}; these exits generally avoided later weakness."
            ),
            (
                f"Suspected theme-not-weak overkill count={overkill.get('count', 0)}, "
                f"pnl={_fmt_money(overkill.get('pnl_sum'))}; these rebounded after risk-off exit."
            ),
            (
                f"Mixed industry-weak-but-rebounded count={mixed_industry.get('count', 0)}, "
                f"pnl={_fmt_money(mixed_industry.get('pnl_sum'))}; industry weakness alone is not enough for final confirmation."
            ),
            "C2 should stay as a diagnostic layer until C3 counterfactual proves delayed or staged exit is stable across windows.",
        ],
        "audit": {
            "same_window_compare": False,
            "config_truth_checked": False,
            "nav_lineage_checked": False,
            "docker_run_checked": False,
            "source_artifact_checked": True,
            "theme_proxy_source_checked": True,
            "read_only_shadow": True,
        },
        "decision": {
            "status": "continue",
            "reason": "Continue to C3 counterfactual; do not promote C2 directly to runtime because theme coverage and false-positive risk are still material.",
        },
        "next_actions": [
            "Run C3 delayed/staged exit counterfactual for suspected overkill samples only.",
            "Separate results by profitable protected exits, losing exits, and rebounded exits.",
            "Require cross-window stability before any formal AB.",
        ],
        "tags": ["cn_stock_etf", "V3", "C2", "theme-health", "risk-off-exit", "shadow"],
        "schema_version": "openclaw_study_round@1",
        "created_at": now,
        "updated_at": now,
    }
    journal_path = _abs(JOURNAL_PATH)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> dict[str, Any]:
    out_dir = _abs(OUT_DIR)
    machine_dir = out_dir / "machine"
    machine_dir.mkdir(parents=True, exist_ok=True)

    closed = _read_csv(SOURCE_LOSS_AUDIT_DIR / "machine" / "all_closed_stock_trades_enriched.csv")
    if closed.empty:
        raise RuntimeError("missing enriched V3 closed trades from loss TOP30 audit")
    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce")
    risk_exits = closed.loc[closed["exit_reason_code"].astype(str).eq("RISK_OFF_EXIT")].copy()
    risk_exits.sort_values(["exit_date", "symbol"], inplace=True)

    matrix: list[dict[str, Any]] = []
    detail_by_window: dict[str, pd.DataFrame] = {}
    for window_key, (start, end) in WINDOWS.items():
        detail, window_summary = _build_shadow_for_window(risk_exits, window_key, start, end)
        matrix.append(window_summary)
        detail_by_window[window_key] = detail
        detail.to_csv(machine_dir / f"risk_off_exit_c2_detail_{window_key}.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(window_summary.get("verdict_summary", [])).to_csv(
            machine_dir / f"verdict_summary_{window_key}.csv", index=False, encoding="utf-8-sig"
        )

    matrix_frame = pd.DataFrame(
        [
            {
                "window_key": item.get("window_key"),
                "risk_off_exit_count": item.get("risk_off_exit_count"),
                "total_pnl": item.get("total_pnl"),
                "winning_exit_count": item.get("winning_exit_count"),
                "losing_exit_count": item.get("losing_exit_count"),
                "theme_evidence_coverage_ratio": item.get("theme_evidence_coverage_ratio"),
                "market_state_weak_count": item.get("market_state_weak_count"),
                "broad_indices_weak_count": item.get("broad_indices_weak_count"),
                "industry_weak_count": item.get("industry_weak_count"),
                "theme_confirmed_weak_count": item.get("theme_confirmed_weak_count"),
                "theme_watch_or_weak_count": item.get("theme_watch_or_weak_count"),
                "stock_weak_count": item.get("stock_weak_count"),
            }
            for item in matrix
        ]
    )
    matrix_frame.to_csv(machine_dir / "window_summary.csv", index=False, encoding="utf-8-sig")

    summary = {
        "round_id": ROUND_ID,
        "study_id": STUDY_ID,
        "baseline_id": BASELINE_ID,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "read-only C2 shadow over V3 stock_alpha_core RISK_OFF_EXIT trades",
        "theme_lookup_mode": "asof_on_or_before_exit_date_with_10_calendar_day_limit",
        "source_files": {
            "closed_trades_enriched": str(SOURCE_LOSS_AUDIT_DIR / "machine" / "all_closed_stock_trades_enriched.csv"),
            "theme_health_daily": str(SOURCE_C1_DIR / "{window}/C1_THEME_HEALTH_SHADOW/machine/theme_health_daily.csv"),
        },
        "outputs": {
            "report": str(OUT_DIR / "human" / "c2_theme_weak_confirmation_shadow.md"),
            "window_summary": str(OUT_DIR / "machine" / "window_summary.csv"),
            "journal": str(JOURNAL_PATH),
        },
        "windows": matrix,
    }
    (machine_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(matrix, detail_by_window.get("1626", pd.DataFrame()), out_dir)
    _write_journal(summary)
    return summary


if __name__ == "__main__":
    result = run()
    compact = {
        "round_id": result["round_id"],
        "study_id": result["study_id"],
        "baseline_id": result["baseline_id"],
        "theme_lookup_mode": result["theme_lookup_mode"],
        "outputs": result["outputs"],
        "window_summary": [
            {
                "window_key": item["window_key"],
                "risk_off_exit_count": item["risk_off_exit_count"],
                "theme_evidence_coverage_ratio": item["theme_evidence_coverage_ratio"],
                "theme_watch_or_weak_count": item["theme_watch_or_weak_count"],
                "industry_weak_count": item["industry_weak_count"],
                "stock_weak_count": item["stock_weak_count"],
            }
            for item in result["windows"]
        ],
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))

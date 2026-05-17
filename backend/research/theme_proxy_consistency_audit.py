from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None

from backend.api.shared.json_utils import sanitize_json

TARGET_THEMES = ("算力", "CPO/光模块", "存储", "半导体")

WINDOWS = {
    "2020_2026": ("2020-01-01", "2026-05-08"),
    "2024_2026": ("2024-01-01", "2026-05-08"),
    "2025_2026": ("2025-01-01", "2026-05-08"),
    "2025_12_2026_04": ("2025-12-01", "2026-04-30"),
    "2026_03": ("2026-03-01", "2026-03-31"),
    "2026_04": ("2026-04-01", "2026-04-30"),
}


@dataclass(frozen=True)
class ProxySpec:
    theme: str
    proxy_group: str
    primary_symbols: tuple[str, ...]
    auxiliary_symbols: tuple[str, ...]

    @property
    def all_symbols(self) -> tuple[str, ...]:
        out: list[str] = []
        for symbol in [*self.primary_symbols, *self.auxiliary_symbols]:
            if symbol not in out:
                out.append(symbol)
        return tuple(out)


PROXY_SPECS = (
    ProxySpec(
        theme="算力",
        proxy_group="compute",
        primary_symbols=("sz159819", "sh516510", "sh512720"),
        auxiliary_symbols=("sh515230",),
    ),
    ProxySpec(
        theme="CPO/光模块",
        proxy_group="cpo_optical",
        primary_symbols=("sh515880",),
        auxiliary_symbols=("sz159819", "sh512720"),
    ),
    ProxySpec(
        theme="存储",
        proxy_group="storage",
        primary_symbols=("sh512760", "sh512480", "sz159997"),
        auxiliary_symbols=("sz159732",),
    ),
    ProxySpec(
        theme="半导体",
        proxy_group="semiconductor",
        primary_symbols=("sh512480", "sh512760"),
        auxiliary_symbols=("sz159997", "sz159732"),
    ),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _db_settings() -> dict[str, Any]:
    return {
        "host": os.environ.get("PAMS_PG_HOST") or os.environ.get("PGHOST") or "127.0.0.1",
        "port": int(os.environ.get("PAMS_PG_PORT") or os.environ.get("PGPORT") or "15432"),
        "dbname": os.environ.get("PAMS_PG_DB") or os.environ.get("PGDATABASE") or "pams",
        "user": os.environ.get("PAMS_PG_USER") or os.environ.get("PGUSER") or "pams",
        "password": os.environ.get("PAMS_PG_PASSWORD") or os.environ.get("PGPASSWORD") or "",
    }


def _load_prices(
    *,
    table: str,
    symbols: list[str],
    start: str,
    end: str,
) -> pd.DataFrame:
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg is required for theme proxy consistency audit")
    if not symbols:
        return pd.DataFrame(columns=["date", "symbol", "close", "adj_factor"])
    query = f"""
        SELECT trade_date AS date, symbol, close, adj_factor
        FROM public.{table}
        WHERE symbol = ANY(%s)
          AND trade_date >= %s
          AND trade_date <= %s
        ORDER BY trade_date, symbol
    """
    with psycopg.connect(**_db_settings(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (symbols, start, end))
            rows = cur.fetchall()
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol", "close", "adj_factor"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["adj_factor"] = pd.to_numeric(frame["adj_factor"], errors="coerce").fillna(1.0)
    frame["adj_close"] = frame["close"] * frame["adj_factor"]
    return frame.dropna(subset=["date", "symbol", "adj_close"]).sort_values(["symbol", "date"]).reset_index(drop=True)


def _add_returns(prices: pd.DataFrame, horizons: tuple[int, ...] = (5, 20)) -> pd.DataFrame:
    if prices.empty:
        return prices.copy()
    out = prices.copy().sort_values(["symbol", "date"])
    for horizon in horizons:
        out[f"ret{horizon}"] = out.groupby("symbol")["adj_close"].pct_change(horizon)
    return out


def _target_holdings(holdings: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    base = holdings.copy()
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base["value"] = pd.to_numeric(base["value"], errors="coerce")
    base["theme_tags"] = base["theme_tags"].fillna("").astype(str)
    for theme in TARGET_THEMES:
        part = base.loc[base["theme_tags"].str.contains(theme, regex=False)].copy()
        if part.empty:
            continue
        part["theme"] = theme
        rows.append(part)
    if not rows:
        return pd.DataFrame(columns=["date", "symbol", "theme", "value"])
    return pd.concat(rows, ignore_index=True).dropna(subset=["date", "symbol", "value"])


def _build_stock_theme_returns(holdings: pd.DataFrame, stock_returns: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame()
    cols = ["date", "symbol", "ret5", "ret20"]
    merged = holdings.merge(stock_returns[cols], how="left", on=["date", "symbol"])
    rows: list[dict[str, Any]] = []
    for (date, theme), grp in merged.groupby(["date", "theme"], dropna=False):
        row: dict[str, Any] = {
            "date": pd.Timestamp(date),
            "theme": str(theme),
            "held_symbols": int(grp["symbol"].nunique()),
            "theme_value": float(pd.to_numeric(grp["value"], errors="coerce").fillna(0.0).sum()),
            "held_examples": "; ".join(
                (grp["symbol"].astype(str) + " " + grp.get("name", "").fillna("").astype(str)).drop_duplicates().head(8).tolist()
            ),
        }
        for horizon in (5, 20):
            ret_col = f"ret{horizon}"
            valid = grp.loc[pd.to_numeric(grp[ret_col], errors="coerce").notna()].copy()
            row[f"stock_ret{horizon}_valid_symbols"] = int(valid["symbol"].nunique())
            row[f"stock_ret{horizon}_coverage_ratio"] = (
                float(valid["symbol"].nunique() / max(grp["symbol"].nunique(), 1))
            )
            if valid.empty:
                row[f"stock_ret{horizon}_ew"] = None
                row[f"stock_ret{horizon}_vw"] = None
                continue
            values = pd.to_numeric(valid["value"], errors="coerce").fillna(0.0)
            returns = pd.to_numeric(valid[ret_col], errors="coerce")
            row[f"stock_ret{horizon}_ew"] = float(returns.mean())
            row[f"stock_ret{horizon}_vw"] = (
                float((returns * values).sum() / values.sum()) if float(values.sum()) > 0 else float(returns.mean())
            )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["date", "theme"]).reset_index(drop=True)


def _build_proxy_returns(etf_returns: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in PROXY_SPECS:
        all_rows = etf_returns.loc[etf_returns["symbol"].isin(spec.all_symbols)].copy()
        primary_rows = etf_returns.loc[etf_returns["symbol"].isin(spec.primary_symbols)].copy()
        for date, grp in all_rows.groupby("date", dropna=False):
            primary_grp = primary_rows.loc[primary_rows["date"].eq(date)]
            row: dict[str, Any] = {
                "date": pd.Timestamp(date),
                "theme": spec.theme,
                "proxy_group": spec.proxy_group,
                "primary_symbols": ";".join(spec.primary_symbols),
                "auxiliary_symbols": ";".join(spec.auxiliary_symbols),
                "proxy_names": "; ".join(f"{symbol} {names.get(symbol, '')}".strip() for symbol in spec.all_symbols),
            }
            for horizon in (5, 20):
                ret_col = f"ret{horizon}"
                all_ret = pd.to_numeric(grp[ret_col], errors="coerce").dropna()
                primary_ret = pd.to_numeric(primary_grp[ret_col], errors="coerce").dropna()
                row[f"proxy_ret{horizon}_all_valid_count"] = int(len(all_ret))
                row[f"proxy_ret{horizon}_primary_valid_count"] = int(len(primary_ret))
                row[f"proxy_ret{horizon}_all_mean"] = float(all_ret.mean()) if not all_ret.empty else None
                row[f"proxy_ret{horizon}_all_median"] = float(all_ret.median()) if not all_ret.empty else None
                row[f"proxy_ret{horizon}_all_max"] = float(all_ret.max()) if not all_ret.empty else None
                row[f"proxy_ret{horizon}_primary_mean"] = float(primary_ret.mean()) if not primary_ret.empty else None
                row[f"proxy_ret{horizon}_main"] = (
                    float(primary_ret.mean())
                    if not primary_ret.empty
                    else (float(all_ret.mean()) if not all_ret.empty else None)
                )
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["date", "theme"]).reset_index(drop=True)


def _corr(a: pd.Series, b: pd.Series, *, method: str = "pearson") -> float | None:
    pair = pd.DataFrame({"a": pd.to_numeric(a, errors="coerce"), "b": pd.to_numeric(b, errors="coerce")}).dropna()
    if len(pair) < 5:
        return None
    if method == "spearman":
        return float(pair["a"].rank().corr(pair["b"].rank()))
    return float(pair["a"].corr(pair["b"]))


def _sign_match(a: pd.Series, b: pd.Series) -> float | None:
    pair = pd.DataFrame({"a": pd.to_numeric(a, errors="coerce"), "b": pd.to_numeric(b, errors="coerce")}).dropna()
    if pair.empty:
        return None
    return float((pair["a"].ge(0) == pair["b"].ge(0)).mean())


def _verdict(joint_days: int, corr20: float | None, sign20: float | None) -> str:
    if joint_days < 20:
        return "LOW_SAMPLE"
    if corr20 is not None and sign20 is not None and corr20 >= 0.45 and sign20 >= 0.60:
        return "ACCEPT"
    if corr20 is not None and sign20 is not None and corr20 >= 0.25 and sign20 >= 0.55:
        return "PARTIAL"
    return "WEAK"


def _correlation_summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_key, (start, end) in WINDOWS.items():
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        frame = daily.loc[(daily["date"] >= start_ts) & (daily["date"] <= end_ts)].copy()
        for theme in TARGET_THEMES:
            part = frame.loc[frame["theme"].eq(theme)].copy()
            if part.empty:
                rows.append({"window_key": window_key, "theme": theme, "held_days": 0, "verdict": "NO_HOLDINGS"})
                continue
            row: dict[str, Any] = {
                "window_key": window_key,
                "start": start,
                "end": end,
                "theme": theme,
                "held_days": int(part["date"].nunique()),
                "avg_held_symbols": float(pd.to_numeric(part["held_symbols"], errors="coerce").mean()),
                "avg_theme_value": float(pd.to_numeric(part["theme_value"], errors="coerce").mean()),
            }
            for horizon in (5, 20):
                stock_col = f"stock_ret{horizon}_vw"
                proxy_col = f"proxy_ret{horizon}_main"
                pair = part[[stock_col, proxy_col]].apply(pd.to_numeric, errors="coerce").dropna()
                row[f"joint_ret{horizon}_days"] = int(len(pair))
                row[f"corr_ret{horizon}_pearson"] = _corr(part[stock_col], part[proxy_col])
                row[f"corr_ret{horizon}_spearman"] = _corr(part[stock_col], part[proxy_col], method="spearman")
                row[f"sign_match_ret{horizon}"] = _sign_match(part[stock_col], part[proxy_col])
                row[f"stock_ret{horizon}_avg"] = float(pd.to_numeric(part[stock_col], errors="coerce").mean())
                row[f"proxy_ret{horizon}_avg"] = float(pd.to_numeric(part[proxy_col], errors="coerce").mean())
            row["verdict"] = _verdict(
                int(row.get("joint_ret20_days") or 0),
                row.get("corr_ret20_pearson"),
                row.get("sign_match_ret20"),
            )
            rows.append(row)
    return pd.DataFrame(rows)


def _coverage_summary(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for theme in TARGET_THEMES:
        part = daily.loc[daily["theme"].eq(theme)].copy()
        if part.empty:
            rows.append({"theme": theme, "held_days": 0})
            continue
        row = {
            "theme": theme,
            "first_held_date": str(part["date"].min().date()),
            "last_held_date": str(part["date"].max().date()),
            "held_days": int(part["date"].nunique()),
            "ret5_joint_days": int(part[["stock_ret5_vw", "proxy_ret5_main"]].dropna().shape[0]),
            "ret20_joint_days": int(part[["stock_ret20_vw", "proxy_ret20_main"]].dropna().shape[0]),
            "ret5_joint_coverage": float(part[["stock_ret5_vw", "proxy_ret5_main"]].dropna().shape[0] / max(len(part), 1)),
            "ret20_joint_coverage": float(part[["stock_ret20_vw", "proxy_ret20_main"]].dropna().shape[0] / max(len(part), 1)),
            "avg_ret20_stock_symbol_coverage": float(
                pd.to_numeric(part["stock_ret20_coverage_ratio"], errors="coerce").mean()
            ),
            "avg_proxy_ret20_primary_valid_count": float(
                pd.to_numeric(part["proxy_ret20_primary_valid_count"], errors="coerce").mean()
            ),
            "avg_proxy_ret20_all_valid_count": float(
                pd.to_numeric(part["proxy_ret20_all_valid_count"], errors="coerce").mean()
            ),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _etf_symbol_coverage(etf_returns: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in PROXY_SPECS:
        for role, symbols in (("primary", spec.primary_symbols), ("auxiliary", spec.auxiliary_symbols)):
            for symbol in symbols:
                part = etf_returns.loc[etf_returns["symbol"].eq(symbol)].copy()
                rows.append(
                    {
                        "theme": spec.theme,
                        "proxy_group": spec.proxy_group,
                        "role": role,
                        "symbol": symbol,
                        "name": names.get(symbol, ""),
                        "first_price_date": str(part["date"].min().date()) if not part.empty else "",
                        "last_price_date": str(part["date"].max().date()) if not part.empty else "",
                        "price_days": int(len(part)),
                        "ret5_valid_days": int(pd.to_numeric(part.get("ret5"), errors="coerce").notna().sum()) if not part.empty else 0,
                        "ret20_valid_days": int(pd.to_numeric(part.get("ret20"), errors="coerce").notna().sum()) if not part.empty else 0,
                    }
                )
    return pd.DataFrame(rows)


def _write_report(
    *,
    path: Path,
    summary: dict[str, Any],
    coverage: pd.DataFrame,
    corr: pd.DataFrame,
    etf_cov: pd.DataFrame,
) -> None:
    lines = [
        "# Theme Proxy Consistency Audit",
        "",
        "## Conclusion",
        "",
        f"- overall_verdict: {summary.get('overall_verdict')}",
        f"- reason: {summary.get('reason')}",
        "- scope: research-only audit; no trades, no NAV recomputation, no baseline change.",
        "",
        "## Theme Coverage",
        "",
        "| theme | held_days | ret20_joint_coverage | avg_stock_symbol_coverage | avg_proxy_primary_count | avg_proxy_all_count |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in coverage.itertuples(index=False):
        lines.append(
            f"| {row.theme} | {getattr(row, 'held_days', '')} | {getattr(row, 'ret20_joint_coverage', '')} | "
            f"{getattr(row, 'avg_ret20_stock_symbol_coverage', '')} | {getattr(row, 'avg_proxy_ret20_primary_valid_count', '')} | "
            f"{getattr(row, 'avg_proxy_ret20_all_valid_count', '')} |"
        )
    lines.extend(
        [
            "",
            "## Correlation By Window",
            "",
            "| window | theme | verdict | held_days | joint20 | corr20 | sign20 | corr5 | sign5 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in corr.itertuples(index=False):
        lines.append(
            "| {window} | {theme} | {verdict} | {held} | {joint20} | {corr20} | {sign20} | {corr5} | {sign5} |".format(
                window=getattr(row, "window_key", ""),
                theme=getattr(row, "theme", ""),
                verdict=getattr(row, "verdict", ""),
                held=getattr(row, "held_days", ""),
                joint20=getattr(row, "joint_ret20_days", ""),
                corr20=getattr(row, "corr_ret20_pearson", ""),
                sign20=getattr(row, "sign_match_ret20", ""),
                corr5=getattr(row, "corr_ret5_pearson", ""),
                sign5=getattr(row, "sign_match_ret5", ""),
            )
        )
    lines.extend(["", "## ETF Proxy Coverage", ""])
    lines.extend(
        [
            "| theme | role | symbol | name | first | last | ret20_valid_days |",
            "|---|---|---|---|---|---|---:|",
        ]
    )
    for row in etf_cov.itertuples(index=False):
        lines.append(
            f"| {row.theme} | {row.role} | {row.symbol} | {row.name} | {row.first_price_date} | {row.last_price_date} | {row.ret20_valid_days} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_audit(
    *,
    source_artifact_dir: Path,
    output_dir: Path,
    price_start: str = "2018-01-01",
    price_end: str = "2026-05-08",
) -> dict[str, Any]:
    source_artifact_dir = source_artifact_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    holdings = _target_holdings(_read_csv(source_artifact_dir / "long_daily_stock_holdings_reconstructed.csv"))
    etf_map = _read_csv(source_artifact_dir / "etf_theme_index_map.csv")
    names = dict(zip(etf_map["symbol"].astype(str), etf_map["name"].astype(str)))

    stock_symbols = sorted(holdings["symbol"].dropna().astype(str).unique().tolist())
    etf_symbols = sorted({symbol for spec in PROXY_SPECS for symbol in spec.all_symbols})
    stock_prices = _add_returns(_load_prices(table="pams_ohlcv_daily_v2", symbols=stock_symbols, start=price_start, end=price_end))
    etf_prices = _add_returns(_load_prices(table="pams_cn_etf_daily", symbols=etf_symbols, start=price_start, end=price_end))
    stock_theme_returns = _build_stock_theme_returns(holdings, stock_prices)
    proxy_returns = _build_proxy_returns(etf_prices, names)
    daily = stock_theme_returns.merge(proxy_returns, how="left", on=["date", "theme"])
    coverage = _coverage_summary(daily)
    corr = _correlation_summary(daily)
    etf_cov = _etf_symbol_coverage(etf_prices, names)
    proxy_config = pd.DataFrame(
        [
            {
                "theme": spec.theme,
                "proxy_group": spec.proxy_group,
                "primary_symbols": ";".join(spec.primary_symbols),
                "primary_names": "; ".join(names.get(symbol, "") for symbol in spec.primary_symbols),
                "auxiliary_symbols": ";".join(spec.auxiliary_symbols),
                "auxiliary_names": "; ".join(names.get(symbol, "") for symbol in spec.auxiliary_symbols),
            }
            for spec in PROXY_SPECS
        ]
    )

    machine_dir = output_dir / "machine"
    human_dir = output_dir / "human"
    machine_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)
    stock_theme_returns.to_csv(machine_dir / "stock_theme_daily_returns.csv", index=False, encoding="utf-8-sig")
    proxy_returns.to_csv(machine_dir / "theme_proxy_daily_returns.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(machine_dir / "theme_proxy_joined_daily.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(machine_dir / "coverage_by_theme.csv", index=False, encoding="utf-8-sig")
    corr.to_csv(machine_dir / "correlation_by_theme_window.csv", index=False, encoding="utf-8-sig")
    etf_cov.to_csv(machine_dir / "etf_symbol_coverage.csv", index=False, encoding="utf-8-sig")
    proxy_config.to_csv(machine_dir / "proxy_config.csv", index=False, encoding="utf-8-sig")

    key = corr.loc[corr["window_key"].eq("2025_2026")].copy()
    verdict_counts = key["verdict"].fillna("").astype(str).value_counts().to_dict() if not key.empty else {}
    accepted = int(verdict_counts.get("ACCEPT", 0))
    partial = int(verdict_counts.get("PARTIAL", 0))
    weak = int(verdict_counts.get("WEAK", 0))
    low_sample = int(verdict_counts.get("LOW_SAMPLE", 0))
    no_holdings = int(verdict_counts.get("NO_HOLDINGS", 0))
    if accepted == len(TARGET_THEMES):
        overall = "ACCEPT"
        reason = "All target themes have acceptable held-stock/proxy consistency in 2025-2026."
    elif accepted >= 3 and (low_sample or no_holdings):
        overall = "PARTIAL"
        reason = "Three target themes have acceptable consistency, but at least one target theme has insufficient 2025-2026 held-stock samples."
    elif accepted + partial >= 3:
        overall = "PARTIAL"
        reason = "Most target themes are usable for shadow diagnostics, but at least one proxy needs refinement before runtime AB."
    else:
        overall = "WEAK"
        reason = "ETF proxies are not consistent enough with held stock themes for runtime AB."
    summary = sanitize_json(
        {
            "study_id": "sr_20260511_theme_proxy_consistency_audit",
            "generated_at": datetime.now().isoformat(),
            "research_only": True,
            "not_nav_backtest": True,
            "source_artifact_dir": str(source_artifact_dir),
            "source_manifest": _read_json(source_artifact_dir / "manifest.json"),
            "db_tables": {
                "stock_prices": "public.pams_ohlcv_daily_v2",
                "etf_prices": "public.pams_cn_etf_daily",
            },
            "price_start": price_start,
            "price_end": price_end,
            "target_themes": list(TARGET_THEMES),
            "overall_verdict": overall,
            "reason": reason,
            "verdict_counts_2025_2026": verdict_counts,
            "outputs": {
                "coverage_by_theme": str(machine_dir / "coverage_by_theme.csv"),
                "correlation_by_theme_window": str(machine_dir / "correlation_by_theme_window.csv"),
                "etf_symbol_coverage": str(machine_dir / "etf_symbol_coverage.csv"),
                "proxy_config": str(machine_dir / "proxy_config.csv"),
                "report": str(human_dir / "theme_proxy_consistency_audit.md"),
            },
        }
    )
    (machine_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(path=human_dir / "theme_proxy_consistency_audit.md", summary=summary, coverage=coverage, corr=corr, etf_cov=etf_cov)
    return summary


def main() -> None:
    repo = _repo_root()
    summary = run_audit(
        source_artifact_dir=repo / "outputs" / "studies" / "cn_stock_etf" / "sr_20260510_v3_industry_theme_etf_index_attribution",
        output_dir=repo / "outputs" / "studies" / "cn_stock_etf" / "sr_20260511_theme_proxy_consistency_audit",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

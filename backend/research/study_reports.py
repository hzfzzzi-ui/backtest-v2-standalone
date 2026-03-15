from __future__ import annotations

from typing import Any


def render_conclusion_markdown(
    *,
    title: str,
    hypothesis: str,
    verdict: dict[str, Any],
    perf: dict[str, Any],
    compare: dict[str, Any],
    window_key: str,
    variant_name: str,
) -> str:
    status = str(verdict.get("status") or "UNKNOWN")
    reason = str(verdict.get("reason") or "").strip() or "暂无"
    cagr = perf.get("cagr")
    max_drawdown = perf.get("max_drawdown")
    sharpe = perf.get("sharpe")
    trades = perf.get("trades")
    cagr_delta = (((compare.get("metrics") or {}).get("cagr") or {}) if isinstance(compare.get("metrics"), dict) else {}).get("delta")
    mdd_delta = (((compare.get("metrics") or {}).get("max_drawdown") or {}) if isinstance(compare.get("metrics"), dict) else {}).get("delta")
    return "\n".join(
        [
            f"[{title}]",
            "",
            "1. 本轮目标",
            f"- 窗口：{window_key}",
            f"- 变体：{variant_name}",
            "",
            "2. 研究假设",
            f"- {hypothesis}",
            "",
            "3. 审计结果",
            f"- 结论：{status}",
            f"- 原因：{reason}",
            "",
            "4. 回测结果对比",
            f"- CAGR：{cagr}",
            f"- MaxDD：{max_drawdown}",
            f"- Sharpe：{sharpe}",
            f"- Trades：{trades}",
            f"- 相对 baseline CAGR delta：{cagr_delta}",
            f"- 相对 baseline MaxDD delta：{mdd_delta}",
            "",
            "5. 结论（通过/不通过）",
            f"- {status}",
        ]
    ).strip() + "\n"


def render_summary_text(
    *,
    title: str,
    verdict: dict[str, Any],
    perf: dict[str, Any],
    window_key: str,
    variant_name: str,
) -> str:
    status = str(verdict.get("status") or "UNKNOWN")
    reason = str(verdict.get("reason") or "").strip() or "暂无"
    return (
        f"{title} | {window_key}/{variant_name} | {status} | "
        f"CAGR={perf.get('cagr')} | MaxDD={perf.get('max_drawdown')} | "
        f"Sharpe={perf.get('sharpe')} | Trades={perf.get('trades')} | {reason}"
    )

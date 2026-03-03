"""参数扫描结果汇总报告。

从 batch_runner 的返回结果中提取关键指标，生成对比表（终端 + CSV）。
"""
from __future__ import annotations

import csv
import io
from typing import Any


# 报告列定义: (显示名, 结果 key, 格式化函数)
_COLUMNS: list[tuple[str, str, str]] = [
    ("Config", "config_name", "s"),
    ("Status", "status", "s"),
    ("总收益", "total_return", ".2%"),
    ("年化", "cagr", ".2%"),
    ("最大回撤", "max_drawdown", ".2%"),
    ("Sharpe", "sharpe", ".3f"),
    ("交易数", "trades", "d"),
    ("换手率", "turnover", ".2%"),
    ("ATR止损", "atr_stop_exit_count", "d"),
    ("ATR跟踪", "atr_trail_exit_count", "d"),
    ("耗时(s)", "elapsed_s", ".0f"),
]


def format_report(results: list[dict[str, Any]], sort_by: str = "sharpe") -> str:
    """从结果列表生成终端对齐表格字符串。"""
    # 按 sort_by 降序排列（FAILED 排最后）
    ok_results = [r for r in results if r.get("status") == "OK"]
    fail_results = [r for r in results if r.get("status") != "OK"]
    ok_results.sort(key=lambda r: float(r.get(sort_by, 0) or 0), reverse=True)
    sorted_results = ok_results + fail_results

    # 计算列宽
    widths = [len(col[0]) for col in _COLUMNS]
    rows: list[list[str]] = []
    for r in sorted_results:
        row: list[str] = []
        for i, (_, key, fmt) in enumerate(_COLUMNS):
            val = r.get(key, "")
            if r.get("status") != "OK" and key not in ("config_name", "status", "elapsed_s"):
                cell = "-"
            elif fmt == "s":
                cell = str(val)
            elif fmt == "d":
                cell = str(int(val or 0))
            elif fmt == ".2%":
                cell = f"{float(val or 0) * 100:.2f}%"
            elif fmt == ".3f":
                cell = f"{float(val or 0):.3f}"
            elif fmt == ".0f":
                cell = f"{float(val or 0):.0f}"
            else:
                cell = str(val)
            widths[i] = max(widths[i], len(cell))
            row.append(cell)
        rows.append(row)

    # 构建表格
    lines: list[str] = []
    header = "  ".join(col[0].ljust(widths[i]) for i, col in enumerate(_COLUMNS))
    lines.append(header)
    lines.append("-" * len(header))
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))

    return "\n".join(lines)


def to_csv_string(results: list[dict[str, Any]], sort_by: str = "sharpe") -> str:
    """从结果列表生成 CSV 字符串。"""
    ok_results = [r for r in results if r.get("status") == "OK"]
    fail_results = [r for r in results if r.get("status") != "OK"]
    ok_results.sort(key=lambda r: float(r.get(sort_by, 0) or 0), reverse=True)
    sorted_results = ok_results + fail_results

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([col[0] for col in _COLUMNS])

    for r in sorted_results:
        row: list[str] = []
        for _, key, fmt in _COLUMNS:
            val = r.get(key, "")
            if r.get("status") != "OK" and key not in ("config_name", "status", "elapsed_s"):
                row.append("")
            elif fmt in ("s", "d"):
                row.append(str(val))
            else:
                row.append(str(val))
        writer.writerow(row)

    return buf.getvalue()


def save_csv(results: list[dict[str, Any]], path: str, sort_by: str = "sharpe") -> None:
    """保存对比 CSV 到文件。"""
    from pathlib import Path as P
    P(path).write_text(to_csv_string(results, sort_by), encoding="utf-8")


def print_report(results: list[dict[str, Any]], sort_by: str = "sharpe") -> None:
    """打印终端对比表格。"""
    print("\n" + format_report(results, sort_by) + "\n")

"""从 BaoStock 拉取 CSI800 (HS300+ZZ500) 历史成分股，重建 in_date / out_date。

BaoStock 免费、无需注册、支持任意历史日期的 PIT 查询。
CSI800 = HS300 + ZZ500，分别查询后合并。

用法:
  pip install baostock
  python backend/scripts/fetch_csi800_pit.py

输出:
  data_cache/csi800_pit_snapshots.csv  — 月度快照
  data_cache/csi800_pit_changes.csv    — 重建的 in_date / out_date 变动表
"""
from __future__ import annotations

import csv
import datetime
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
_cache_dir = _root / "data_cache"
_cache_dir.mkdir(exist_ok=True)

SNAPSHOT_CSV = _cache_dir / "csi800_pit_snapshots.csv"
CHANGES_CSV = _cache_dir / "csi800_pit_changes.csv"

START_YEAR = 2007  # CSI800 launched 2007-01-15
END_YEAR = 2026
CSI800_LAUNCH_DATE = datetime.date(2007, 1, 15)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def bs_to_local(bs_code: str) -> str:
    """sh.600000 -> 600000.SH, sz.000001 -> 000001.SZ"""
    parts = bs_code.split(".")
    if len(parts) == 2:
        exchange = parts[0].upper()
        num = parts[1]
        return f"{num}.{exchange}"
    return bs_code


def build_sample_dates() -> list[datetime.date]:
    """每月 1 号作为采样日。"""
    today = datetime.date.today()
    dates: list[datetime.date] = []
    if CSI800_LAUNCH_DATE <= today:
        # Use the actual launch date as the first snapshot.
        # Sampling 2007-01-01 leaves 2007-01-15 to 2007-01-31 at only 300 names.
        dates.append(CSI800_LAUNCH_DATE)
    for year in range(START_YEAR, END_YEAR + 1):
        for month in range(1, 13):
            d = datetime.date(year, month, 1)
            if d < CSI800_LAUNCH_DATE:
                continue
            if d <= today:
                dates.append(d)
    return dates


def fetch_snapshots(dates: list[datetime.date]) -> list[tuple[str, list[str]]]:
    """从 BaoStock 逐月拉取 HS300 + ZZ500 成分股快照，合并为 CSI800。"""
    try:
        import baostock as bs
    except ImportError:
        print("ERROR: baostock 未安装。请运行: pip install baostock")
        sys.exit(1)

    lg = bs.login()
    if lg.error_code != "0":
        print(f"ERROR: BaoStock login failed: {lg.error_msg}")
        sys.exit(1)
    print(f"BaoStock login OK")

    results: list[tuple[str, list[str]]] = []

    for i, d in enumerate(dates):
        date_str = d.strftime("%Y-%m-%d")

        try:
            # HS300
            rs300 = bs.query_hs300_stocks(date=date_str)
            df300 = rs300.get_data()
            hs300_codes = set()
            if len(df300) > 0:
                hs300_codes = {bs_to_local(c) for c in df300["code"]}

            # ZZ500
            rs500 = bs.query_zz500_stocks(date=date_str)
            df500 = rs500.get_data()
            zz500_codes = set()
            if len(df500) > 0:
                zz500_codes = {bs_to_local(c) for c in df500["code"]}

            # CSI800 = HS300 ∪ ZZ500
            csi800 = sorted(hs300_codes | zz500_codes)
            results.append((date_str, csi800))
            print(f"  [{i + 1}/{len(dates)}] {date_str}: HS300={len(hs300_codes)} + ZZ500={len(zz500_codes)} = CSI800={len(csi800)}")

        except Exception as e:
            print(f"  [{i + 1}/{len(dates)}] {date_str}: ERROR — {e}")
            results.append((date_str, []))

        time.sleep(0.05)

    bs.logout()
    return results


def validate_snapshots(snapshots: list[tuple[str, list[str]]]) -> None:
    """Fail fast when the upstream source clearly returns broken monthly snapshots."""
    launch_seen = False
    broken_dates: list[str] = []
    for date_str, stocks in snapshots:
        count = len(stocks)
        if date_str == CSI800_LAUNCH_DATE.isoformat():
            launch_seen = True
            if count < 700:
                raise RuntimeError(f"launch snapshot {date_str} only has {count} names")
            continue
        if date_str >= "2007-02-01" and count < 700:
            broken_dates.append(f"{date_str}:{count}")
    if not launch_seen:
        raise RuntimeError(f"missing launch snapshot {CSI800_LAUNCH_DATE.isoformat()}")
    if broken_dates:
        sample = ", ".join(broken_dates[:5])
        raise RuntimeError(f"upstream snapshot quality check failed after launch: {sample}")


def save_snapshots(snapshots: list[tuple[str, list[str]]]) -> None:
    """保存月度快照到 CSV。"""
    with open(SNAPSHOT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "symbol"])
        total = 0
        for date_str, stocks in snapshots:
            for sym in stocks:
                writer.writerow([date_str, sym])
                total += 1
    print(f"快照保存: {SNAPSHOT_CSV} ({total:,} 行)")


def reconstruct_changes(snapshots: list[tuple[str, list[str]]]) -> list[dict]:
    """从连续快照 diff 出 in_date / out_date 变动记录。"""
    active: dict[str, str] = {}
    changes: list[dict] = []

    for i, (date_str, stocks) in enumerate(snapshots):
        current_set = set(stocks)
        prev_set = set(active.keys())

        added = current_set - prev_set
        for sym in added:
            active[sym] = date_str

        removed = prev_set - current_set
        for sym in removed:
            changes.append({
                "index_code": "000906.SH",
                "symbol": sym,
                "in_date": active[sym],
                "out_date": date_str,
            })
            del active[sym]

        if i == 0:
            print(f"初始快照 {date_str}: {len(current_set)} 只")
        elif added or removed:
            print(f"  {date_str}: +{len(added)} / -{len(removed)}")

    # 仍在成分中的股票: out_date = None (当前成分)
    for sym, in_date in active.items():
        changes.append({
            "index_code": "000906.SH",
            "symbol": sym,
            "in_date": in_date,
            "out_date": "",
        })

    changes.sort(key=lambda r: (r["symbol"], r["in_date"]))
    return changes


def save_changes(changes: list[dict]) -> None:
    """保存变动表到 CSV。"""
    with open(CHANGES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["index_code", "symbol", "in_date", "out_date"])
        writer.writeheader()
        writer.writerows(changes)

    active = sum(1 for c in changes if not c["out_date"])
    removed = sum(1 for c in changes if c["out_date"])
    print(f"变动表保存: {CHANGES_CSV}")
    print(f"  总记录: {len(changes)}, 当前成分: {active}, 历史移出: {removed}")


def print_stats(changes: list[dict]) -> None:
    """打印统计摘要。"""
    unique_symbols = set(c["symbol"] for c in changes)
    active = [c for c in changes if not c["out_date"]]
    removed = [c for c in changes if c["out_date"]]

    print(f"\n{'=' * 60}")
    print(f"  CSI800 历史成分股统计")
    print(f"{'=' * 60}")
    print(f"  历史出现过的股票总数:  {len(unique_symbols)}")
    print(f"  当前成分股数:          {len(active)}")
    print(f"  历史被移出次数:        {len(removed)}")
    if unique_symbols:
        print(f"  平均每只股票在指数中:  {len(changes) / len(unique_symbols):.1f} 段")

    # PIT 抽检
    print(f"\n  PIT 抽检（各时间点的成分股数）:")
    check_dates = ["2008-01-01", "2010-01-01", "2012-01-01", "2014-01-01",
                    "2016-03-01", "2018-01-01", "2020-01-01", "2022-01-01",
                    "2024-01-01", "2025-12-01"]
    for d in check_dates:
        count = sum(1 for c in changes
                    if c["in_date"] <= d and (not c["out_date"] or c["out_date"] > d))
        print(f"    {d}: {count} 只")

    if removed:
        from collections import Counter
        remove_counts = Counter(c["symbol"] for c in removed)
        print(f"\n  被移出次数最多的股票:")
        for sym, cnt in remove_counts.most_common(5):
            print(f"    {sym}: {cnt} 次")

    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"{'=' * 60}")
    print(f"  CSI800 历史成分股 PIT 数据采集 (BaoStock)")
    print(f"  数据源: HS300 + ZZ500 月度快照合并")
    print(f"  采样: {START_YEAR}-01 至 {END_YEAR} 月度")
    print(f"{'=' * 60}\n")

    dates = build_sample_dates()
    print(f"采样日期数: {len(dates)}")

    # Step 1: 拉取快照
    snapshots = fetch_snapshots(dates)

    # Guard against silently overwriting a valid local cache with broken upstream output.
    validate_snapshots(snapshots)

    # Step 2: 保存快照
    save_snapshots(snapshots)

    # Step 3: 重建变动记录
    print(f"\n重建 in_date / out_date ...")
    changes = reconstruct_changes(snapshots)

    # Step 4: 保存变动表
    save_changes(changes)

    # Step 5: 统计
    print_stats(changes)

    print(f"\n下一步:")
    print(f"  1. docker cp data_cache/csi800_pit_changes.csv backtest-v2-standalone:/app/data_cache/")
    print(f"  2. docker exec backtest-v2-standalone python backend/scripts/import_csi800_pit.py --from-csv /app/data_cache/csi800_pit_changes.csv")


if __name__ == "__main__":
    main()

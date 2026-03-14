"""将聚宽采集的 CSI800 PIT 变动表导入 pit_index_constituents。

用法（在 Docker 内执行）:
  python backend/scripts/import_csi800_pit.py --from-csv /app/data_cache/csi800_pit_changes.csv

或从宿主机两步式:
  1. 宿主机: python backend/scripts/fetch_csi800_pit.py   # 生成 data_cache/csi800_pit_changes.csv
  2. docker cp data_cache/csi800_pit_changes.csv backtest-v2-standalone:/app/data_cache/
  3. docker exec: python backend/scripts/import_csi800_pit.py --from-csv /app/data_cache/csi800_pit_changes.csv

功能:
  - TRUNCATE pit_index_constituents（清除旧 AKShare 数据）
  - 插入聚宽重建的 in_date/out_date 记录
  - 打印统计对比
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    import psycopg
except ImportError:
    psycopg = None


def _get_db_conn():
    if psycopg is None:
        raise RuntimeError("psycopg 未安装")
    return psycopg.connect(
        host=os.environ.get("PGHOST", os.environ.get("PAMS_PG_HOST", "pams-postgres")),
        port=int(os.environ.get("PGPORT", os.environ.get("PAMS_PG_PORT", "5432"))),
        dbname=os.environ.get("PGDATABASE", os.environ.get("PAMS_PG_DBNAME", "pams")),
        user=os.environ.get("PGUSER", os.environ.get("PAMS_PG_USER", "pams")),
        password=os.environ.get("PGPASSWORD", os.environ.get("PAMS_PG_PASSWORD", "")),
        autocommit=False,
    )


def _query_old_stats(conn) -> dict:
    """查询导入前的旧数据统计。"""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM public.pit_index_constituents WHERE index_code = '000906.SH'")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM public.pit_index_constituents WHERE index_code = '000906.SH' AND end_date IS NULL")
        active = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM public.pit_index_constituents WHERE index_code = '000906.SH' AND end_date IS NOT NULL")
        removed = cur.fetchone()[0]
        cur.execute("SELECT source FROM public.pit_index_constituents WHERE index_code = '000906.SH' LIMIT 1")
        row = cur.fetchone()
        source = row[0] if row else "N/A"
    return {"total": total, "active": active, "removed": removed, "source": source}


def _query_pit_check(conn, check_date: str) -> int:
    """查询指定日期的成分股数量。"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT symbol)
            FROM public.pit_index_constituents
            WHERE index_code = '000906.SH'
              AND start_date <= %s
              AND (end_date IS NULL OR end_date > %s)
        """, (check_date, check_date))
        return cur.fetchone()[0]


def import_changes(conn, csv_path: str) -> int:
    """读取 CSV，TRUNCATE + INSERT。"""
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out_date = row["out_date"].strip() if row["out_date"].strip() else None
            records.append((
                row["index_code"],
                row["symbol"],
                row["in_date"],
                out_date,
                "baostock_pit_snapshot",
            ))

    with conn.cursor() as cur:
        # Preserve other index_code datasets such as CSI1000.
        cur.execute("DELETE FROM public.pit_index_constituents WHERE index_code = '000906.SH'")
        insert_sql = """
            INSERT INTO public.pit_index_constituents
                (index_code, symbol, start_date, end_date, source, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """
        cur.executemany(insert_sql, records)
    conn.commit()
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="导入聚宽 CSI800 PIT 数据")
    parser.add_argument("--from-csv", required=True, help="csi800_pit_changes.csv 路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印统计，不写入")
    args = parser.parse_args()

    csv_path = args.from_csv
    if not Path(csv_path).exists():
        print(f"ERROR: 文件不存在: {csv_path}")
        sys.exit(1)

    # 读 CSV 统计
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    new_total = len(rows)
    new_active = sum(1 for r in rows if not r["out_date"].strip())
    new_removed = sum(1 for r in rows if r["out_date"].strip())
    new_symbols = len(set(r["symbol"] for r in rows))

    print(f"{'=' * 60}")
    print(f"  CSI800 PIT 数据导入")
    print(f"{'=' * 60}")
    print(f"\n  新数据 ({csv_path}):")
    print(f"    总记录:       {new_total}")
    print(f"    当前成分:     {new_active}")
    print(f"    历史移出记录: {new_removed}")
    print(f"    不重复股票:   {new_symbols}")

    conn = _get_db_conn()
    try:
        # 旧数据统计
        old = _query_old_stats(conn)
        print(f"\n  旧数据 (pit_index_constituents):")
        print(f"    总记录:       {old['total']}")
        print(f"    当前成分:     {old['active']} (end_date IS NULL)")
        print(f"    历史移出记录: {old['removed']} (end_date IS NOT NULL)")
        print(f"    数据来源:     {old['source']}")

        # PIT 检查点
        check_dates = ["2010-01-01", "2016-03-01", "2020-01-01", "2025-01-01"]
        print(f"\n  PIT 对比（旧数据）:")
        for d in check_dates:
            cnt = _query_pit_check(conn, d)
            print(f"    {d}: {cnt} 只")

        if args.dry_run:
            print(f"\n  [DRY RUN] 不写入数据库")
            return

        # 导入
        print(f"\n  正在导入...")
        count = import_changes(conn, csv_path)
        print(f"  写入 {count} 条记录")

        # 导入后 PIT 检查
        print(f"\n  PIT 对比（新数据）:")
        for d in check_dates:
            cnt = _query_pit_check(conn, d)
            print(f"    {d}: {cnt} 只")

    finally:
        conn.close()

    print(f"\n{'=' * 60}")
    print(f"  导入完成！")
    print(f"  数据来源已从 akshare_index_stock_cons → jqdatasdk_pit_snapshot")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

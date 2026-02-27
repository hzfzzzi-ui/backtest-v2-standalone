"""Universe 数据导入脚本 — 从 AKShare 拉取行业分类历史 + 中证800 成分数据。

用法:
  # 两步式（Docker 无外网时）:
  python -m backend.core.universe.ingest_universe --fetch-only --csv-dir ./data_cache
  docker-compose exec backtest-v2-standalone python -m backend.core.universe.ingest_universe --all --from-csv /app/data_cache

  # 一步式（有外网时）:
  python -m backend.core.universe.ingest_universe --all
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

try:
    import psycopg
except ImportError:
    psycopg = None

try:
    import akshare as ak
except ImportError:
    ak = None

from backend.core.data.mapping import normalize_stock_symbol

# ── 申万2021版 一级行业映射 ─────────────────────────────────────────
# industry_code 前2位 → L1 行业名称（共 31 个）
SW_L1_MAP: dict[str, str] = {
    # ── SW2021 标准 (31 个) ──
    "11": "农林牧渔",
    "22": "基础化工",
    "23": "钢铁",
    "24": "有色金属",
    "27": "电子",
    "28": "汽车",
    "33": "家用电器",
    "34": "食品饮料",
    "35": "纺织服饰",
    "36": "轻工制造",
    "37": "医药生物",
    "41": "公用事业",
    "42": "交通运输",
    "43": "房地产",
    "45": "商贸零售",
    "46": "社会服务",
    "48": "银行",
    "49": "非银金融",
    "51": "综合",
    "61": "建筑材料",
    "62": "建筑装饰",
    "63": "电力设备",
    "64": "机械设备",
    "65": "国防军工",
    "71": "计算机",
    "72": "传媒",
    "73": "通信",
    "74": "煤炭",
    "75": "石油石化",
    "76": "环保",
    "77": "美容护理",
    # ── SW2014 旧标准兼容映射 ──
    # 旧标准 code 前缀映射到最接近的 2021 L1 行业名
    "21": "煤炭",       # 旧:采掘 → 2021:煤炭（主体部分）
    "25": "基础化工",   # 旧:化工 → 2021:基础化工
    "26": "钢铁",       # 旧:钢铁（code 变更）
    "31": "建筑材料",   # 旧:建筑材料（code 变更）
    "32": "建筑装饰",   # 旧:建筑装饰（code 变更）
    "44": "商贸零售",   # 旧:商业贸易 → 2021:商贸零售
    "47": "社会服务",   # 旧:休闲服务 → 2021:社会服务
}

_INDUSTRY_CSV = "industry_clf_hist_sw.csv"
_INDEX_CSV = "index_stock_cons_000906.csv"


def _get_db_conn():
    """从环境变量获取数据库连接。"""
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


def _map_industry_l1(code: str) -> str | None:
    """从6位 industry_code 的前2位映射到 L1 行业名。"""
    prefix = str(code).strip()[:2]
    return SW_L1_MAP.get(prefix)


def _compute_end_dates(df: pd.DataFrame) -> pd.DataFrame:
    """对同一只股票的多条行业记录，推算 end_date。

    按 symbol+start_date 排序，前一条 end_date = 下一条 start_date，
    最后一条 end_date = None（当前仍有效）。
    """
    df = df.sort_values(["ts_code", "start_date"]).reset_index(drop=True)
    end_dates = [None] * len(df)
    groups = df.groupby("ts_code")
    for _, group in groups:
        idxs = group.index.tolist()
        for i in range(len(idxs) - 1):
            end_dates[idxs[i]] = df.at[idxs[i + 1], "start_date"]
    df["end_date"] = end_dates
    return df


def _fetch_industry_raw() -> pd.DataFrame:
    """从 AKShare 拉取行业分类历史原始数据。"""
    if ak is None:
        raise RuntimeError("akshare 未安装")
    print("[fetch] 从 AKShare 拉取 stock_industry_clf_hist_sw() ...")
    raw = ak.stock_industry_clf_hist_sw()
    print(f"[fetch] 获取 {len(raw)} 条行业分类记录")
    return raw


def _fetch_index_raw() -> pd.DataFrame:
    """从 AKShare 拉取中证800成分原始数据。"""
    if ak is None:
        raise RuntimeError("akshare 未安装")
    print("[fetch] 从 AKShare 拉取 index_stock_cons('000906') (中证800) ...")
    raw = ak.index_stock_cons(symbol="000906")
    print(f"[fetch] 获取 {len(raw)} 条成分记录")
    return raw


def fetch_and_save(csv_dir: str) -> None:
    """拉取 AKShare 数据并保存为 CSV（在有外网的环境运行）。"""
    out = Path(csv_dir)
    out.mkdir(parents=True, exist_ok=True)

    industry_raw = _fetch_industry_raw()
    industry_path = out / _INDUSTRY_CSV
    industry_raw.to_csv(str(industry_path), index=False, encoding="utf-8-sig")
    print(f"[fetch] 已保存 {industry_path} ({len(industry_raw)} 行)")

    index_raw = _fetch_index_raw()
    index_path = out / _INDEX_CSV
    index_raw.to_csv(str(index_path), index=False, encoding="utf-8-sig")
    print(f"[fetch] 已保存 {index_path} ({len(index_raw)} 行)")


def _load_industry_raw(csv_dir: str | None) -> pd.DataFrame:
    """从 AKShare 或 CSV 加载行业分类数据。"""
    if csv_dir:
        p = Path(csv_dir) / _INDUSTRY_CSV
        print(f"[industry] 从 CSV 加载: {p}")
        return pd.read_csv(str(p), dtype=str)
    return _fetch_industry_raw()


def _load_index_raw(csv_dir: str | None) -> pd.DataFrame:
    """从 AKShare 或 CSV 加载指数成分数据。"""
    if csv_dir:
        p = Path(csv_dir) / _INDEX_CSV
        print(f"[index] 从 CSV 加载: {p}")
        return pd.read_csv(str(p), dtype=str)
    return _fetch_index_raw()


def _transform_industry(raw: pd.DataFrame) -> pd.DataFrame:
    """将原始行业数据转换为标准格式，包括 L1 映射和 end_date 推算。"""
    if "symbol" not in raw.columns:
        raise ValueError(f"行业数据列不符合预期: {list(raw.columns)}")

    records = []
    unmapped = set()
    for _, row in raw.iterrows():
        symbol_raw = str(row["symbol"]).strip()
        start_raw = row["start_date"]
        code_raw = str(row["industry_code"]).strip()

        l1 = _map_industry_l1(code_raw)
        if l1 is None:
            unmapped.add(code_raw[:2])
            continue

        ts_code = normalize_stock_symbol(symbol_raw)

        if isinstance(start_raw, (date, datetime)):
            start_date = start_raw if isinstance(start_raw, date) else start_raw.date()
        else:
            start_date = pd.to_datetime(str(start_raw)).date()

        records.append({
            "ts_code": ts_code,
            "start_date": start_date,
            "standard": "SW2021",
            "industry_l1": l1,
            "industry_l2": code_raw,
        })

    if unmapped:
        print(f"[industry] 警告: {len(unmapped)} 个未映射的 code 前缀: {sorted(unmapped)}")

    df = pd.DataFrame(records)
    print(f"[industry] 映射后 {len(df)} 条记录, {df['ts_code'].nunique()} 只股票")
    return _compute_end_dates(df)


def ingest_industry(conn, csv_dir: str | None = None) -> int:
    """导入申万行业分类历史到 pit_industry_history。"""
    raw = _load_industry_raw(csv_dir)
    df = _transform_industry(raw)

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE public.pit_industry_history")
        insert_sql = """
            INSERT INTO public.pit_industry_history
                (ts_code, start_date, end_date, standard, industry_l1, industry_l2, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        batch = [
            (
                r["ts_code"],
                r["start_date"],
                r["end_date"] if pd.notna(r["end_date"]) else None,
                r["standard"],
                r["industry_l1"],
                r["industry_l2"],
            )
            for _, r in df.iterrows()
        ]
        cur.executemany(insert_sql, batch)
    conn.commit()

    count = len(batch)
    print(f"[industry] 写入 pit_industry_history {count} 条")
    return count


def _ensure_index_constituents_table(conn) -> None:
    """确保 pit_index_constituents 表存在。"""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.pit_index_constituents (
                index_code VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                start_date DATE,
                end_date DATE,
                source VARCHAR,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    conn.commit()


def ingest_index(conn, csv_dir: str | None = None) -> int:
    """导入中证800成分数据到 pit_index_constituents。"""
    _ensure_index_constituents_table(conn)

    raw = _load_index_raw(csv_dir)

    if "品种代码" not in raw.columns:
        raise ValueError(f"指数成分数据列不符合预期: {list(raw.columns)}")

    records = []
    for _, row in raw.iterrows():
        code_raw = str(row["品种代码"]).strip()
        entry_raw = row["纳入日期"]

        symbol = normalize_stock_symbol(code_raw)

        if pd.isna(entry_raw) or str(entry_raw).strip() == "":
            start_date = None
        elif isinstance(entry_raw, (date, datetime)):
            start_date = entry_raw if isinstance(entry_raw, date) else entry_raw.date()
        else:
            start_date = pd.to_datetime(str(entry_raw)).date()

        records.append({
            "index_code": "000906.SH",
            "symbol": symbol,
            "start_date": start_date,
            "end_date": None,
            "source": "akshare_index_stock_cons",
        })

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE public.pit_index_constituents")
        insert_sql = """
            INSERT INTO public.pit_index_constituents
                (index_code, symbol, start_date, end_date, source, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """
        batch = [
            (r["index_code"], r["symbol"], r["start_date"], r["end_date"], r["source"])
            for r in records
        ]
        cur.executemany(insert_sql, batch)
    conn.commit()

    count = len(batch)
    print(f"[index] 写入 pit_index_constituents {count} 条")
    return count


def update_security_master_industry(conn) -> int:
    """用每只股票最新的行业分类更新 pit_security_master.industry。"""
    sql = """
        UPDATE public.pit_security_master sm
        SET industry = sub.industry_l1
        FROM (
            SELECT DISTINCT ON (ts_code) ts_code, industry_l1
            FROM public.pit_industry_history
            ORDER BY ts_code, start_date DESC
        ) sub
        WHERE sm.symbol = sub.ts_code
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        updated = cur.rowcount
    conn.commit()
    print(f"[update-master] 更新 pit_security_master.industry {updated} 条")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Universe 数据导入脚本")
    parser.add_argument("--industry", action="store_true", help="导入申万行业分类历史")
    parser.add_argument("--index", action="store_true", help="导入中证800成分")
    parser.add_argument("--update-master", action="store_true", help="更新 pit_security_master.industry")
    parser.add_argument("--all", action="store_true", help="全部导入")
    parser.add_argument("--fetch-only", action="store_true", help="仅从 AKShare 拉取数据保存为 CSV（不写 DB）")
    parser.add_argument("--from-csv", type=str, default=None, help="从 CSV 目录加载数据（不调 AKShare API）")
    parser.add_argument("--csv-dir", type=str, default="./data_cache", help="--fetch-only 的输出目录")
    args = parser.parse_args()

    # --fetch-only 模式: 只拉取数据保存 CSV
    if args.fetch_only:
        fetch_and_save(args.csv_dir)
        print("[done] 数据已保存，可用 --from-csv 导入到数据库")
        return

    if not any([args.industry, args.index, args.update_master, args.all]):
        parser.print_help()
        sys.exit(1)

    conn = _get_db_conn()
    csv_dir = args.from_csv
    try:
        if args.industry or args.all:
            ingest_industry(conn, csv_dir)
        if args.index or args.all:
            ingest_index(conn, csv_dir)
        if args.update_master or args.all:
            update_security_master_industry(conn)
    finally:
        conn.close()

    print("[done] 导入完成")


if __name__ == "__main__":
    main()

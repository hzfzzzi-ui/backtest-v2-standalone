"""Universe 数据导入脚本 — 从 AKShare 拉取行业分类历史 + 中证800 成分 + 申万行业指数日线。

用法:
  # 两步式（Docker 无外网时）:
  python -m backend.core.universe.ingest_universe --fetch-only --csv-dir ./data_cache
  docker-compose exec backtest-v2-standalone python -m backend.core.universe.ingest_universe --all --from-csv /app/data_cache

  # 仅拉取+导入申万行业指数日线:
  python -m backend.core.universe.ingest_universe --fetch-only --csv-dir ./data_cache
  docker-compose exec backtest-v2-standalone python -m backend.core.universe.ingest_universe --sw-index --from-csv /app/data_cache

  # 一步式（有外网时）:
  python -m backend.core.universe.ingest_universe --all
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

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

# 历史申万前缀元数据。核心目的是保留历史分类语义，并给运行时一个
# contemporaneous bridge 的指数代码映射，而不是把所有历史记录都折算成 SW2021。
SW_PREFIX_META: dict[str, dict[str, str]] = {
    "11": {"standard": "SW2021", "industry_l1": "农林牧渔", "index_code": "801010.SI"},
    "21": {"standard": "SW_LEGACY", "industry_l1": "采掘", "index_code": "801020.SI"},
    "22": {"standard": "SW2021", "industry_l1": "基础化工", "index_code": "801030.SI"},
    "23": {"standard": "SW2021", "industry_l1": "钢铁", "index_code": "801040.SI"},
    "24": {"standard": "SW2021", "industry_l1": "有色金属", "index_code": "801050.SI"},
    "25": {"standard": "SW_LEGACY", "industry_l1": "化工", "index_code": "801030.SI"},
    "26": {"standard": "SW_LEGACY", "industry_l1": "钢铁", "index_code": "801040.SI"},
    "27": {"standard": "SW2021", "industry_l1": "电子", "index_code": "801080.SI"},
    "28": {"standard": "SW2021", "industry_l1": "汽车", "index_code": "801880.SI"},
    "31": {"standard": "SW_LEGACY", "industry_l1": "建筑材料", "index_code": "801061.SI"},
    "32": {"standard": "SW_LEGACY", "industry_l1": "建筑装饰", "index_code": "801062.SI"},
    "33": {"standard": "SW2021", "industry_l1": "家用电器", "index_code": "801110.SI"},
    "34": {"standard": "SW2021", "industry_l1": "食品饮料", "index_code": "801120.SI"},
    "35": {"standard": "SW2021", "industry_l1": "纺织服饰", "index_code": "801130.SI"},
    "36": {"standard": "SW2021", "industry_l1": "轻工制造", "index_code": "801140.SI"},
    "37": {"standard": "SW2021", "industry_l1": "医药生物", "index_code": "801150.SI"},
    "41": {"standard": "SW2021", "industry_l1": "公用事业", "index_code": "801160.SI"},
    "42": {"standard": "SW2021", "industry_l1": "交通运输", "index_code": "801170.SI"},
    "43": {"standard": "SW2021", "industry_l1": "房地产", "index_code": "801180.SI"},
    "44": {"standard": "SW_LEGACY", "industry_l1": "商业贸易", "index_code": "801200.SI"},
    "45": {"standard": "SW2021", "industry_l1": "商贸零售", "index_code": "801200.SI"},
    "46": {"standard": "SW2021", "industry_l1": "社会服务", "index_code": "801210.SI"},
    "47": {"standard": "SW_LEGACY", "industry_l1": "休闲服务", "index_code": "801210.SI"},
    "48": {"standard": "SW2021", "industry_l1": "银行", "index_code": "801780.SI"},
    "49": {"standard": "SW2021", "industry_l1": "非银金融", "index_code": "801790.SI"},
    "51": {"standard": "SW2021", "industry_l1": "综合", "index_code": "801230.SI"},
    "61": {"standard": "SW2021", "industry_l1": "建筑材料", "index_code": "801710.SI"},
    "62": {"standard": "SW2021", "industry_l1": "建筑装饰", "index_code": "801720.SI"},
    "63": {"standard": "SW2021", "industry_l1": "电力设备", "index_code": "801730.SI"},
    "64": {"standard": "SW2021", "industry_l1": "机械设备", "index_code": "801890.SI"},
    "65": {"standard": "SW2021", "industry_l1": "国防军工", "index_code": "801740.SI"},
    "71": {"standard": "SW2021", "industry_l1": "计算机", "index_code": "801750.SI"},
    "72": {"standard": "SW2021", "industry_l1": "传媒", "index_code": "801760.SI"},
    "73": {"standard": "SW2021", "industry_l1": "通信", "index_code": "801770.SI"},
    "74": {"standard": "SW2021", "industry_l1": "煤炭", "index_code": "801950.SI"},
    "75": {"standard": "SW2021", "industry_l1": "石油石化", "index_code": "801960.SI"},
    "76": {"standard": "SW2021", "industry_l1": "环保", "index_code": "801970.SI"},
    "77": {"standard": "SW2021", "industry_l1": "美容护理", "index_code": "801980.SI"},
}

# ── 申万 L1 行业名 → 行业指数代码 ─────────────────────────────────────
# industry_l1 名称（pit_industry_history 中的值）→ 申万行业指数代码（pit_index_daily 中的 index_code）
SW_L1_INDEX_MAP: dict[str, str] = {
    "农林牧渔": "801010.SI",
    "基础化工": "801030.SI",
    "钢铁": "801040.SI",
    "有色金属": "801050.SI",
    "电子": "801080.SI",
    "汽车": "801880.SI",
    "家用电器": "801110.SI",
    "食品饮料": "801120.SI",
    "纺织服饰": "801130.SI",
    "轻工制造": "801140.SI",
    "医药生物": "801150.SI",
    "公用事业": "801160.SI",
    "交通运输": "801170.SI",
    "房地产": "801180.SI",
    "商贸零售": "801200.SI",
    "社会服务": "801210.SI",
    "银行": "801780.SI",
    "非银金融": "801790.SI",
    "综合": "801230.SI",
    "建筑材料": "801710.SI",
    "建筑装饰": "801720.SI",
    "电力设备": "801730.SI",
    "机械设备": "801890.SI",
    "国防军工": "801740.SI",
    "计算机": "801750.SI",
    "传媒": "801760.SI",
    "通信": "801770.SI",
    "煤炭": "801950.SI",
    "石油石化": "801960.SI",
    "环保": "801970.SI",
    "美容护理": "801980.SI",
}

_INDUSTRY_CSV = "industry_clf_hist_sw.csv"
_INDEX_CSV = "index_stock_cons_000906.csv"
_SW_INDEX_DAILY_CSV = "sw_index_daily.csv"
_SW_INDEX_START_DATE = "2007-01-01"
_SW_INDEX_EXTRA_CODES: tuple[str, ...] = ("801020", "801061", "801062")


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
    meta = SW_PREFIX_META.get(prefix)
    return None if meta is None else str(meta["industry_l1"])


def _resolve_prefix_meta(code: str) -> dict[str, str] | None:
    prefix = str(code).strip()[:2]
    meta = SW_PREFIX_META.get(prefix)
    return dict(meta) if meta is not None else None


def resolve_sw_index_code_from_industry_code(code: str) -> str | None:
    meta = _resolve_prefix_meta(code)
    if meta is None:
        return None
    index_code = str(meta.get("index_code") or "").strip().upper()
    return index_code or None


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


def _fetch_sw_index_daily(start_date: str = _SW_INDEX_START_DATE) -> pd.DataFrame:
    """从 AKShare 拉取所有申万 L1 行业指数日线数据。"""
    codes = sorted(
        {
            str(meta["index_code"]).replace(".SI", "")
            for meta in SW_PREFIX_META.values()
            if str(meta.get("standard")) == "SW2021"
        }
        | set(_SW_INDEX_EXTRA_CODES)
    )
    print(f"[fetch] 申万行业指数: {len(codes)} 个（含历史兼容代码）")

    all_frames = []
    for i, code in enumerate(codes):
        print(f"[fetch] ({i + 1}/{len(codes)}) 拉取 {code} 日线 ...")
        df = _fetch_sw_index_daily_by_code(code)
        all_frames.append(df)
        if i < len(codes) - 1:
            time.sleep(0.3)

    combined = pd.concat(all_frames, ignore_index=True)

    # Filter by start_date — col[1] is date
    date_col = combined.columns[1]
    combined[date_col] = pd.to_datetime(combined[date_col])
    combined = combined[combined[date_col] >= start_date].reset_index(drop=True)

    print(f"[fetch] 合计 {len(combined)} 条 (>= {start_date})")
    return combined


def _fetch_sw_index_daily_by_code(code: str, retries: int = 3) -> pd.DataFrame:
    url = "https://www.swsresearch.com/institute-sw/api/index_publish/trend/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
    }
    params = {"swindexcode": str(code).replace(".SI", ""), "period": "DAY"}
    last_exc: Exception | None = None
    for attempt in range(1, int(retries) + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, verify=False, timeout=60)
            resp.raise_for_status()
            data_json = resp.json()
            rows = list(data_json.get("data") or [])
            if not rows:
                return pd.DataFrame(columns=["代码", "日期", "收盘", "开盘", "最高", "最低", "成交量", "成交额"])
            temp_df = pd.DataFrame(rows)
            temp_df.rename(
                columns={
                    "swindexcode": "代码",
                    "bargaindate": "日期",
                    "openindex": "开盘",
                    "maxindex": "最高",
                    "minindex": "最低",
                    "closeindex": "收盘",
                    "bargainamount": "成交量",
                    "bargainsum": "成交额",
                },
                inplace=True,
            )
            temp_df = temp_df[["代码", "日期", "收盘", "开盘", "最高", "最低", "成交量", "成交额"]]
            temp_df["日期"] = pd.to_datetime(temp_df["日期"], errors="coerce").dt.date
            for col in ("收盘", "开盘", "最高", "最低", "成交量", "成交额"):
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
            return temp_df
        except Exception as exc:  # pragma: no cover - depends on network
            last_exc = exc
            if attempt < int(retries):
                time.sleep(float(attempt))
    raise RuntimeError(f"failed to fetch SW index daily for {code}: {last_exc}")


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

    sw_daily = _fetch_sw_index_daily()
    sw_path = out / _SW_INDEX_DAILY_CSV
    sw_daily.to_csv(str(sw_path), index=False, encoding="utf-8-sig")
    print(f"[fetch] 已保存 {sw_path} ({len(sw_daily)} 行)")


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


def _load_sw_index_raw(csv_dir: str | None) -> pd.DataFrame:
    """从 AKShare 或 CSV 加载申万行业指数日线数据。"""
    if csv_dir:
        p = Path(csv_dir) / _SW_INDEX_DAILY_CSV
        print(f"[sw-index] 从 CSV 加载: {p}")
        return pd.read_csv(str(p))
    return _fetch_sw_index_daily()


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

        meta = _resolve_prefix_meta(code_raw)
        if meta is None:
            unmapped.add(code_raw[:2])
            continue
        l1 = str(meta["industry_l1"])

        ts_code = normalize_stock_symbol(symbol_raw)

        if isinstance(start_raw, (date, datetime)):
            start_date = start_raw if isinstance(start_raw, date) else start_raw.date()
        else:
            start_date = pd.to_datetime(str(start_raw)).date()

        records.append({
            "ts_code": ts_code,
            "start_date": start_date,
            "standard": str(meta["standard"]),
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
        # Preserve non-CSI800 constituent rows such as CSI1000.
        cur.execute("DELETE FROM public.pit_index_constituents WHERE index_code = '000906.SH'")
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


def ingest_sw_index(conn, csv_dir: str | None = None) -> int:
    """导入申万 L1 行业指数日线到 pit_index_daily。"""
    raw = _load_sw_index_raw(csv_dir)

    # Rename by position (encoding-safe): code, date, close, open, high, low, volume, turnover
    raw.columns = ["code", "date", "close", "open", "high", "low", "volume", "turnover"]

    raw["index_code"] = raw["code"].astype(str).str.strip().apply(
        lambda c: f"{c}.SI" if not c.endswith(".SI") else c
    )
    raw["trade_date"] = pd.to_datetime(raw["date"]).dt.date
    raw["open"] = pd.to_numeric(raw["open"], errors="coerce").fillna(0.0)
    raw["high"] = pd.to_numeric(raw["high"], errors="coerce").fillna(0.0)
    raw["low"] = pd.to_numeric(raw["low"], errors="coerce").fillna(0.0)
    raw["close"] = pd.to_numeric(raw["close"], errors="coerce").fillna(0.0)
    # 亿股 → 股, 亿元 → 元
    raw["vol_shares"] = (pd.to_numeric(raw["volume"], errors="coerce").fillna(0.0) * 1e8).astype(int)
    raw["to_yuan"] = pd.to_numeric(raw["turnover"], errors="coerce").fillna(0.0) * 1e8

    records = list(
        raw[["index_code", "trade_date", "open", "high", "low", "close", "vol_shares", "to_yuan"]]
        .itertuples(index=False, name=None)
    )

    n_codes = raw["index_code"].nunique()
    print(f"[sw-index] 准备写入 {len(records)} 条, {n_codes} 个行业指数")

    with conn.cursor() as cur:
        cur.execute("DELETE FROM public.pit_index_daily WHERE index_code LIKE '801%.SI'")
        deleted = cur.rowcount
        if deleted:
            print(f"[sw-index] 清理旧数据 {deleted} 条")

        insert_sql = """
            INSERT INTO public.pit_index_daily
                (index_code, trade_date, open, high, low, close, volume, turnover, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        cur.executemany(insert_sql, records)
    conn.commit()

    print(f"[sw-index] 写入 pit_index_daily {len(records)} 条")
    return len(records)


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
    parser.add_argument("--sw-index", action="store_true", help="导入申万 L1 行业指数日线")
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

    if not any([args.industry, args.index, args.sw_index, args.update_master, args.all]):
        parser.print_help()
        sys.exit(1)

    conn = _get_db_conn()
    csv_dir = args.from_csv
    try:
        if args.industry or args.all:
            ingest_industry(conn, csv_dir)
        if args.index or args.all:
            ingest_index(conn, csv_dir)
        if args.sw_index or args.all:
            ingest_sw_index(conn, csv_dir)
        if args.update_master or args.all:
            update_security_master_industry(conn)
    finally:
        conn.close()

    print("[done] 导入完成")


if __name__ == "__main__":
    main()

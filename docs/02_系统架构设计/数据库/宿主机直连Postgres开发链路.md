# 宿主机直连 Postgres 开发链路

## 目标

在不改变容器内正式运行路径的前提下，让宿主机脚本、`pytest`、临时排查命令可以直接连接 `pams` PostgreSQL。

正式要求：

- 容器内继续使用 `pams-postgres:5432`
- 宿主机默认使用 `127.0.0.1:${PAMS_HOST_PG_PORT}`
- 宿主机直连仅用于开发、测试、排查，不改变运行时研究口径

## 当前实现

`docker-compose.yml` 新增了 `pams-pg-host-proxy`：

- 监听 `127.0.0.1:${PAMS_HOST_PG_PORT}`
- 转发到 Docker 网络中的 `pams-postgres:5432`

`.env` 中默认提供宿主机开发值：

- `PAMS_HOST_PG_PORT=15432`
- `PAMS_PG_HOST=127.0.0.1`
- `PAMS_PG_PORT=15432`
- `PAMS_PG_DBNAME=pams`
- `PAMS_PG_USER=pams`
- 密码统一仍使用 `POSTGRES_PASSWORD`

容器服务在 `docker-compose.yml` 中显式覆盖这些变量，因此：

- 宿主机读取 `.env` 时会默认走 `127.0.0.1`
- 容器内不会被污染，仍走 `pams-postgres`

宿主机开发链的统一解析 helper 为：

- [backend/core/data/pg_env.py](/c:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/core/data/pg_env.py)

当前已切到该 helper 的高频入口包括：

- `backend/core/config/loader.py`
- `backend/core/services/ops_domain_pg.py`
- `backend/cli/managed/cn_side_table_common.py`
- `backend/cli/managed/update_pams_ohlcv_daily.py`
- `backend/cli/managed/refresh_security_master.py`
- `backend/scripts/update_pit_index_daily.py`
- `backend/scripts/import_csi800_pit.py`
- `backend/scripts/import_csi1000_pit.py`
- `backend/scripts/import_cn_daily_basic_liquidity.py`
- `backend/scripts/apply_proven_price_gap_rows.py`
- `backend/scripts/repair_price_gap_suspensions.py`
- `backend/scripts/audit_price_gap_anomalies.py`
- `backend/scripts/rebuild_pams_limit_prices_baostock.py`
- `backend/scripts/backfill_csi800_ohlcv_baostock.py`
- `backend/scripts/backfill_csi800_st_baostock.py`
- `backend/scripts/backfill_csi800_st_history_baostock.py`
- `backend/scripts/ops/audit_csi800_baseline_data.py`

## 使用方式

### 启动

```powershell
docker compose up -d
```

启动后，宿主机可直接连接：

```text
host=127.0.0.1
port=15432
dbname=pams
user=pams
password=.env 中的 POSTGRES_PASSWORD
```

### 验证

```powershell
@'
import os
import psycopg

conn = psycopg.connect(
    host=os.getenv("PAMS_PG_HOST", "127.0.0.1"),
    port=int(os.getenv("PAMS_PG_PORT", "15432")),
    dbname=os.getenv("PAMS_PG_DBNAME", "pams"),
    user=os.getenv("PAMS_PG_USER", "pams"),
    password=os.getenv("POSTGRES_PASSWORD"),
)
with conn, conn.cursor() as cur:
    cur.execute("select current_database(), current_user")
    print(cur.fetchone())
'@ | python -
```

## 约束

- 这条链路只解决宿主机开发/测试直连，不代表所有脚本都可以继续各自直连 SQL。
- 市场数据正式访问边界仍以 [市场数据访问边界](./市场数据访问边界.md) 为准。
- 事务域正式对象仍应优先通过域服务访问；宿主机直连只是开发辅助能力。

## 回退

如需回退宿主机直连链路：

1. 从 `docker-compose.yml` 删除 `pams-pg-host-proxy`
2. 移除 `.env` 中的宿主机 PG 默认值
3. 恢复 `loader.py` 的纯环境变量读取

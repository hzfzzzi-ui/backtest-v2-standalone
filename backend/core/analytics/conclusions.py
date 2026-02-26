from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from backend.core.analytics.schema import normalize_order_status


def build_conclusions(results_dir: str | Path, run_id: str, trade_concentration: dict[str, Any]) -> dict[str, Any]:
    base = Path(results_dir)
    report = _load_json(base / 'report.json')
    summary = _load_json(base / 'report_summary.json')
    warnings = _load_warnings(base / 'warnings.json')
    eq = _read_csv(base / 'equity_curve.csv')
    orders = _read_csv(base / 'orders.csv')
    trades = _read_csv(base / 'trades.csv')
    trade_pnl = _read_csv(base / 'trade_pnl.csv')
    benchmark_curve = _read_csv(base / 'benchmark_curve.csv')
    positions_daily = _read_csv(base / 'positions_daily.csv')

    kpis = summary.get('kpis', {})
    costs = summary.get('costs', report.get('cost_breakdown', {}))
    audit = summary.get('audit', {})
    validation = audit.get('validation', report.get('data_validation', {}))
    benchmark_info = summary.get('benchmark', {})

    consistency_notes: list[str] = []
    items: list[dict[str, Any]] = []

    trades_count = int(len(trades))
    trading_days = int(len(eq)) if not eq.empty else int(kpis.get('trading_days', 0))
    symbols_count, symbols_source = _resolve_symbols_count(trades, positions_daily, summary, report, trades_count)
    benchmark_rows, benchmark_source, benchmark_missing_reason = _resolve_benchmark_rows(benchmark_info, benchmark_curve)

    (
        filled_orders,
        orders_total,
        filled_rate,
        reject_top,
        rejected_count,
        skip_top,
        skipped_count,
        fill_note,
    ) = _calc_order_fill_and_reject(orders, trades_count)
    if fill_note:
        consistency_notes.append(fill_note)

    if trades_count > 0 and filled_orders <= 0:
        filled_orders = trades_count
        filled_rate = filled_orders / max(orders_total, 1)
        consistency_notes.append('orders status mapping missing, fallback to trades_count')

    passed = validation.get('passed', None)
    v_warnings = validation.get('warnings', []) or []
    if passed is False:
        s1 = 'FAIL'
        v1 = 'passed=false'
        d1 = f'validation_warnings={len(v_warnings)}'
    elif passed is True:
        s1 = 'WARN' if len(v_warnings) > 0 else 'PASS'
        v1 = 'passed=true'
        d1 = f'validation_warnings={len(v_warnings)}'
    else:
        s1 = 'PASS'
        v1 = 'not_provided'
        d1 = '未绑定 validate 结果（passed=null）'
    items.append({'id': 1, 'title': '数据验收', 'status': s1, 'value': v1, 'detail': d1})

    no_lookahead = bool(audit.get('no_lookahead_enforced', report.get('no_lookahead_enforced', False)))
    slip_mode = audit.get('slippage_mode', report.get('slippage_mode'))
    limit_source = audit.get('limit_source', report.get('limit_source'))
    limit_fallback_reason = audit.get('limit_fallback_reason', report.get('limit_fallback_reason'))
    eps = audit.get('limit_price_epsilon', report.get('limit_price_epsilon'))
    if not no_lookahead:
        s2 = 'FAIL'
    elif slip_mode and limit_source and eps is not None:
        s2 = 'PASS'
    else:
        s2 = 'WARN'
    items.append(
        {
            'id': 2,
            'title': '审计口径',
            'status': s2,
            'value': f'no_lookahead={no_lookahead}, slippage_mode={slip_mode}, limit_source={limit_source}',
            'detail': f'epsilon={eps}, limit_fallback_reason={limit_fallback_reason}',
        }
    )

    if symbols_count == 0:
        s3 = 'FAIL' if trades_count == 0 else 'WARN'
    elif trading_days < 200:
        s3 = 'WARN'
    else:
        s3 = 'PASS'

    detail3 = f'benchmark_rows={benchmark_rows if benchmark_rows is not None else "NA"}, source={benchmark_source}'
    if benchmark_rows is None:
        s3 = 'WARN' if s3 == 'PASS' else s3
        detail3 = f'{detail3}, reason={benchmark_missing_reason}'
    items.append(
        {
            'id': 3,
            'title': '样本覆盖',
            'status': s3,
            'value': f'trading_days={trading_days}, symbols={symbols_count}({symbols_source})',
            'detail': detail3,
        }
    )

    total_return = _to_num(kpis.get('total_return'), _to_num(report.get('summary', {}).get('total_return_pct')) / 100.0)
    max_dd = _to_num(kpis.get('max_drawdown'), abs(_to_num(report.get('summary', {}).get('max_drawdown_pct')) / 100.0))
    s4 = 'PASS'
    if max_dd >= 0.30 or (total_return < 0 and max_dd >= 0.20):
        s4 = 'WARN'
    items.append(
        {
            'id': 4,
            'title': '收益与回撤',
            'status': s4,
            'value': f'return={total_return:.2%}, max_drawdown={max_dd:.2%}',
            'detail': '阈值：mdd>=30% 或 负收益且 mdd>=20%',
        }
    )

    s5, v5, d5 = _curve_shape(eq)
    items.append({'id': 5, 'title': '净值曲线形态', 'status': s5, 'value': v5, 'detail': d5})

    trades_per_day = trades_count / trading_days if trading_days > 0 else 0.0
    avg_hold = float(trade_pnl['hold_days'].astype(float).mean()) if ('hold_days' in trade_pnl.columns and not trade_pnl.empty) else None
    s6 = 'WARN' if trades_per_day > 0.5 else 'INFO'
    items.append(
        {
            'id': 6,
            'title': '交易频率与持有',
            'status': s6,
            'value': f'trades/day={trades_per_day:.3f}, trades={trades_count}',
            'detail': f'avg_hold_days={avg_hold:.2f}' if avg_hold is not None else 'avg_hold_days=NA',
        }
    )

    reason_top, reason_source = _reason_top3(orders, trades)
    reason_available = len(reason_top) > 0
    _update_reason_code_flag(base, report, reason_available)
    if reason_available:
        s7 = 'INFO'
        d7 = 'top3=' + ', '.join(f'{k}({v})' for k, v in reason_top.items())
    else:
        s7 = 'WARN'
        d7 = 'reason_code 未写入 orders/trades 输出'
    items.append(
        {
            'id': 7,
            'title': '策略行为原因码',
            'status': s7,
            'value': f'reason_count={len(reason_top)}, source={reason_source}',
            'detail': d7,
        }
    )

    fees_total = _to_num(costs.get('fees_total'))
    commission_total = _to_num(costs.get('commission_total'))
    stamp_total = _to_num(costs.get('stamp_tax_total'))
    fee_per_trade = fees_total / trades_count if trades_count > 0 else 0.0
    base_equity = _to_num(eq.iloc[0]['equity']) if (not eq.empty and 'equity' in eq.columns) else 0.0
    fee_ratio = fees_total / base_equity if base_equity > 0 else 0.0
    s8 = 'WARN' if (total_return > 0 and fee_ratio > 0.005) else 'INFO'
    items.append(
        {
            'id': 8,
            'title': '费用成本',
            'status': s8,
            'value': f'fees={fees_total:.2f}, per_trade={fee_per_trade:.2f}',
            'detail': f'commission={commission_total:.2f}, stamp_tax={stamp_total:.2f}, fee_ratio={fee_ratio:.2%}',
        }
    )

    slippage = _to_num(costs.get('slippage_attribution_total'), _to_num(report.get('cost_breakdown', {}).get('slippage_cost_total')))
    s9 = 'WARN' if (slippage <= 0 or slippage > fees_total) else 'INFO'
    items.append(
        {
            'id': 9,
            'title': '滑点归因/执行损耗',
            'status': s9,
            'value': f'slippage_attr={slippage:.2f}',
            'detail': '滑点是归因项，不计入 fees_total',
        }
    )

    s10 = 'WARN' if filled_rate < 0.8 else 'INFO'
    raw_signals_total = int((report.get('audit_rules') or {}).get('raw_signals_total', 0))
    tradable_orders_total = int((report.get('audit_rules') or {}).get('tradable_orders_total', orders_total))
    profile = str((report.get('audit_rules') or {}).get('execution_profile', 'basic'))
    detail10 = (
        f'orders_total={orders_total}, tradable_orders_total={tradable_orders_total}, raw_signals_total={raw_signals_total}, '
        f'filled_orders={filled_orders}, rejected_orders={rejected_count}, skipped_orders={skipped_count}, '
        f'filled_rate={filled_rate:.2%}, top_reject={reject_top}, top_skip={skip_top}'
    )
    if profile == 'tradable':
        detail10 += '；profile=tradable 时策略不变，变化来自“信号到订单的可交易映射”'
    if reject_top and set(reject_top.keys()) == {'NO_CASH'}:
        detail10 += '；大量 NO_CASH 表示资金约束主导成交，策略信号并未全部可执行（先修资金/下单规则再评估策略）'
    if any('fallback to trades_count' in n for n in consistency_notes):
        s10 = 'WARN'
    items.append(
        {
            'id': 10,
            'title': '拒单/未成交结构',
            'status': s10,
            'value': f'filled_rate={filled_rate:.2%}',
            'detail': detail10,
        }
    )

    next_change = _suggested_next_change(items, reject_top, reason_top)
    if consistency_notes:
        next_change['reason'] += ' | ' + '; '.join(consistency_notes)

    payload = {
        'run_id': run_id,
        'items': items,
        'suggested_next_change': next_change,
        'artifacts': {
            'report_summary': 'report_summary.json',
            'report_json': 'report.json',
            'orders_csv': 'orders.csv',
            'trades_csv': 'trades.csv',
            'equity_curve_csv': 'equity_curve.csv',
            'warnings_json': 'warnings.json',
            'benchmark_curve_csv': 'benchmark_curve.csv',
            'trade_pnl_csv': 'trade_pnl.csv',
        },
    }
    (base / 'conclusions_10.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    _write_text(base / 'conclusions_10.txt', payload)
    return payload


def _resolve_symbols_count(
    trades: pd.DataFrame,
    positions_daily: pd.DataFrame,
    summary: dict[str, Any],
    report: dict[str, Any],
    trades_count: int,
) -> tuple[int, str]:
    trade_symbols = _symbols_from_df(trades)
    pos_symbols = _symbols_from_df(positions_daily)
    if trades_count > 0:
        syms = trade_symbols | pos_symbols
        if syms:
            return len(syms), 'trades_union_positions'
        if trade_symbols:
            return len(trade_symbols), 'trades_fallback'
        return 0, 'trades_union_positions'
    if pos_symbols:
        return len(pos_symbols), 'positions_daily'

    cfg_symbols = set(summary.get('universe', {}).get('symbols_sample', []) or [])
    if not cfg_symbols:
        q_meta = (report.get('data_snapshot', {}) or {}).get('query_meta', [])
        for meta in q_meta:
            symbols = meta.get('symbols', [])
            if isinstance(symbols, list):
                cfg_symbols.update(str(x) for x in symbols if str(x).strip())
    return len(cfg_symbols), 'config_fallback'


def _resolve_benchmark_rows(
    benchmark_info: dict[str, Any],
    benchmark_curve: pd.DataFrame,
) -> tuple[int | None, str, str | None]:
    rows = benchmark_info.get('rows', None)
    if rows is not None:
        try:
            return int(rows), 'report_summary.benchmark.rows', None
        except Exception:
            pass
    if not benchmark_curve.empty:
        return int(len(benchmark_curve)), 'benchmark_curve.csv', None
    return None, 'missing', 'benchmark data unavailable'


def _calc_order_fill_and_reject(
    orders: pd.DataFrame,
    trades_count: int,
) -> tuple[int, int, float, dict[str, int], int, dict[str, int], int, str]:
    note = ''
    if orders.empty:
        if trades_count > 0:
            return trades_count, trades_count, 1.0, {}, 0, {}, 0, 'orders.csv empty; fallback to trades_count'
        return 0, 0, 0.0, {}, 0, {}, 0, ''

    df = orders.copy()
    orders_total = int(len(df))
    if 'status' not in df.columns:
        if trades_count > 0:
            filled_orders = trades_count
            filled_rate = filled_orders / max(orders_total, 1)
            return filled_orders, orders_total, filled_rate, {}, 0, {}, 0, 'orders status mapping missing, fallback to trades_count'
        return 0, orders_total, 0.0, {}, 0, {}, 0, 'orders.status missing'

    df['_status'] = df['status'].map(normalize_order_status)
    filled_orders = int(df['_status'].isin(['FILLED', 'PARTIAL_FILLED']).sum())
    reject_df = df[df['_status'].isin(['REJECTED', 'CANCELLED'])].copy()
    if 'reject_stage' in reject_df.columns:
        reject_df = reject_df[reject_df['reject_stage'].astype(str).str.upper() != 'PRECHECK']
    rejected_count = int(len(reject_df))
    skip_df = df[df['status'].astype(str).str.upper() == 'SKIPPED'].copy()
    skipped_count = int(len(skip_df))
    reject_top: dict[str, int] = {}
    if 'reject_reason' in reject_df.columns and not reject_df.empty:
        reject_top = (
            reject_df['reject_reason']
            .astype(str)
            .str.strip()
            .str.upper()
            .replace({'': 'UNKNOWN'})
            .value_counts()
            .head(3)
            .to_dict()
        )
    filled_rate = filled_orders / max(orders_total, 1)
    skip_top: dict[str, int] = {}
    if 'skip_reason' in skip_df.columns and not skip_df.empty:
        skip_top = (
            skip_df['skip_reason']
            .astype(str)
            .str.strip()
            .replace({'': 'UNKNOWN'})
            .value_counts()
            .head(3)
            .to_dict()
        )
    return filled_orders, orders_total, filled_rate, reject_top, rejected_count, skip_top, skipped_count, note


def _reason_top3(orders: pd.DataFrame, trades: pd.DataFrame) -> tuple[dict[str, int], str]:
    if not orders.empty and 'reason_code' in orders.columns:
        top = _top_counts(orders['reason_code'])
        if top:
            return top, 'orders.csv'
    if not trades.empty and 'reason_code' in trades.columns:
        top = _top_counts(trades['reason_code'])
        if top:
            return top, 'trades.csv'
    return {}, 'missing'


def _curve_shape(equity: pd.DataFrame) -> tuple[str, str, str]:
    if equity.empty or 'equity' not in equity.columns:
        return 'WARN', '无净值数据', 'equity_curve 缺失，无法判断形态'
    eq = equity['equity'].astype(float)
    if len(eq) < 5 or float(eq.iloc[0]) == 0.0:
        return 'WARN', '样本不足', '净值点位不足，无法稳定识别形态'

    nav = eq / float(eq.iloc[0])
    mdd = float((nav / nav.cummax() - 1.0).min())
    pos_days_ratio = float((nav.pct_change().fillna(0.0) > 0).mean())
    final_nav = float(nav.iloc[-1])
    start_idx = int(len(nav) * 0.7)
    last30_ret = float(nav.iloc[-1] / nav.iloc[start_idx] - 1.0) if start_idx < len(nav) and float(nav.iloc[start_idx]) != 0 else 0.0

    if final_nav >= 1.2 and mdd > -0.10:
        shape = '单边上行'
        status = 'INFO'
    elif final_nav > 1.0 and last30_ret >= 0:
        shape = '震荡上行'
        status = 'INFO'
    elif final_nav < 1.0 and last30_ret < -0.10:
        shape = '整体下行'
        status = 'WARN'
    elif final_nav < 1.0 and mdd <= -0.20:
        shape = '先涨后崩'
        status = 'WARN'
    else:
        shape = '震荡磨损'
        status = 'WARN'

    detail = f'final_nav={final_nav:.3f}, mdd={mdd:.2%}, last30_ret={last30_ret:.2%}, pos_days_ratio={pos_days_ratio:.2%}'
    return status, shape, detail


def _suggested_next_change(
    items: list[dict[str, Any]],
    reject_top: dict[str, int],
    reason_top: dict[str, int],
) -> dict[str, str]:
    item4 = next((x for x in items if int(x['id']) == 4), {})
    item6 = next((x for x in items if int(x['id']) == 6), {})
    item10 = next((x for x in items if int(x['id']) == 10), {})

    filled_rate = _extract_pct(item10.get('value', ''), 'filled_rate=')
    rejected_count = _extract_int(item10.get('detail', ''), 'rejected_orders=')
    filled_orders = _extract_int(item10.get('detail', ''), 'filled_orders=')
    reject_keys = {str(k).upper() for k in reject_top.keys()}

    if 'NO_CASH' in reject_keys and rejected_count > filled_orders:
        return {
            'code': 'FIX_ORDER_SIZING',
            'reason': f'item10: rejected_count={rejected_count} > filled_orders={filled_orders}, top_reject=NO_CASH',
        }
    if filled_rate < 0.5 and ({'LIMIT_UP', 'LIMIT_DOWN'} & reject_keys):
        return {
            'code': 'AVOID_LIMIT_STOCKS',
            'reason': f'item10: filled_rate={filled_rate:.2%}, top_reject includes LIMIT_UP/LIMIT_DOWN',
        }
    if item6.get('status') == 'WARN' and 'return=-' in str(item4.get('value', '')):
        return {'code': 'ADD_TREND_FILTER', 'reason': 'item6+item4: high turnover with negative return'}
    if _extract_pct(str(item4.get('value', '')), 'max_drawdown=') >= 0.30:
        return {'code': 'TUNE_RISK', 'reason': 'item4: max_drawdown>=30%'}
    return {'code': 'ADD_REGIME_FILTER', 'reason': 'default fallback'}


def _update_reason_code_flag(base: Path, report: dict[str, Any], available: bool) -> None:
    report_path = base / 'report.json'
    if not report_path.exists():
        return
    audit_rules = dict(report.get('audit_rules', {}) or {})
    audit_rules['reason_code_available'] = bool(available)
    report['audit_rules'] = audit_rules
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}


def _load_warnings(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return [str(x) for x in data] if isinstance(data, list) else []
    except Exception:
        return []


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except EmptyDataError:
        return pd.DataFrame()


def _symbols_from_df(df: pd.DataFrame) -> set[str]:
    if df.empty or 'symbol' not in df.columns:
        return set()
    s = df['symbol'].astype(str).str.strip()
    s = s[s != '']
    return set(s.tolist())


def _top_counts(series: pd.Series) -> dict[str, int]:
    c = series.astype(str).str.strip()
    c = c[c != '']
    if c.empty:
        return {}
    return c.value_counts().head(3).to_dict()


def _to_num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _extract_pct(text: str, key: str) -> float:
    try:
        i = text.index(key) + len(key)
        j = text.find(',', i)
        raw = text[i:] if j < 0 else text[i:j]
        raw = raw.strip().rstrip('%')
        return float(raw) / 100.0
    except Exception:
        return 0.0


def _extract_int(text: str, key: str) -> int:
    try:
        i = text.index(key) + len(key)
        j = text.find(',', i)
        raw = text[i:] if j < 0 else text[i:j]
        return int(raw.strip())
    except Exception:
        return 0


def _write_text(path: Path, payload: dict[str, Any]) -> None:
    lines = [f"run_id: {payload.get('run_id', '')}"]
    for item in payload.get('items', []):
        lines.append(f"{item['id']}. [{item['status']}] {item['title']} | {item['value']} | {item['detail']}")
    nxt = payload.get('suggested_next_change', {})
    lines.append(f"next: {nxt.get('code', '')} | {nxt.get('reason', '')}")
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

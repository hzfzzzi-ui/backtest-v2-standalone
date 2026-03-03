"""Alpha Strategy v1 — 自动化多阶段实验脚本。

通过 HTTP API 提交回测任务，实现：
  Phase 0: 基线对照（B0 无 strength_rank vs B1 有 strength_rank）
  Phase 1: S1_MOMO 动量选股（5 参数变体 + WF + 成本敏感度）
  Phase 2: S2_REGIME 制度自适应（5 参数变体 + WF + 成本敏感度）
  Phase 3: S3_LOWTURN 低换手动量（4 参数变体 + WF + 成本敏感度）

用法:
  python -m backend.scripts.run_alpha_v1 --base-url http://localhost:8000 --phase 0
  python -m backend.scripts.run_alpha_v1 --base-url http://localhost:8000 --phase all
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────

FULL_START = "2015-01-01"
FULL_END = "2025-01-01"

COMMON_PARAMS: dict[str, Any] = {
    "config_path": "configs/pams_cn_pg.json",
    "workbench_mode": "workbench",
    "universe_mode": "ALL_A",
    "universe_limit": 800,
    "base_order_value": 10000,
    "price_adj": "hfq",
    "start_date": FULL_START,
    "end_date": FULL_END,
}

COST_TIERS = {
    "5bp": {"commission_rate": 0.0005, "stamp_tax_rate": 0.001},
    "15bp": {"commission_rate": 0.0015, "stamp_tax_rate": 0.001},
    "30bp": {"commission_rate": 0.003, "stamp_tax_rate": 0.001},
    "50bp": {"commission_rate": 0.005, "stamp_tax_rate": 0.001},
}

WF_WINDOWS = [
    (f"{y}-01-01", f"{y + 1}-01-01") for y in range(2015, 2025)
]

# ── 决策门阈值 ────────────────────────────────────────────────

GATE0_MIN_IMPROVEMENT_PP = 3.0  # B1 - B0 CAGR 改善最少 3 个百分点
GATE_MIN_CAGR = 0.0  # Phase A 最佳变体 CAGR > 0%
GATE_MIN_TRADES_PER_YEAR = 50
GATE_MAX_TRADES_PER_YEAR = 400
GATE_MIN_WIN_RATE = 0.35


# ── HTTP 客户端 ───────────────────────────────────────────────

class ExperimentClient:
    """HTTP API 客户端：提交实验、轮询结果、提取指标。"""

    def __init__(self, base_url: str, poll_interval: int = 30, timeout: int = 1200):
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.timeout = timeout

    def submit_job(self, payload: dict[str, Any]) -> str:
        """提交异步回测任务，返回 job_id。"""
        url = f"{self.base_url}/api/backtest_v2/experiment/run_async"
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        job_id = data.get("job_id", "")
        if not job_id:
            raise RuntimeError(f"未返回 job_id: {data}")
        logger.info("已提交任务 %s", job_id)
        return job_id

    def poll_job(self, job_id: str) -> dict[str, Any]:
        """轮询直到任务完成，返回完整结果。"""
        url = f"{self.base_url}/api/backtest_v2/jobs/{job_id}"
        t0 = time.time()
        while True:
            elapsed = time.time() - t0
            if elapsed > self.timeout:
                raise TimeoutError(f"任务 {job_id} 超时 ({self.timeout}s)")
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                logger.warning("轮询失败 (%s), 重试...", exc)
                time.sleep(self.poll_interval)
                continue

            status = str(data.get("status", "")).lower()
            pct = data.get("progress_pct", 0)
            msg = data.get("message", "")
            logger.info("  [%s] %d%% — %s (%.0fs)", job_id[:8], pct, msg, elapsed)

            if status == "success":
                return data.get("result", data)
            if status in ("failed", "canceled"):
                error = data.get("error", data.get("message", "unknown"))
                raise RuntimeError(f"任务 {job_id} 失败: {error}")

            time.sleep(self.poll_interval)

    def run_and_wait(self, payload: dict[str, Any]) -> dict[str, Any]:
        """提交 + 轮询，返回结果字典。"""
        job_id = self.submit_job(payload)
        return self.poll_job(job_id)

    @staticmethod
    def extract_metrics(result: dict[str, Any]) -> dict[str, Any]:
        """从结果字典提取关键指标。"""
        return {
            "cagr": float(result.get("cagr", 0) or 0),
            "sharpe": float(result.get("sharpe", 0) or 0),
            "max_drawdown": float(result.get("max_drawdown", 0) or 0),
            "calmar": float(result.get("calmar", 0) or 0),
            "total_return": float(result.get("total_return", 0) or 0),
            "trades": int(result.get("trades", result.get("closed_trades", 0)) or 0),
            "avg_positions": float(result.get("avg_positions", 0) or 0),
            "exit_take_profit_count": int(result.get("exit_take_profit_count", 0) or 0),
            "exit_fixed_stop_count": int(result.get("exit_fixed_stop_count", 0) or 0),
            "exit_atr_stop_count": int(result.get("exit_atr_stop_count", 0) or 0),
            "exit_atr_trail_count": int(result.get("exit_atr_trail_count", 0) or 0),
            "exit_time_exit_count": int(result.get("exit_time_exit_count", 0) or 0),
            "exit_signal_count": int(result.get("exit_signal_count", 0) or 0),
            "market_filter_bull_days": int(result.get("market_filter_bull_days", 0) or 0),
            "market_filter_bear_days": int(result.get("market_filter_bear_days", 0) or 0),
            "exp_id": str(result.get("exp_id", "")),
            "results_dir": str(result.get("results_dir", "")),
        }


# ── 参数构建器 ────────────────────────────────────────────────

def _build_wb_config(
    strategy: str,
    signal_generation: dict[str, Any],
    exit_rules: dict[str, Any],
    costs: dict[str, Any],
    position_risk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建 workbench_config 字典。"""
    wb: dict[str, Any] = {
        "signal_generation": signal_generation,
        "exit_rules": exit_rules,
        "costs": costs,
    }
    if position_risk:
        wb["position_risk"] = position_risk
    return wb


def build_baseline_b0() -> dict[str, Any]:
    """B0: 当前基线（无 strength_rank）。"""
    payload = {
        **COMMON_PARAMS,
        "enable_strength_rank": False,
        "max_positions": 10,
        "workbench_config": _build_wb_config(
            strategy="EMA_CROSS",
            signal_generation={
                "strategy": "EMA_CROSS",
                "ema": {"fast_ma": 8, "slow_ma": 25},
            },
            exit_rules={
                "take_profit": {"enabled": True, "mode": "pct", "pct": 0.30},
                "atr_stop": {"enabled": True, "k": 2.0},
                "trailing": {"enabled": True, "k": 6.0},
                "hold_constraint": {"min_hold_days": 5, "cooldown_days": 5},
            },
            costs=COST_TIERS["30bp"],
        ),
    }
    return payload


def build_baseline_b1() -> dict[str, Any]:
    """B1: 基线 + strength_rank。"""
    payload = build_baseline_b0()
    payload["enable_strength_rank"] = True
    payload["strength_ma"] = 120
    return payload


def _s1_exit_rules(trail_k: float = 5.0, time_exit_days: int = 45) -> dict[str, Any]:
    """S1_MOMO 退出规则模板。"""
    rules: dict[str, Any] = {
        "take_profit": {"enabled": True, "mode": "pct", "pct": 0.25},
        "atr_stop": {"enabled": True, "k": 2.5},
        "fixed_stop": {"enabled": True, "pct": 0.08},
        "trailing": {"enabled": True, "k": trail_k},
        "hold_constraint": {"min_hold_days": 10, "cooldown_days": 15},
    }
    if time_exit_days > 0:
        rules["time_exit"] = {"enabled": True, "n_days": time_exit_days}
    return rules


def build_s1_variants() -> dict[str, dict[str, Any]]:
    """S1_MOMO: 5 个参数变体。"""
    grid = {
        "S1_CENTER": {"fast": 10, "slow": 30, "trail_k": 5.0, "time_exit": 45},
        "S1_FAST": {"fast": 8, "slow": 25, "trail_k": 5.0, "time_exit": 45},
        "S1_SLOW": {"fast": 12, "slow": 40, "trail_k": 5.0, "time_exit": 45},
        "S1_TIGHT": {"fast": 10, "slow": 30, "trail_k": 4.0, "time_exit": 45},
        "S1_LONG": {"fast": 10, "slow": 30, "trail_k": 5.0, "time_exit": 60},
    }
    variants: dict[str, dict[str, Any]] = {}
    for name, p in grid.items():
        variants[name] = {
            **COMMON_PARAMS,
            "enable_strength_rank": True,
            "strength_ma": 120,
            "max_positions": 10,
            "workbench_config": _build_wb_config(
                strategy="EMA_CROSS",
                signal_generation={
                    "strategy": "EMA_CROSS",
                    "ema": {"fast_ma": p["fast"], "slow_ma": p["slow"]},
                },
                exit_rules=_s1_exit_rules(p["trail_k"], p["time_exit"]),
                costs=COST_TIERS["30bp"],
                position_risk={
                    "market_filter": {
                        "enabled": True,
                        "slope_ma_period": 50,
                        "slope_window": 10,
                        "light_multiplier": 0.6,
                    },
                },
            ),
        }
    return variants


def build_s2_variants() -> dict[str, dict[str, Any]]:
    """S2_REGIME: 5 个参数变体。"""
    grid = {
        "S2_CENTER": {"regime_ma": 50, "trail_k": 6.0, "rsi_buy": 25, "mr_hold": 5},
        "S2_FAST_REG": {"regime_ma": 40, "trail_k": 6.0, "rsi_buy": 25, "mr_hold": 5},
        "S2_SLOW_REG": {"regime_ma": 60, "trail_k": 6.0, "rsi_buy": 25, "mr_hold": 5},
        "S2_DEEP_RSI": {"regime_ma": 50, "trail_k": 6.0, "rsi_buy": 20, "mr_hold": 5},
        "S2_LONG_MR": {"regime_ma": 50, "trail_k": 6.0, "rsi_buy": 25, "mr_hold": 8},
    }
    variants: dict[str, dict[str, Any]] = {}
    for name, p in grid.items():
        variants[name] = {
            **COMMON_PARAMS,
            "enable_strength_rank": True,
            "strength_ma": 120,
            "max_positions": 10,
            "workbench_config": _build_wb_config(
                strategy="REGIME_ROUTER",
                signal_generation={
                    "strategy": "REGIME_ROUTER",
                    "regime_detection": {"regime_ma": p["regime_ma"]},
                    "trend": {"strategy": "EMA_CROSS", "fast_ma": 8, "slow_ma": 25},
                    "mr": {
                        "rsi_period": 6,
                        "rsi_buy_threshold": p["rsi_buy"],
                        "rsi_sell_threshold": 75,
                        "mr_max_hold_days": p["mr_hold"],
                        "mr_stop_loss_pct": 0.05,
                    },
                },
                exit_rules={
                    "take_profit": {"enabled": True, "mode": "pct", "pct": 0.30},
                    "atr_stop": {"enabled": True, "k": 2.0},
                    "trailing": {"enabled": True, "k": p["trail_k"]},
                    "hold_constraint": {"min_hold_days": 5, "cooldown_days": 10},
                },
                costs=COST_TIERS["30bp"],
            ),
        }
    return variants


def build_s3_variants() -> dict[str, dict[str, Any]]:
    """S3_LOWTURN: 4 个参数变体。"""
    grid = {
        "S3_CENTER": {"fast": 15, "slow": 40, "trail_k": 6.0, "time_exit": 60, "max_pos": 8},
        "S3_FASTER": {"fast": 12, "slow": 30, "trail_k": 6.0, "time_exit": 60, "max_pos": 8},
        "S3_WIDER": {"fast": 15, "slow": 40, "trail_k": 7.0, "time_exit": 60, "max_pos": 8},
        "S3_MORE": {"fast": 15, "slow": 40, "trail_k": 6.0, "time_exit": 60, "max_pos": 10},
    }
    variants: dict[str, dict[str, Any]] = {}
    for name, p in grid.items():
        variants[name] = {
            **COMMON_PARAMS,
            "enable_strength_rank": True,
            "strength_ma": 120,
            "enable_multifactor_rank": True,
            "max_positions": p["max_pos"],
            "workbench_config": _build_wb_config(
                strategy="EMA_CROSS",
                signal_generation={
                    "strategy": "EMA_CROSS",
                    "ema": {"fast_ma": p["fast"], "slow_ma": p["slow"]},
                },
                exit_rules={
                    "take_profit": {"enabled": False},
                    "atr_stop": {"enabled": False},
                    "fixed_stop": {"enabled": True, "pct": 0.10},
                    "trailing": {"enabled": True, "k": p["trail_k"]},
                    "time_exit": {"enabled": True, "n_days": p["time_exit"]},
                    "hold_constraint": {"min_hold_days": 15, "cooldown_days": 20},
                },
                costs=COST_TIERS["30bp"],
            ),
        }
    return variants


def build_wf_payloads(base_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """从基础 payload 生成 10 × 1 年 walk-forward 窗口切片。"""
    payloads: dict[str, dict[str, Any]] = {}
    for start, end in WF_WINDOWS:
        year = start[:4]
        name = f"WF_{year}"
        p = json.loads(json.dumps(base_payload))
        p["start_date"] = start
        p["end_date"] = end
        payloads[name] = p
    return payloads


def build_cost_payloads(base_payload: dict[str, Any], skip_30bp: bool = True) -> dict[str, dict[str, Any]]:
    """从基础 payload 生成 4 档成本敏感度变体。"""
    payloads: dict[str, dict[str, Any]] = {}
    for label, cost in COST_TIERS.items():
        if skip_30bp and label == "30bp":
            continue
        p = json.loads(json.dumps(base_payload))
        # 替换 workbench_config 中的 costs
        if isinstance(p.get("workbench_config"), dict):
            p["workbench_config"]["costs"] = cost
        payloads[f"COST_{label}"] = p
    return payloads


# ── Phase 调度 ─────────────────────────────────────────────────

def run_phase_0(client: ExperimentClient, output_dir: Path) -> dict[str, dict[str, Any]]:
    """Phase 0: 基线对照。"""
    logger.info("=" * 60)
    logger.info("Phase 0: 基线对照")
    logger.info("=" * 60)

    results: dict[str, dict[str, Any]] = {}
    for name, builder in [("B0", build_baseline_b0), ("B1", build_baseline_b1)]:
        logger.info("提交 %s ...", name)
        raw = client.run_and_wait(builder())
        metrics = client.extract_metrics(raw)
        results[name] = metrics
        logger.info(
            "%s: CAGR=%.2f%% Sharpe=%.3f MaxDD=%.2f%% Trades=%d",
            name, metrics["cagr"] * 100, metrics["sharpe"],
            metrics["max_drawdown"] * 100, metrics["trades"],
        )

    _save_json(output_dir / "phase0_results.json", results)
    return results


def gate_0(results: dict[str, dict[str, Any]]) -> bool:
    """Gate 0: strength_rank 是否带来足够改善。"""
    b0_cagr = results["B0"]["cagr"] * 100
    b1_cagr = results["B1"]["cagr"] * 100
    improvement = b1_cagr - b0_cagr
    logger.info("Gate 0: B0 CAGR=%.2f%%, B1 CAGR=%.2f%%, 改善=%.2fpp", b0_cagr, b1_cagr, improvement)
    if improvement < GATE0_MIN_IMPROVEMENT_PP:
        logger.warning("Gate 0 FAIL: 改善 %.2fpp < 阈值 %.1fpp", improvement, GATE0_MIN_IMPROVEMENT_PP)
        return False
    logger.info("Gate 0 PASS")
    return True


def run_phase_a(
    client: ExperimentClient,
    variants: dict[str, dict[str, Any]],
    phase_name: str,
    output_dir: Path,
) -> dict[str, dict[str, Any]]:
    """Phase A: 参数矩阵全量回测。"""
    logger.info("=" * 60)
    logger.info("Phase %s-A: %d 个参数变体", phase_name, len(variants))
    logger.info("=" * 60)

    results: dict[str, dict[str, Any]] = {}
    for idx, (name, payload) in enumerate(variants.items(), 1):
        logger.info("[%d/%d] 提交 %s ...", idx, len(variants), name)
        raw = client.run_and_wait(payload)
        metrics = client.extract_metrics(raw)
        results[name] = metrics
        logger.info(
            "  %s: CAGR=%.2f%% Sharpe=%.3f MaxDD=%.2f%% Trades=%d",
            name, metrics["cagr"] * 100, metrics["sharpe"],
            metrics["max_drawdown"] * 100, metrics["trades"],
        )

    _save_json(output_dir / f"phase{phase_name}a_results.json", results)
    return results


def gate_a(results: dict[str, dict[str, Any]], phase_name: str) -> tuple[bool, str]:
    """Phase A 决策门：最佳变体 CAGR > 0%，返回 (pass, best_name)。"""
    best_name = max(results, key=lambda k: results[k]["sharpe"])
    best = results[best_name]
    cagr = best["cagr"]
    trades = best["trades"]
    # 粗略年化交易次数（10 年）
    trades_per_year = trades / 10.0 if trades > 0 else 0

    logger.info(
        "Gate %s: 最佳=%s CAGR=%.2f%% Sharpe=%.3f Trades/yr=%.0f",
        phase_name, best_name, cagr * 100, best["sharpe"], trades_per_year,
    )

    passed = True
    if cagr <= GATE_MIN_CAGR:
        logger.warning("Gate %s FAIL: CAGR %.2f%% <= 0%%", phase_name, cagr * 100)
        passed = False
    if trades_per_year < GATE_MIN_TRADES_PER_YEAR:
        logger.warning("Gate %s WARN: 交易次数 %.0f/yr < %d", phase_name, trades_per_year, GATE_MIN_TRADES_PER_YEAR)
    if trades_per_year > GATE_MAX_TRADES_PER_YEAR:
        logger.warning("Gate %s WARN: 交易次数 %.0f/yr > %d", phase_name, trades_per_year, GATE_MAX_TRADES_PER_YEAR)

    if passed:
        logger.info("Gate %s PASS", phase_name)
    return passed, best_name


def run_phase_bc(
    client: ExperimentClient,
    base_payload: dict[str, Any],
    phase_name: str,
    best_name: str,
    output_dir: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Phase B+C: Walk-Forward + 成本敏感度。"""
    # Phase B: Walk-Forward
    logger.info("=" * 60)
    logger.info("Phase %s-B: Walk-Forward (%s)", phase_name, best_name)
    logger.info("=" * 60)

    wf_payloads = build_wf_payloads(base_payload)
    wf_results: dict[str, dict[str, Any]] = {}
    for idx, (name, payload) in enumerate(wf_payloads.items(), 1):
        logger.info("[%d/%d] 提交 %s ...", idx, len(wf_payloads), name)
        raw = client.run_and_wait(payload)
        metrics = client.extract_metrics(raw)
        wf_results[name] = metrics
        logger.info(
            "  %s: CAGR=%.2f%% Sharpe=%.3f MaxDD=%.2f%%",
            name, metrics["cagr"] * 100, metrics["sharpe"], metrics["max_drawdown"] * 100,
        )

    _save_json(output_dir / f"phase{phase_name}b_wf_results.json", wf_results)

    # Phase C: 成本敏感度
    logger.info("=" * 60)
    logger.info("Phase %s-C: 成本敏感度 (%s)", phase_name, best_name)
    logger.info("=" * 60)

    cost_payloads = build_cost_payloads(base_payload, skip_30bp=True)
    cost_results: dict[str, dict[str, Any]] = {}
    for idx, (name, payload) in enumerate(cost_payloads.items(), 1):
        logger.info("[%d/%d] 提交 %s ...", idx, len(cost_payloads), name)
        raw = client.run_and_wait(payload)
        metrics = client.extract_metrics(raw)
        cost_results[name] = metrics
        logger.info(
            "  %s: CAGR=%.2f%% Sharpe=%.3f",
            name, metrics["cagr"] * 100, metrics["sharpe"],
        )

    _save_json(output_dir / f"phase{phase_name}c_cost_results.json", cost_results)
    return wf_results, cost_results


def run_strategy_phase(
    client: ExperimentClient,
    variants: dict[str, dict[str, Any]],
    phase_name: str,
    output_dir: Path,
) -> dict[str, Any]:
    """完整执行一个策略的 Phase A → Gate → Phase B+C。"""
    # Phase A
    a_results = run_phase_a(client, variants, phase_name, output_dir)

    # Gate
    passed, best_name = gate_a(a_results, phase_name)
    if not passed:
        logger.warning("策略 Phase %s 未通过 Gate，跳过 WF + 成本测试", phase_name)
        return {
            "phase_a": a_results,
            "gate_passed": False,
            "best_variant": best_name,
        }

    # Phase B + C
    best_payload = variants[best_name]
    wf_results, cost_results = run_phase_bc(client, best_payload, phase_name, best_name, output_dir)

    return {
        "phase_a": a_results,
        "gate_passed": True,
        "best_variant": best_name,
        "phase_b_wf": wf_results,
        "phase_c_cost": cost_results,
    }


# ── 后处理 ─────────────────────────────────────────────────────

def compute_wf_summary(wf_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """从 10 次 WF 结果计算汇总指标。"""
    cagrs = [m["cagr"] for m in wf_results.values()]
    sharpes = [m["sharpe"] for m in wf_results.values()]
    maxdds = [m["max_drawdown"] for m in wf_results.values()]

    positive_years = sum(1 for c in cagrs if c > 0)
    sorted_cagrs = sorted(cagrs)
    median_cagr = sorted_cagrs[len(sorted_cagrs) // 2] if sorted_cagrs else 0

    return {
        "years": list(wf_results.keys()),
        "cagrs": cagrs,
        "sharpes": sharpes,
        "max_drawdowns": maxdds,
        "positive_years": positive_years,
        "total_years": len(cagrs),
        "median_cagr": median_cagr,
        "mean_cagr": sum(cagrs) / len(cagrs) if cagrs else 0,
        "mean_sharpe": sum(sharpes) / len(sharpes) if sharpes else 0,
        "worst_year_cagr": min(cagrs) if cagrs else 0,
        "best_year_cagr": max(cagrs) if cagrs else 0,
    }


def compute_param_stability(a_results: dict[str, dict[str, Any]], best_name: str) -> dict[str, Any]:
    """检查邻近参数变体的 Sharpe 差异是否在 ±0.15 以内。"""
    best_sharpe = a_results[best_name]["sharpe"]
    neighbors: dict[str, dict[str, Any]] = {}
    all_stable = True
    for name, metrics in a_results.items():
        diff = metrics["sharpe"] - best_sharpe
        stable = abs(diff) <= 0.15
        if not stable:
            all_stable = False
        neighbors[name] = {
            "sharpe": metrics["sharpe"],
            "diff_from_best": diff,
            "stable": stable,
        }
    return {
        "best_variant": best_name,
        "best_sharpe": best_sharpe,
        "neighbors": neighbors,
        "all_stable": all_stable,
    }


def compute_segment_analysis(wf_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """牛熊分段分析：将 WF 年度结果归类到 Bull/Bear/Sideways 段。

    基于 CSI800 EMA(200) 的近似分段定义（见 experiments_plan.md）:
      Bull:     2015, 2017, 2019, 2020, 2024
      Bear:     2016, 2018, 2021, 2022
      Sideways: 2023
    """
    # 年份 → 市场状态映射（基于 experiments_plan.md 的分段定义）
    year_regime = {
        "2015": "bull",    # 2015-01~06 bull + 06~12 bear → 按主导方向归为 bull（含暴涨期）
        "2016": "bear",    # 2016-02 底部后缓慢恢复
        "2017": "bull",    # 2017 年恢复行情
        "2018": "bear",    # 贸易战
        "2019": "bull",    # 恢复 + COVID 反弹开始
        "2020": "bull",    # COVID 反弹
        "2021": "bear",    # 监管 + 封控
        "2022": "bear",    # 持续下跌
        "2023": "sideways",  # 横盘
        "2024": "bull",    # Q4 反弹
    }

    segments: dict[str, list[float]] = {"bull": [], "bear": [], "sideways": []}
    for wf_name, metrics in wf_results.items():
        # wf_name 格式: WF_2015, WF_2016, ...
        year = wf_name.replace("WF_", "")
        regime = year_regime.get(year, "sideways")
        segments[regime].append(metrics["cagr"])

    summary: dict[str, Any] = {}
    for regime, cagrs in segments.items():
        if cagrs:
            summary[regime] = {
                "years": len(cagrs),
                "mean_cagr": sum(cagrs) / len(cagrs),
                "cagrs": cagrs,
            }
        else:
            summary[regime] = {"years": 0, "mean_cagr": 0, "cagrs": []}

    # Bear 段 CAGR 硬性检查: >= -5%
    bear_mean = summary.get("bear", {}).get("mean_cagr", 0)
    summary["bear_pass"] = bear_mean >= -0.05

    return summary


def compute_cost_sensitivity(
    a_results_30bp: dict[str, Any],
    cost_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """成本敏感度曲线：验证 5bp > 15bp > 30bp > 50bp 单调性。"""
    curve: dict[str, float] = {"30bp": a_results_30bp["cagr"]}
    for label, metrics in cost_results.items():
        # label 格式: COST_5bp, COST_15bp, COST_50bp
        tier = label.replace("COST_", "")
        curve[tier] = metrics["cagr"]

    # 排序检查单调性
    ordered_labels = ["5bp", "15bp", "30bp", "50bp"]
    ordered_cagrs = [curve.get(l, float("nan")) for l in ordered_labels]
    monotonic = all(
        ordered_cagrs[i] >= ordered_cagrs[i + 1]
        for i in range(len(ordered_cagrs) - 1)
        if not (ordered_cagrs[i] != ordered_cagrs[i] or ordered_cagrs[i + 1] != ordered_cagrs[i + 1])  # NaN 检查
    )

    return {
        "curve": curve,
        "ordered_labels": ordered_labels,
        "ordered_cagrs": ordered_cagrs,
        "monotonic": monotonic,
    }


# ── 报告生成 ──────────────────────────────────────────────────

def generate_final_report(all_results: dict[str, Any], output_dir: Path) -> None:
    """生成 final_report.md。"""
    lines: list[str] = []
    lines.append("# Alpha Strategy v1 — 最终研究报告\n")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Phase 0 基线
    p0 = all_results.get("phase0", {})
    if p0:
        lines.append("## Phase 0: 基线对照\n")
        lines.append("| 实验 | CAGR | Sharpe | MaxDD | Trades |")
        lines.append("|------|------|--------|-------|--------|")
        for name in ["B0", "B1"]:
            m = p0.get(name, {})
            lines.append(
                f"| {name} | {m.get('cagr', 0) * 100:.2f}% | {m.get('sharpe', 0):.3f} | "
                f"{m.get('max_drawdown', 0) * 100:.2f}% | {m.get('trades', 0)} |"
            )
        b0c = p0.get("B0", {}).get("cagr", 0) * 100
        b1c = p0.get("B1", {}).get("cagr", 0) * 100
        lines.append(f"\nstrength_rank 改善: {b1c - b0c:.2f}pp\n")

    # 各策略 Phase A 结果
    for phase_key, label in [("phase1", "S1_MOMO"), ("phase2", "S2_REGIME"), ("phase3", "S3_LOWTURN")]:
        phase = all_results.get(phase_key, {})
        if not phase:
            continue
        lines.append(f"## {label}\n")
        a_results = phase.get("phase_a", {})
        best = phase.get("best_variant", "")
        gate = phase.get("gate_passed", False)

        lines.append("### Phase A: 参数矩阵\n")
        lines.append("| 变体 | CAGR | Sharpe | MaxDD | Trades | Best? |")
        lines.append("|------|------|--------|-------|--------|-------|")
        for name, m in a_results.items():
            marker = " **<--**" if name == best else ""
            lines.append(
                f"| {name} | {m['cagr'] * 100:.2f}% | {m['sharpe']:.3f} | "
                f"{m['max_drawdown'] * 100:.2f}% | {m['trades']} |{marker} |"
            )

        lines.append(f"\nGate: {'PASS' if gate else 'FAIL'}\n")

        # WF 汇总
        wf = phase.get("wf_summary")
        if wf:
            lines.append("### Walk-Forward 汇总\n")
            lines.append(f"- 正收益年数: {wf['positive_years']}/{wf['total_years']}")
            lines.append(f"- 中位 CAGR: {wf['median_cagr'] * 100:.2f}%")
            lines.append(f"- 平均 Sharpe: {wf['mean_sharpe']:.3f}")
            lines.append(f"- 最差年: {wf['worst_year_cagr'] * 100:.2f}%")
            lines.append(f"- 最好年: {wf['best_year_cagr'] * 100:.2f}%\n")

        # 成本敏感度
        cost = phase.get("cost_sensitivity")
        if cost:
            lines.append("### 成本敏感度\n")
            lines.append("| 成本档 | CAGR |")
            lines.append("|--------|------|")
            for label_cost, cagr_val in zip(cost["ordered_labels"], cost["ordered_cagrs"]):
                lines.append(f"| {label_cost} | {cagr_val * 100:.2f}% |")
            lines.append(f"\n单调性: {'PASS' if cost['monotonic'] else 'FAIL'}\n")

        # 牛熊分段
        seg = phase.get("segment_analysis")
        if seg:
            lines.append("### 牛熊分段分析\n")
            lines.append("| 段 | 年数 | 平均 CAGR |")
            lines.append("|---|------|-----------|")
            for regime in ["bull", "bear", "sideways"]:
                s = seg.get(regime, {})
                lines.append(f"| {regime} | {s.get('years', 0)} | {s.get('mean_cagr', 0) * 100:.2f}% |")
            lines.append(f"\nBear 段检查 (>= -5%): {'PASS' if seg.get('bear_pass', False) else 'FAIL'}\n")

        # 参数稳定性
        stability = phase.get("param_stability")
        if stability:
            lines.append("### 参数稳定性\n")
            lines.append(f"- 全部稳定 (Sharpe ±0.15): {'YES' if stability['all_stable'] else 'NO'}\n")

    # Pass/Fail 检查清单
    lines.append("## Pass/Fail 检查清单\n")
    lines.append("| 检查项 | 阈值 | 结果 | 状态 |")
    lines.append("|--------|------|------|------|")
    lines.append("*(手动填写或由脚本二次运行时自动判断)*\n")

    report_path = output_dir / "final_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("最终报告已写入: %s", report_path)


# ── 工具 ──────────────────────────────────────────────────────

def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info("已保存: %s", path)


# ── 主入口 ────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Alpha Strategy v1 自动化实验脚本")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API 服务地址")
    parser.add_argument("--phase", default="all", help="运行阶段: 0, 1, 2, 3, all")
    parser.add_argument("--output-dir", default=None, help="输出目录 (默认: outputs/alpha_v1_<timestamp>)")
    parser.add_argument("--poll-interval", type=int, default=30, help="轮询间隔秒数")
    parser.add_argument("--timeout", type=int, default=1200, help="单任务超时秒数")
    parser.add_argument("--skip-gates", action="store_true", help="跳过决策门（强制继续所有 Phase）")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    output_dir = Path(args.output_dir) if args.output_dir else Path(
        f"outputs/alpha_v1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("输出目录: %s", output_dir)

    client = ExperimentClient(args.base_url, args.poll_interval, args.timeout)
    phases = args.phase.lower()
    all_results: dict[str, Any] = {}

    # Phase 0
    if phases in ("0", "all"):
        p0 = run_phase_0(client, output_dir)
        all_results["phase0"] = p0
        if not args.skip_gates:
            if not gate_0(p0):
                logger.warning("Gate 0 未通过。继续运行但请注意 strength_rank 效果不足。")

    # Phase 1: S1_MOMO
    if phases in ("1", "all"):
        s1_variants = build_s1_variants()
        result = run_strategy_phase(client, s1_variants, "1", output_dir)
        if result.get("gate_passed") and result.get("phase_b_wf"):
            result["wf_summary"] = compute_wf_summary(result["phase_b_wf"])
            result["segment_analysis"] = compute_segment_analysis(result["phase_b_wf"])
            result["param_stability"] = compute_param_stability(result["phase_a"], result["best_variant"])
            if result.get("phase_c_cost"):
                result["cost_sensitivity"] = compute_cost_sensitivity(
                    result["phase_a"][result["best_variant"]], result["phase_c_cost"],
                )
        all_results["phase1"] = result

    # Phase 2: S2_REGIME
    if phases in ("2", "all"):
        s2_variants = build_s2_variants()
        result = run_strategy_phase(client, s2_variants, "2", output_dir)
        if result.get("gate_passed") and result.get("phase_b_wf"):
            result["wf_summary"] = compute_wf_summary(result["phase_b_wf"])
            result["segment_analysis"] = compute_segment_analysis(result["phase_b_wf"])
            result["param_stability"] = compute_param_stability(result["phase_a"], result["best_variant"])
            if result.get("phase_c_cost"):
                result["cost_sensitivity"] = compute_cost_sensitivity(
                    result["phase_a"][result["best_variant"]], result["phase_c_cost"],
                )
        all_results["phase2"] = result

    # Phase 3: S3_LOWTURN
    if phases in ("3", "all"):
        s3_variants = build_s3_variants()
        result = run_strategy_phase(client, s3_variants, "3", output_dir)
        if result.get("gate_passed") and result.get("phase_b_wf"):
            result["wf_summary"] = compute_wf_summary(result["phase_b_wf"])
            result["segment_analysis"] = compute_segment_analysis(result["phase_b_wf"])
            result["param_stability"] = compute_param_stability(result["phase_a"], result["best_variant"])
            if result.get("phase_c_cost"):
                result["cost_sensitivity"] = compute_cost_sensitivity(
                    result["phase_a"][result["best_variant"]], result["phase_c_cost"],
                )
        all_results["phase3"] = result

    # 保存全量结果 + 生成报告
    _save_json(output_dir / "all_results.json", all_results)
    generate_final_report(all_results, output_dir)

    logger.info("=" * 60)
    logger.info("Alpha Strategy v1 实验全部完成")
    logger.info("输出目录: %s", output_dir)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

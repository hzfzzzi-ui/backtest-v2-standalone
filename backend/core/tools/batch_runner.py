"""批量参数扫描运行器。

遍历指定目录下的 JSON 配置文件，依次调用 run_experiment() 执行回测。
每个实验独立 try/except，失败不阻断后续。
"""
from __future__ import annotations

import fnmatch
import json
import logging
import time
from pathlib import Path
from typing import Any

from backend.core.tools.experiment_runner import run_experiment

logger = logging.getLogger(__name__)


def run_sweep(
    config_dir: str,
    pattern: str = "*.json",
) -> list[dict[str, Any]]:
    """批量执行配置目录下匹配 pattern 的所有 JSON 配置。

    每个 JSON 配置可包含 ``_sweep`` 字段，其内容会作为 overrides 传给
    ``run_experiment()``（universe_mode, universe_limit, max_positions 等）。

    返回每个实验的结果摘要列表。
    """
    cfg_path = Path(config_dir).resolve()
    if not cfg_path.is_dir():
        raise FileNotFoundError(f"配置目录不存在: {cfg_path}")

    configs = sorted(
        p for p in cfg_path.iterdir()
        if p.suffix == ".json" and fnmatch.fnmatch(p.name, pattern)
    )

    if not configs:
        logger.warning("未找到匹配 '%s' 的配置文件: %s", pattern, cfg_path)
        return []

    total = len(configs)
    results: list[dict[str, Any]] = []
    logger.info("=" * 60)
    logger.info("参数扫描开始: %d 个配置, pattern=%s", total, pattern)
    logger.info("=" * 60)

    for idx, cfg_file in enumerate(configs, 1):
        name = cfg_file.stem
        logger.info("[%d/%d] %s ...", idx, total, name)
        t0 = time.perf_counter()

        try:
            # 读取 _sweep 字段作为 overrides
            raw = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
            overrides = dict(raw.get("_sweep", {}))
            overrides["source_config"] = cfg_file.name

            result = run_experiment(
                base_cfg_path=str(cfg_file),
                preset="single",
                overrides=overrides,
            )
            elapsed = time.perf_counter() - t0
            result["config_name"] = name
            result["elapsed_s"] = round(elapsed, 1)
            results.append(result)
            logger.info(
                "[%d/%d] %s ... done (%.1fs) sharpe=%.3f ret=%.2f%%",
                idx, total, name, elapsed,
                float(result.get("sharpe", 0)),
                float(result.get("total_return", 0)) * 100,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.error("[%d/%d] %s ... FAILED (%.1fs): %s", idx, total, name, elapsed, exc)
            results.append({
                "config_name": name,
                "status": "FAILED",
                "error": str(exc),
                "elapsed_s": round(elapsed, 1),
            })

    # 汇总
    ok = sum(1 for r in results if r.get("status") == "OK")
    fail = total - ok
    logger.info("=" * 60)
    logger.info("参数扫描完成: %d 成功, %d 失败, 共 %d 个", ok, fail, total)
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    parser = argparse.ArgumentParser(description="批量参数扫描运行器")
    parser.add_argument("config_dir", help="配置文件目录路径")
    parser.add_argument("--pattern", default="*.json", help="文件名匹配模式 (default: *.json)")
    args = parser.parse_args()

    results = run_sweep(args.config_dir, pattern=args.pattern)

    # 打印简要结果表
    print(f"\n{'Config':<35} {'Status':<8} {'Return':>8} {'Sharpe':>8} {'MaxDD':>8} {'Time':>6}")
    print("-" * 80)
    for r in results:
        if r.get("status") == "OK":
            print(
                f"{r['config_name']:<35} {'OK':<8} "
                f"{r.get('total_return', 0) * 100:>7.2f}% "
                f"{r.get('sharpe', 0):>8.3f} "
                f"{r.get('max_drawdown', 0) * 100:>7.2f}% "
                f"{r.get('elapsed_s', 0):>5.0f}s"
            )
        else:
            print(f"{r['config_name']:<35} {'FAILED':<8} {r.get('error', '')[:40]}")

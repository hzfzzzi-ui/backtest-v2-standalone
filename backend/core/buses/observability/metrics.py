"""
Metrics Collection for Backtest Observability.

Collects counters, gauges, and histograms during backtest execution.
"""

from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Collect backtest metrics for observability."""

    def __init__(self):
        self.counters: dict[str, int] = defaultdict(int)
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = defaultdict(list)

    def increment(self, metric: str, value: int = 1) -> None:
        """Increment counter."""
        self.counters[metric] += value

    def set_gauge(self, metric: str, value: float) -> None:
        """Set gauge value."""
        self.gauges[metric] = value

    def record(self, metric: str, value: float) -> None:
        """Record histogram value."""
        self.histograms[metric].append(value)

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary."""
        summary: dict[str, Any] = {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {},
        }

        # Calculate histogram statistics
        for metric, values in self.histograms.items():
            if values:
                sorted_values = sorted(values)
                n = len(sorted_values)
                summary["histograms"][metric] = {
                    "count": n,
                    "min": sorted_values[0],
                    "max": sorted_values[-1],
                    "mean": sum(values) / n,
                    "p50": sorted_values[n // 2],
                    "p95": sorted_values[int(n * 0.95)] if n > 20 else sorted_values[-1],
                    "p99": sorted_values[int(n * 0.99)] if n > 100 else sorted_values[-1],
                }

        return summary

    def reset(self) -> None:
        """Reset all metrics."""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()


# Standard metrics to collect:
"""
Counters:
- signals.generated
- signals.blocked.{reason_code}
- orders.submitted
- orders.filled
- orders.rejected.{reason_code}
- orders.skipped.{reason_code}
- trades.executed
- overlay.blocks.{reason_code}

Gauges:
- portfolio.equity
- portfolio.cash
- portfolio.num_positions
- portfolio.drawdown_pct
- overlay.dd_state
- overlay.regime

Histograms:
- trade.pnl
- trade.duration_days
- order.fill_latency_ms
- feature.compute_time_ms
- cache.hit_rate
"""

"""
Structured Logger for Backtest Observability.

Writes JSON Lines format for easy parsing and analysis.
"""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


class StructuredLogger:
    """Structured logger for backtest events."""

    def __init__(self, run_id: str, log_path: str | Path):
        self.run_id = run_id
        self.log_path = Path(log_path)

        # Ensure directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup JSON logger
        self.logger = logging.getLogger(f"backtest.{run_id}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # JSON handler
        handler = logging.FileHandler(str(self.log_path), encoding="utf-8")
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)

    def log_signal(
        self,
        day: date,
        symbol: str,
        side: str,
        reason_code: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log signal event."""
        self.logger.info("signal", extra={
            "event_type": "signal",
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "day": day.isoformat(),
            "symbol": symbol,
            "side": side,
            "reason_code": reason_code,
            "metadata": metadata or {},
        })

    def log_order(
        self,
        day: date,
        order_id: int,
        symbol: str,
        side: str,
        qty: int,
        status: str,
        reason_code: str,
    ) -> None:
        """Log order event."""
        self.logger.info("order", extra={
            "event_type": "order",
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "day": day.isoformat(),
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "status": status,
            "reason_code": reason_code,
        })

    def log_trade(
        self,
        day: date,
        trade_id: int,
        symbol: str,
        side: str,
        qty: int,
        price: float,
        net_amount: float,
    ) -> None:
        """Log trade execution."""
        self.logger.info("trade", extra={
            "event_type": "trade",
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "day": day.isoformat(),
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "net_amount": net_amount,
        })

    def log_overlay_event(
        self,
        day: date,
        event_type: str,
        reason_code: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log overlay gate event (regime change, DD tier change, etc.)."""
        self.logger.info("overlay", extra={
            "event_type": "overlay",
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "day": day.isoformat(),
            "overlay_event": event_type,
            "reason_code": reason_code,
            "metadata": metadata or {},
        })

    def log_risk_event(
        self,
        day: date,
        event_type: str,
        reason_code: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log risk event (position sizing, stop checks, etc.)."""
        self.logger.info("risk", extra={
            "event_type": "risk",
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "day": day.isoformat(),
            "risk_event": event_type,
            "reason_code": reason_code,
            "metadata": metadata or {},
        })

    def close(self) -> None:
        """Close logger and handlers."""
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Add extra fields (skip standard logging attributes)
        skip_keys = {
            "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "lineno", "funcName", "created",
            "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "exc_info", "exc_text", "stack_info",
        }

        for key, value in record.__dict__.items():
            if key not in skip_keys:
                log_dict[key] = value

        return json.dumps(log_dict, ensure_ascii=False)

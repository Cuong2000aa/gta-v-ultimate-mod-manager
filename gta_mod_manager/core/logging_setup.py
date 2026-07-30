"""Logging configuration and the in-memory buffer used by the log viewer."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from gta_mod_manager.core import constants
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.events import EventBus, LogEvent

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-38s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True, slots=True)
class LogRecordView:
    """A log record reduced to what the UI needs to render a row."""

    timestamp: datetime
    level: str
    logger: str
    message: str


class RingBufferHandler(logging.Handler):
    """Keeps the most recent records in memory for the in-app log viewer."""

    def __init__(self, capacity: int = constants.LOG_RING_CAPACITY) -> None:
        super().__init__()
        self._records: deque[LogRecordView] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        """Store ``record`` in the ring buffer."""
        self._records.append(
            LogRecordView(
                timestamp=datetime.fromtimestamp(record.created),
                level=record.levelname,
                logger=record.name,
                message=record.getMessage(),
            )
        )

    def records(self) -> tuple[LogRecordView, ...]:
        """Return a snapshot of the buffered records, oldest first."""
        return tuple(self._records)

    def clear(self) -> None:
        """Drop every buffered record."""
        self._records.clear()


class EventBusHandler(logging.Handler):
    """Mirrors log records onto the application event bus."""

    def __init__(self, bus: EventBus, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._bus = bus

    def emit(self, record: logging.LogRecord) -> None:
        """Publish ``record`` as a :class:`LogEvent`."""
        self._bus.publish(
            LogEvent(level=record.levelname, logger=record.name, message=record.getMessage())
        )


@dataclass(frozen=True, slots=True)
class LoggingHandles:
    """References to the handlers created by :func:`configure_logging`."""

    ring_buffer: RingBufferHandler
    file_handler: logging.Handler


def configure_logging(
    paths: AppPaths,
    *,
    bus: EventBus | None = None,
    level: int = logging.INFO,
    console: bool = True,
) -> LoggingHandles:
    """Install the application's logging handlers on the root logger.

    Args:
        paths: Resolved application paths; the log directory is created.
        bus: Optional event bus that receives mirrored log records.
        level: Minimum level captured by the root logger.
        console: Whether to also write to standard error.

    Returns:
        Handles to the created handlers so callers (and tests) can inspect
        or remove them.
    """
    paths.logs.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)
    _remove_managed_handlers(root)

    file_handler = logging.handlers.RotatingFileHandler(
        paths.log_file,
        maxBytes=constants.LOG_MAX_BYTES,
        backupCount=constants.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.set_name("gmm.file")
    root.addHandler(file_handler)

    ring = RingBufferHandler()
    ring.setFormatter(formatter)
    ring.set_name("gmm.ring")
    root.addHandler(ring)

    # Under pythonw.exe there is no console and sys.stderr is None; attaching
    # a StreamHandler there would raise on the very first log record.
    if console and sys.stderr is not None:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        stream.set_name("gmm.console")
        root.addHandler(stream)

    if bus is not None:
        bus_handler = EventBusHandler(bus)
        bus_handler.set_name("gmm.bus")
        root.addHandler(bus_handler)

    return LoggingHandles(ring_buffer=ring, file_handler=file_handler)


def _remove_managed_handlers(root: logging.Logger) -> None:
    """Detach handlers previously installed by this module."""
    managed: Iterable[logging.Handler] = [
        handler for handler in root.handlers if (handler.name or "").startswith("gmm.")
    ]
    for handler in managed:
        root.removeHandler(handler)
        handler.close()


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced application logger."""
    return logging.getLogger(f"{constants.APP_SLUG}.{name}")

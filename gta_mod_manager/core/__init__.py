"""Shared kernel: constants, errors, ports and cross-cutting infrastructure."""

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.container import Container
from gta_mod_manager.core.events import (
    EventBus,
    NotificationEvent,
    NotificationLevel,
    ProgressEvent,
    new_operation_id,
)
from gta_mod_manager.core.result import Result

__all__ = [
    "AppPaths",
    "Container",
    "EventBus",
    "NotificationEvent",
    "NotificationLevel",
    "ProgressEvent",
    "Result",
    "new_operation_id",
]

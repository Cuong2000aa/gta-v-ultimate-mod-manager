"""Tests for the event bus and the progress reporters."""

from __future__ import annotations

from gta_mod_manager.core.events import (
    EventBus,
    NotificationEvent,
    NotificationLevel,
    ProgressEvent,
    new_operation_id,
)
from gta_mod_manager.core.progress import EventBusProgressReporter, NullProgressReporter


def test_handlers_only_receive_their_own_event_type() -> None:
    bus = EventBus()
    progress: list[ProgressEvent] = []
    notifications: list[NotificationEvent] = []
    bus.subscribe(ProgressEvent, progress.append)
    bus.subscribe(NotificationEvent, notifications.append)

    bus.publish(ProgressEvent(operation_id="op", label="Extracting", current=1, total=4))

    assert len(progress) == 1
    assert not notifications


def test_unsubscribing_stops_delivery() -> None:
    bus = EventBus()
    seen: list[NotificationEvent] = []
    unsubscribe = bus.subscribe(NotificationEvent, seen.append)

    bus.publish(NotificationEvent(title="first", message=""))
    unsubscribe()
    bus.publish(NotificationEvent(title="second", message=""))

    assert [event.title for event in seen] == ["first"]


def test_a_broken_subscriber_cannot_abort_the_publisher() -> None:
    bus = EventBus()
    delivered: list[str] = []

    def broken(_event: NotificationEvent) -> None:
        raise RuntimeError("subscriber is broken")

    bus.subscribe(NotificationEvent, broken)
    bus.subscribe(NotificationEvent, lambda event: delivered.append(event.title))

    bus.publish(NotificationEvent(title="still delivered", message=""))

    assert delivered == ["still delivered"]


def test_progress_percent_is_clamped() -> None:
    assert ProgressEvent(operation_id="op", label="", current=5, total=0).percent == 0
    assert ProgressEvent(operation_id="op", label="", current=9, total=4).percent == 100
    assert ProgressEvent(operation_id="op", label="", current=1, total=4).percent == 25


def test_event_bus_reporter_publishes_the_whole_operation() -> None:
    bus = EventBus()
    progress: list[ProgressEvent] = []
    bus.subscribe(ProgressEvent, progress.append)

    reporter = EventBusProgressReporter(bus)
    operation = new_operation_id()
    reporter.start(operation, "Installing", total=2)
    reporter.advance(operation, 1, "Copying")
    reporter.finish(operation, "Done")

    assert [event.label for event in progress] == ["Installing", "Copying", "Done"]
    assert progress[-1].percent == 100


def test_the_null_reporter_accepts_every_call() -> None:
    reporter = NullProgressReporter()
    reporter.start("op", "label", total=1)
    reporter.advance("op", 1, "label")
    reporter.finish("op", "label")


def test_notification_levels_round_trip_through_their_value() -> None:
    event = NotificationEvent(
        title="Installed", message="2 files", level=NotificationLevel.SUCCESS
    )

    assert NotificationLevel(event.level.value) is NotificationLevel.SUCCESS

"""Tests for the Result type used at every service boundary."""

from __future__ import annotations

import pytest

from gta_mod_manager.core.result import Result


def test_ok_carries_the_value() -> None:
    result = Result.ok(42)

    assert result.is_ok
    assert not result.is_error
    assert result.unwrap() == 42


def test_fail_carries_the_message_and_code() -> None:
    result: Result[int] = Result.fail("boom", code="test.boom")

    assert result.is_error
    assert result.error == "boom"
    assert result.code == "test.boom"


def test_unwrapping_a_failure_raises() -> None:
    result: Result[int] = Result.fail("boom")

    with pytest.raises(ValueError, match="boom"):
        result.unwrap()


def test_unwrap_or_returns_the_fallback() -> None:
    assert Result.fail("boom").unwrap_or(7) == 7
    assert Result.ok(1).unwrap_or(7) == 1


def test_map_only_applies_to_successes() -> None:
    assert Result.ok(2).map(lambda value: value * 3).unwrap() == 6

    failed: Result[int] = Result.fail("boom")
    assert failed.map(lambda value: value * 3).error == "boom"


def test_warnings_are_preserved_and_appendable() -> None:
    result = Result.ok("value").with_warning("careful")

    assert result.is_ok
    assert result.warnings == ("careful",)

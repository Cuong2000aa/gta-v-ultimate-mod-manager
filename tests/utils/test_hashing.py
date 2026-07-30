"""Tests for the content hashing helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gta_mod_manager.utils import hashing


def test_file_hash_matches_the_reference_implementation(tmp_path: Path) -> None:
    target = tmp_path / "dlc.rpf"
    payload = b"binary payload" * 1000
    target.write_bytes(payload)

    assert hashing.sha256_file(target) == hashlib.sha256(payload).hexdigest()


def test_short_id_is_stable_and_bounded() -> None:
    first = hashing.short_id("Adder2 Addon.zip")
    second = hashing.short_id("Adder2 Addon.zip")

    assert first == second
    assert len(first) == 12
    assert first != hashing.short_id("Adder3 Addon.zip")


def test_files_are_identical_compares_content(tmp_path: Path) -> None:
    left = tmp_path / "left.bin"
    right = tmp_path / "right.bin"
    other = tmp_path / "other.bin"
    left.write_bytes(b"same")
    right.write_bytes(b"same")
    other.write_bytes(b"different")

    assert hashing.files_are_identical(left, right)
    assert not hashing.files_are_identical(left, other)
    assert not hashing.files_are_identical(left, tmp_path / "missing.bin")

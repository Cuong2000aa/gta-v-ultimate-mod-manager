"""Tests for the glob helpers behind the root-installation whitelist."""

from __future__ import annotations

from pathlib import PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.utils import patterns


def test_allowed_root_patterns_match_the_expected_files() -> None:
    allowed = constants.ALLOWED_ROOT_FILE_PATTERNS

    assert patterns.matches_any("ScriptHookV.dll", allowed)
    assert patterns.matches_any("OpenIV.asi", allowed)
    assert patterns.matches_any("trainerv.asi", allowed)
    assert not patterns.matches_any("common.rpf", allowed)
    assert not patterns.matches_any("GTA5.exe", allowed)


def test_first_match_returns_the_winning_pattern() -> None:
    assert patterns.first_match("mod.asi", ("*.dll", "*.asi")) == "*.asi"
    assert patterns.first_match("mod.rpf", ("*.dll", "*.asi")) is None


def test_path_contains_directory_ignores_the_file_name() -> None:
    relative = PurePosixPath("MyMod/scripts/Cool.dll")

    assert patterns.path_contains_directory(relative, ("scripts",))
    assert not patterns.path_contains_directory(relative, ("Cool.dll",))


def test_top_directory_is_none_for_loose_files() -> None:
    assert patterns.top_directory(PurePosixPath("MyMod/file.dll")) == "MyMod"
    assert patterns.top_directory(PurePosixPath("file.dll")) is None


def test_strip_leading_directories_unwraps_nested_folders() -> None:
    stripped = patterns.strip_leading_directories(
        PurePosixPath("MyMod v1.2/MyMod v1.2/mods/update/update.rpf"),
        ("MyMod v1.2",),
    )

    assert stripped == PurePosixPath("mods/update/update.rpf")

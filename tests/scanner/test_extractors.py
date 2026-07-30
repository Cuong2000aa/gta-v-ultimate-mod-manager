"""Tests for the archive extractors, focused on the RAR backends.

RAR needs an external tool, so the tests drive the command-line path with a
Python interpreter standing in for UnRAR: it exercises the staging, the move
into the workspace and the failure handling without requiring WinRAR.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gta_mod_manager.core import constants
from gta_mod_manager.core.exceptions import DependencyMissingError
from gta_mod_manager.scanner.extractors import RarExtractor

_WRITE_TWO_FILES = (
    "import pathlib, sys;"
    "root = pathlib.Path(sys.argv[1]);"
    "(root / 'pack').mkdir(parents=True, exist_ok=True);"
    "(root / 'pack' / 'dlc.rpf').write_text('payload');"
    "(root / 'ReadMe.txt').write_text('notes')"
)


def _fake_archive(tmp_path: Path) -> Path:
    """Return a path that looks like a RAR but holds no archive."""
    archive = tmp_path / "mod.rar"
    archive.write_bytes(b"not really a rar")
    return archive


def test_a_configured_executable_wins_over_a_detected_one(tmp_path: Path) -> None:
    configured = tmp_path / "UnRAR.exe"
    configured.write_bytes(b"")

    assert RarExtractor(unrar_path=configured)._resolve_unrar() == configured


def test_a_configured_path_that_no_longer_exists_is_ignored(tmp_path: Path) -> None:
    extractor = RarExtractor(unrar_path=tmp_path / "gone.exe")

    resolved = extractor._resolve_unrar()

    assert resolved is None or resolved.is_file()


def test_the_command_line_output_lands_in_the_workspace(tmp_path: Path) -> None:
    destination = tmp_path / "workspace"
    extractor = RarExtractor()

    extracted = extractor._extract_with_cli(
        Path(sys.executable),
        lambda staging: [sys.executable, "-c", _WRITE_TWO_FILES, str(staging)],
        _fake_archive(tmp_path),
        destination,
    )

    assert extracted
    assert (destination / "pack" / "dlc.rpf").read_text() == "payload"
    assert (destination / "ReadMe.txt").read_text() == "notes"
    assert not (destination / constants.CLI_EXTRACTION_STAGING_DIR).exists()


def test_a_failing_archiver_reports_failure_and_cleans_up(tmp_path: Path) -> None:
    destination = tmp_path / "workspace"
    extractor = RarExtractor()

    extracted = extractor._extract_with_cli(
        Path(sys.executable),
        lambda _staging: [sys.executable, "-c", "raise SystemExit(1)"],
        _fake_archive(tmp_path),
        destination,
    )

    assert not extracted
    assert not (destination / constants.CLI_EXTRACTION_STAGING_DIR).exists()


def test_an_unreadable_executable_does_not_raise(tmp_path: Path) -> None:
    extractor = RarExtractor()

    extracted = extractor._extract_with_cli(
        tmp_path / "missing.exe",
        lambda _staging: [str(tmp_path / "missing.exe"), "x"],
        _fake_archive(tmp_path),
        tmp_path / "workspace",
    )

    assert not extracted


def test_without_any_archiver_the_error_says_what_to_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(RarExtractor, "_resolve_unrar", lambda _self: None)
    monkeypatch.setattr(RarExtractor, "_resolve_seven_zip", lambda _self: None)

    with pytest.raises(DependencyMissingError) as error:
        RarExtractor().extract(_fake_archive(tmp_path), tmp_path / "workspace")

    assert "WinRAR" in str(error.value)
    assert "7-Zip" in str(error.value)

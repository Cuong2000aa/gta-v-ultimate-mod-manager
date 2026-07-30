"""Tests for installation detection and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gta_mod_manager.core.exceptions import InvalidGameInstallationError
from gta_mod_manager.detector.game_detector import GameDetector
from gta_mod_manager.detector.sources.base import DetectionSource
from gta_mod_manager.models.enums import GamePlatform


class FakeSource(DetectionSource):
    """Detection source returning a fixed list of folders."""

    def __init__(
        self,
        candidates: tuple[Path, ...],
        name: str = "fake",
        platform: GamePlatform = GamePlatform.STEAM,
    ) -> None:
        self._candidates = candidates
        self.source_name = name
        self.platform = platform

    def candidate_paths(self) -> tuple[Path, ...]:
        """Return the configured candidates."""
        return self._candidates


class BrokenSource(DetectionSource):
    """Detection source that raises, to prove failures are contained."""

    source_name = "broken"

    def candidate_paths(self) -> tuple[Path, ...]:
        """Always fail."""
        raise OSError("registry unavailable")


def test_a_valid_folder_is_detected(game_root: Path) -> None:
    detector = GameDetector((FakeSource((game_root,)),))

    installs = detector.detect_all()

    assert len(installs) == 1
    assert installs[0].root_path == game_root.resolve()
    assert installs[0].detected_by == "fake"
    assert installs[0].platform is GamePlatform.STEAM


def test_invalid_candidates_are_dropped(game_root: Path, tmp_path: Path) -> None:
    empty = tmp_path / "not-a-game"
    empty.mkdir()
    detector = GameDetector((FakeSource((empty, game_root, tmp_path / "missing")),))

    assert [item.root_path for item in detector.detect_all()] == [game_root.resolve()]


def test_duplicates_reported_by_several_sources_are_merged(game_root: Path) -> None:
    detector = GameDetector(
        (
            FakeSource((game_root,), name="first", platform=GamePlatform.UNKNOWN),
            FakeSource((game_root,), name="second", platform=GamePlatform.EPIC),
        )
    )

    installs = detector.detect_all()

    assert len(installs) == 1
    assert installs[0].platform is GamePlatform.EPIC


def test_a_broken_source_cannot_stop_detection(game_root: Path) -> None:
    detector = GameDetector((BrokenSource(), FakeSource((game_root,))))

    assert len(detector.detect_all()) == 1


def test_detect_primary_returns_none_without_candidates() -> None:
    assert GameDetector((FakeSource(()),)).detect_primary() is None


def test_from_path_accepts_a_manually_selected_folder(game_root: Path) -> None:
    install = GameDetector(()).from_path(game_root)

    assert install.root_path == game_root.resolve()
    assert install.detected_by == "manual"
    assert install.mods_path.name == "mods"


def test_from_path_rejects_a_folder_without_the_executable(tmp_path: Path) -> None:
    with pytest.raises(InvalidGameInstallationError):
        GameDetector(()).from_path(tmp_path)


def test_validation_reports_a_missing_mods_folder_as_a_warning(game_root: Path) -> None:
    report = GameDetector(()).validate(game_root)

    assert report.is_valid
    assert [issue.code for issue in report.warnings] == ["game.no_mods_folder"]


def test_validation_of_a_missing_folder_is_fatal(tmp_path: Path) -> None:
    report = GameDetector(()).validate(tmp_path / "nope")

    assert not report.is_valid
    assert report.fatal_issues[0].code == "game.missing_folder"


def test_platform_is_guessed_from_the_path(tmp_path: Path, game_root: Path) -> None:
    steam_like = tmp_path / "steamapps" / "common" / "Grand Theft Auto V"
    steam_like.parent.mkdir(parents=True)
    game_root.rename(steam_like)

    install = GameDetector(()).from_path(steam_like)

    assert install.platform is GamePlatform.STEAM

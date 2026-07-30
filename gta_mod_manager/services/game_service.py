"""Use-cases around selecting and inspecting the active game installation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gta_mod_manager.core.events import EventBus, GameChangedEvent
from gta_mod_manager.core.exceptions import InvalidGameInstallationError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.result import Result
from gta_mod_manager.detector.component_detector import ComponentDetector
from gta_mod_manager.detector.game_detector import GameDetector
from gta_mod_manager.models.component import ComponentReport
from gta_mod_manager.models.game_install import GameInstall, ValidationReport
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository
from gta_mod_manager.validator.game_validator import GameValidator

_LOGGER = get_logger("services.game")


@dataclass(frozen=True, slots=True)
class GameStatus:
    """Everything the dashboard needs to describe the installation."""

    install: GameInstall
    components: ComponentReport
    validation: ValidationReport

    @property
    def is_ready(self) -> bool:
        """Return whether mods can be installed right now."""
        return self.validation.is_valid


class GameService:
    """Finds, validates and remembers the active installation."""

    def __init__(
        self,
        detector: GameDetector,
        components: ComponentDetector,
        validator: GameValidator,
        settings: JsonSettingsRepository,
        bus: EventBus,
    ) -> None:
        self._detector = detector
        self._components = components
        self._validator = validator
        self._settings = settings
        self._bus = bus
        self._active: GameInstall | None = None

    @property
    def active(self) -> GameInstall | None:
        """Return the currently selected installation, if any."""
        return self._active

    def detect_all(self) -> tuple[GameInstall, ...]:
        """Return every installation found on this machine."""
        return self._detector.detect_all()

    def resolve_active(self) -> Result[GameInstall]:
        """Return the installation to work with.

        The saved path wins; auto-detection is the fallback. The result is
        cached and published on the event bus.
        """
        saved = self._settings.load().game_root
        if saved is not None:
            outcome = self.select(saved)
            if outcome.is_ok:
                return outcome
            _LOGGER.warning("Saved game path is no longer valid: %s", saved)

        detected = self._detector.detect_primary()
        if detected is None:
            return Result.fail(
                "No GTA V installation could be detected. Select the folder manually.",
                code="game.not_found",
            )
        return self.select(detected.root_path)

    def select(self, root: Path) -> Result[GameInstall]:
        """Make ``root`` the active installation and persist the choice."""
        try:
            install = self._detector.from_path(root)
        except InvalidGameInstallationError as error:
            return Result.fail(str(error), code="game.invalid")

        self._active = install
        self._settings.save(self._settings.load().with_game_root(install.root_path))
        self._bus.publish(
            GameChangedEvent(game_id=install.game_id, root_path=str(install.root_path))
        )
        _LOGGER.info("Active installation: %s (%s)", install.root_path, install.platform.value)
        return Result.ok(install)

    def validate(self, root: Path) -> ValidationReport:
        """Return the detector's validation report for ``root``."""
        return self._detector.validate(root)

    def status(self, install: GameInstall | None = None) -> Result[GameStatus]:
        """Return the full status of an installation for the dashboard."""
        target = install or self._active
        if target is None:
            resolved = self.resolve_active()
            if resolved.is_error:
                return Result.fail(resolved.error or "No installation", code=resolved.code)
            target = resolved.unwrap()

        components = self._components.detect(target)
        validation = self._validator.validate(target, components)
        return Result.ok(GameStatus(install=target, components=components, validation=validation))

    def ensure_mods_folder(self, install: GameInstall) -> Path:
        """Create ``<game>/mods`` when it does not exist yet and return it."""
        mods = install.mods_path
        if not mods.is_dir():
            mods.mkdir(parents=True, exist_ok=True)
            _LOGGER.info("Created the mods folder at %s", mods)
        return mods

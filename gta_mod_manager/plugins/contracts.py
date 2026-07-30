"""The contract a game plugin must satisfy.

The core knows nothing about GTA V. It asks the active plugin where mods go,
which components matter, which analyzer rules to add and how to turn a package
into an install plan. Supporting another game means writing one plugin, not
touching the core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from gta_mod_manager.analyzer.rule_base import AnalyzerRule
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.detector.component_catalog import ComponentProbe
from gta_mod_manager.detector.sources.base import DetectionSource
from gta_mod_manager.models.enums import InstallTarget
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.install_plan import InstallPlan
from gta_mod_manager.models.mod_package import ModPackage
from gta_mod_manager.models.variant_selection import VariantSelection
from gta_mod_manager.models.vehicle import VehicleManifest


@dataclass(frozen=True, slots=True)
class PlanRequest:
    """Input for :meth:`GamePlugin.build_install_plan`.

    Attributes:
        package: The analysed package to install.
        install: Target game installation.
        paths: Application paths, used to stage payloads outside the game.
        allow_root_install: Whether writing outside ``mods`` is permitted.
        overwrite_existing: Whether existing files may be replaced.
        variants: Which Add-On / Replace halves to install when both ship.
    """

    package: ModPackage
    install: GameInstall
    paths: AppPaths
    allow_root_install: bool = True
    overwrite_existing: bool = True
    variants: VariantSelection | None = None


@dataclass(frozen=True, slots=True)
class TargetDecision:
    """Where one packaged file is allowed to be written.

    Attributes:
        target: Safety zone the file belongs to; ``None`` means "refuse".
        relative_target: Path relative to the zone root. For archive imports
            this is the mods-folder ``.rpf`` file (e.g. ``x64e.rpf``).
        reason: Explanation shown in the preview and the log.
        needs_archive_editor: The file belongs inside an ``.rpf`` archive and
            cannot be installed automatically (manual OpenIV step).
        archive_member_path: When set, the file is imported into the mods
            copy of :attr:`relative_target` at this internal path.
    """

    target: InstallTarget | None
    relative_target: Path | None = None
    reason: str = ""
    needs_archive_editor: bool = False
    archive_member_path: str | None = None

    @property
    def is_archive_import(self) -> bool:
        """Return whether this decision targets a mods-folder RPF member."""
        return self.archive_member_path is not None and self.target is not None


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    """Descriptive information about a plugin."""

    game_id: str
    display_name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


class GamePlugin(ABC):
    """A game-specific strategy bundle."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return descriptive information about this plugin."""

    @property
    def game_id(self) -> str:
        """Return the identifier used to select this plugin."""
        return self.metadata.game_id

    @abstractmethod
    def detection_sources(self) -> tuple[DetectionSource, ...]:
        """Return the strategies used to find installations of this game."""

    @abstractmethod
    def component_catalog(self) -> tuple[ComponentProbe, ...]:
        """Return the components the detector should look for."""

    @abstractmethod
    def analyzer_rules(self) -> tuple[AnalyzerRule, ...]:
        """Return the classification rules specific to this game."""

    @abstractmethod
    def mods_root(self, install: GameInstall) -> Path:
        """Return the folder every mod is installed into by default."""

    @abstractmethod
    def decide_target(self, package: ModPackage, relative_path: Path) -> TargetDecision:
        """Return where one packaged file may be written."""

    @abstractmethod
    def build_install_plan(self, request: PlanRequest) -> InstallPlan:
        """Turn ``request`` into a reviewable, executable plan."""

    def parse_vehicles(
        self,
        package: ModPackage,
        variants: object | None = None,
    ) -> VehicleManifest:
        """Return vehicle metadata for ``package``.

        The default implementation reports nothing, which is correct for games
        without vehicle metadata files. ``variants`` is reserved for plugins
        that ship dual Add-On / Replace packages.
        """
        del variants
        return VehicleManifest()

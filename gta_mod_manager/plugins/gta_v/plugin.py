"""The GTA V game plugin: every piece of GTA-specific knowledge lives here."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from gta_mod_manager.analyzer.rule_base import AnalyzerRule
from gta_mod_manager.analyzer.rules import default_rules
from gta_mod_manager.core import constants
from gta_mod_manager.detector.component_catalog import ComponentProbe, default_catalog
from gta_mod_manager.detector.sources import DetectionSource, default_sources
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.install_plan import InstallPlan
from gta_mod_manager.models.mod_package import ModPackage
from gta_mod_manager.models.variant_selection import VariantSelection
from gta_mod_manager.models.vehicle import VehicleManifest
from gta_mod_manager.plugins.contracts import (
    GamePlugin,
    PlanRequest,
    PluginMetadata,
    TargetDecision,
)
from gta_mod_manager.plugins.gta_v.layout import PackageLayout
from gta_mod_manager.plugins.gta_v.oiv_package import OivPackage, OivPackageParser
from gta_mod_manager.plugins.gta_v.path_mapper import GtaVPathMapper
from gta_mod_manager.plugins.gta_v.plan_builder import GtaVPlanBuilder
from gta_mod_manager.plugins.gta_v.root_policy import RootInstallPolicy
from gta_mod_manager.plugins.gta_v.vehicle_meta import VehicleMetaParser


class GtaVPlugin(GamePlugin):
    """Implements the :class:`GamePlugin` contract for Grand Theft Auto V."""

    def __init__(
        self,
        policy: RootInstallPolicy | None = None,
        mapper: GtaVPathMapper | None = None,
        plan_builder: GtaVPlanBuilder | None = None,
        vehicle_parser: VehicleMetaParser | None = None,
        oiv_parser: OivPackageParser | None = None,
    ) -> None:
        self._policy = policy or RootInstallPolicy()
        self._mapper = mapper or GtaVPathMapper(self._policy)
        self._oiv_parser = oiv_parser or OivPackageParser()
        self._plan_builder = plan_builder or GtaVPlanBuilder(self._mapper, self._oiv_parser)
        self._vehicle_parser = vehicle_parser or VehicleMetaParser()

    @property
    def metadata(self) -> PluginMetadata:
        """Return descriptive information about this plugin."""
        return PluginMetadata(
            game_id=constants.GAME_ID_GTA_V,
            display_name=constants.GAME_TITLE_GTA_V,
            version=constants.APP_VERSION,
            author="Ultimate Mod Tools",
            description=(
                "Safe mod installation for GTA V: everything possible goes into "
                "<game>/mods, original archives are never modified."
            ),
            tags=("steam", "epic", "rockstar"),
        )

    @property
    def root_policy(self) -> RootInstallPolicy:
        """Return the root-installation whitelist."""
        return self._policy

    def detection_sources(self) -> tuple[DetectionSource, ...]:
        """Return the strategies used to find GTA V installations."""
        return default_sources()

    def component_catalog(self) -> tuple[ComponentProbe, ...]:
        """Return the components relevant to GTA V."""
        return default_catalog()

    def analyzer_rules(self) -> tuple[AnalyzerRule, ...]:
        """Return the GTA V classification rules."""
        return default_rules()

    def mods_root(self, install: GameInstall) -> Path:
        """Return ``<game>/mods``, the only folder mods are installed into."""
        return install.mods_path

    def decide_target(self, package: ModPackage, relative_path: Path) -> TargetDecision:
        """Return where one packaged file may be written."""
        layout = PackageLayout.detect(package.inventory, package.display_name)
        return self._mapper.decide(layout, PurePosixPath(relative_path.as_posix()))

    def build_install_plan(self, request: PlanRequest) -> InstallPlan:
        """Return the plan that installs ``request.package`` safely."""
        return self._plan_builder.build(request)

    def parse_vehicles(
        self,
        package: ModPackage,
        variants: VariantSelection | None = None,
    ) -> VehicleManifest:
        """Return the vehicle metadata declared by ``package``."""
        return self._vehicle_parser.parse(package.inventory, variants)

    def parse_openiv_package(self, package: ModPackage) -> OivPackage | None:
        """Return the OIV descriptor of ``package``, when it has one."""
        return self._oiv_parser.try_parse(package.inventory)


def create_plugin() -> GamePlugin:
    """Factory used by :func:`gta_mod_manager.plugins.registry.discover_plugins`."""
    return GtaVPlugin()

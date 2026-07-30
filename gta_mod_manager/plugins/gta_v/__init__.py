"""GTA V plugin: paths, root whitelist, vehicle metadata and OIV support."""

from gta_mod_manager.plugins.gta_v.layout import DlcPackLayout, PackageLayout
from gta_mod_manager.plugins.gta_v.oiv_package import OivCommand, OivPackage, OivPackageParser
from gta_mod_manager.plugins.gta_v.path_mapper import GtaVPathMapper
from gta_mod_manager.plugins.gta_v.plan_builder import GtaVPlanBuilder
from gta_mod_manager.plugins.gta_v.plugin import GtaVPlugin, create_plugin
from gta_mod_manager.plugins.gta_v.root_policy import RootInstallPolicy, RootVerdict
from gta_mod_manager.plugins.gta_v.vehicle_meta import VehicleMetaParser

__all__ = [
    "DlcPackLayout",
    "GtaVPathMapper",
    "GtaVPlanBuilder",
    "GtaVPlugin",
    "OivCommand",
    "OivPackage",
    "OivPackageParser",
    "PackageLayout",
    "RootInstallPolicy",
    "RootVerdict",
    "VehicleMetaParser",
    "create_plugin",
]

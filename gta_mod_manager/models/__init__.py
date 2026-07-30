"""Domain model of the mod manager.

Everything in this package is pure data plus behaviour that depends only on
that data. No filesystem access, no Qt, no third-party services.
"""

from gta_mod_manager.models.backup_snapshot import BackupEntry, BackupSnapshot, OperationRecord
from gta_mod_manager.models.classification import Evidence, KindScore, ModClassification
from gta_mod_manager.models.component import ComponentReport, ComponentSpec, DetectedComponent
from gta_mod_manager.models.conflict import Conflict, ConflictReport
from gta_mod_manager.models.enums import (
    ComponentStatus,
    ConfidenceLevel,
    ConflictSeverity,
    ConflictType,
    FileAction,
    GamePlatform,
    InstallTarget,
    ModKind,
    ModStatus,
    OperationKind,
    OperationStatus,
)
from gta_mod_manager.models.game_install import GameInstall, ValidationIssue, ValidationReport
from gta_mod_manager.models.install_plan import (
    ArchiveMemberImport,
    FileOperation,
    InstallPlan,
    ManualStep,
)
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.models.mod_package import (
    DependencyRef,
    InstalledFileRecord,
    InstalledMod,
    ModPackage,
    ReadmeExcerpt,
)
from gta_mod_manager.models.settings import AppSettings
from gta_mod_manager.models.vehicle import (
    DlcPackDefinition,
    HandlingDefinition,
    VehicleDefinition,
    VehicleManifest,
)

__all__ = [
    "AppSettings",
    "ArchiveMemberImport",
    "BackupEntry",
    "BackupSnapshot",
    "ComponentReport",
    "ComponentSpec",
    "ComponentStatus",
    "ConfidenceLevel",
    "Conflict",
    "ConflictReport",
    "ConflictSeverity",
    "ConflictType",
    "DependencyRef",
    "DetectedComponent",
    "DlcPackDefinition",
    "Evidence",
    "FileAction",
    "FileInventory",
    "FileOperation",
    "GameInstall",
    "GamePlatform",
    "HandlingDefinition",
    "InstallPlan",
    "InstallTarget",
    "InstalledFileRecord",
    "InstalledMod",
    "KindScore",
    "ManualStep",
    "ModClassification",
    "ModFile",
    "ModKind",
    "ModPackage",
    "ModStatus",
    "OperationKind",
    "OperationRecord",
    "OperationStatus",
    "ReadmeExcerpt",
    "ValidationIssue",
    "ValidationReport",
    "VehicleDefinition",
    "VehicleManifest",
]

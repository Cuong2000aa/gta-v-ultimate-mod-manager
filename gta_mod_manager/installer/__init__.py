"""Transactional installation and removal of mods."""

from gta_mod_manager.installer.conflict_detector import ConflictDetector
from gta_mod_manager.installer.conflict_rules import (
    ConflictContext,
    ConflictRule,
    default_conflict_rules,
)
from gta_mod_manager.installer.install_engine import InstallEngine, InstallOutcome
from gta_mod_manager.installer.operations import OperationExecutor
from gta_mod_manager.installer.transaction import JournalEntry, Transaction
from gta_mod_manager.installer.uninstaller import Uninstaller, UninstallOutcome

__all__ = [
    "ConflictContext",
    "ConflictDetector",
    "ConflictRule",
    "InstallEngine",
    "InstallOutcome",
    "JournalEntry",
    "OperationExecutor",
    "Transaction",
    "UninstallOutcome",
    "Uninstaller",
    "default_conflict_rules",
]

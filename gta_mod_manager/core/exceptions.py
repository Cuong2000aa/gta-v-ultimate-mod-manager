"""Application-wide exception hierarchy.

Every failure raised by the application derives from :class:`ModManagerError`
so the presentation layer can catch a single base type and still show a
meaningful, structured message.
"""

from __future__ import annotations

from typing import Any


class ModManagerError(Exception):
    """Base class for every error raised by the application.

    Args:
        message: Human readable description shown to the user.
        context: Optional structured details used by logs and the UI.
    """

    def __init__(self, message: str, /, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = dict(context)

    def __str__(self) -> str:
        """Return the message plus any context that was attached."""
        if not self.context:
            return self.message
        rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(self.context.items()))
        return f"{self.message} ({rendered})"


class ConfigurationError(ModManagerError):
    """Raised when settings or application paths are invalid."""


class DependencyMissingError(ModManagerError):
    """Raised when an optional third-party library is required but absent."""


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------
class DetectionError(ModManagerError):
    """Base class for game and component detection problems."""


class GameNotFoundError(DetectionError):
    """Raised when no GTA V installation could be located."""


class InvalidGameInstallationError(DetectionError):
    """Raised when a candidate folder is not a usable GTA V installation."""


# --------------------------------------------------------------------------
# Scanning / analysis
# --------------------------------------------------------------------------
class ScanError(ModManagerError):
    """Base class for archive extraction and inventory failures."""


class UnsupportedArchiveError(ScanError):
    """Raised when an archive format cannot be handled."""


class ArchiveExtractionError(ScanError):
    """Raised when extraction fails or produces an unsafe path."""


class AnalysisError(ModManagerError):
    """Raised when a mod package cannot be classified."""


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
class ValidationError(ModManagerError):
    """Raised when validation of an install plan or XML document fails."""


class SafetyViolationError(ValidationError):
    """Raised when an operation would touch a protected game file.

    This is the guard behind the absolute safety rule: original archives and
    executables of the game must never be modified.
    """


# --------------------------------------------------------------------------
# Installation / backup
# --------------------------------------------------------------------------
class InstallError(ModManagerError):
    """Raised when an install plan cannot be applied."""


class RollbackError(InstallError):
    """Raised when a failed installation could not be rolled back cleanly."""


class UninstallError(ModManagerError):
    """Raised when an installed mod cannot be removed."""


class BackupError(ModManagerError):
    """Raised when a backup snapshot cannot be created."""


class RestoreError(BackupError):
    """Raised when a backup snapshot cannot be restored."""


class SnapshotNotFoundError(BackupError):
    """Raised when a referenced snapshot no longer exists."""


# --------------------------------------------------------------------------
# Persistence / plugins
# --------------------------------------------------------------------------
class RepositoryError(ModManagerError):
    """Raised when the local persistence layer fails."""


class EntityNotFoundError(RepositoryError):
    """Raised when a requested entity is missing from a repository."""


class PluginError(ModManagerError):
    """Base class for plugin loading and execution failures."""


class PluginNotFoundError(PluginError):
    """Raised when a requested game plugin is not registered."""


class PluginLoadError(PluginError):
    """Raised when a plugin module cannot be imported or is malformed."""

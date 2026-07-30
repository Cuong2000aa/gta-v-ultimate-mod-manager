"""GTA V Ultimate Mod Manager.

A safety-first, plugin-based mod manager for Grand Theft Auto V built on
Clean Architecture: ``models`` holds the domain, ``services`` the use-cases,
``scanner``/``detector``/``installer``/``backup``/``repository`` the
infrastructure and ``gui`` the PySide6 presentation layer.
"""

from gta_mod_manager.core.constants import APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_VERSION", "__version__"]
__version__ = APP_VERSION

"""Detection of GTA V installations and of the components inside them."""

from gta_mod_manager.detector.component_catalog import ComponentProbe, default_catalog
from gta_mod_manager.detector.component_detector import ComponentDetector
from gta_mod_manager.detector.game_detector import GameDetector
from gta_mod_manager.detector.sources import default_sources

__all__ = [
    "ComponentDetector",
    "ComponentProbe",
    "GameDetector",
    "default_catalog",
    "default_sources",
]

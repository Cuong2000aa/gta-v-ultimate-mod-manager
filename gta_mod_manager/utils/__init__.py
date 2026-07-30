"""Reusable, dependency-light helpers shared by the infrastructure layers."""

from gta_mod_manager.utils.fs import (
    copy_file,
    delete_file,
    delete_tree,
    ensure_directory,
    human_size,
    is_relative_to,
    iter_files,
    normalise,
    safe_join,
    sanitise_name,
    unique_path,
)
from gta_mod_manager.utils.hashing import sha256_file, sha256_text, short_id
from gta_mod_manager.utils.patterns import matches_any, path_contains_directory
from gta_mod_manager.utils.xml_tools import load_xml, parse_xml_text, save_xml

__all__ = [
    "copy_file",
    "delete_file",
    "delete_tree",
    "ensure_directory",
    "human_size",
    "is_relative_to",
    "iter_files",
    "load_xml",
    "matches_any",
    "normalise",
    "parse_xml_text",
    "path_contains_directory",
    "safe_join",
    "sanitise_name",
    "save_xml",
    "sha256_file",
    "sha256_text",
    "short_id",
    "unique_path",
]

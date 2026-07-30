"""Tests for routing bare ScriptHookVDotNet assemblies into ``scripts/``."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from gta_mod_manager.analyzer.dependency_resolver import DependencyResolver
from gta_mod_manager.analyzer.engine import ModAnalyzer
from gta_mod_manager.analyzer.rules import default_rules
from gta_mod_manager.core.script_assets import is_script_assembly
from gta_mod_manager.models.enums import InstallTarget, ModKind
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.plugins.gta_v.layout import PackageLayout
from gta_mod_manager.plugins.gta_v.path_mapper import GtaVPathMapper


def _write_assembly(
    path: Path, *, managed: bool = True, libraries: tuple[str, ...] = ()
) -> Path:
    """Write a stub binary that looks like a compiled SHVDN script."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = b"MZ" + b"\x00" * 128
    if managed:
        body += b"mscorlib\x00ScriptHookVDotNet\x00"
    for library in libraries:
        body += library.encode() + b"\x00"
    path.write_bytes(body + b"\x00" * 64)
    return path


def _inventory(root: Path, *relative_paths: str) -> FileInventory:
    """Build an inventory of files that really exist under ``root``."""
    return FileInventory(
        root=root,
        files=tuple(
            ModFile(
                absolute_path=root / path,
                relative_path=PurePosixPath(path),
                size_bytes=(root / path).stat().st_size,
            )
            for path in relative_paths
        ),
    )


def test_only_managed_shvdn_binaries_are_recognised(tmp_path: Path) -> None:
    script = _write_assembly(tmp_path / "GTZ.dll")
    native = _write_assembly(tmp_path / "d3d11.dll", managed=False)
    loader = _write_assembly(tmp_path / "ScriptHookVDotNet2.dll")
    text = tmp_path / "readme.txt"
    text.write_text("ScriptHookVDotNet", encoding="utf-8")

    assert is_script_assembly(script)
    assert not is_script_assembly(native)
    assert not is_script_assembly(loader)
    assert not is_script_assembly(text)


def test_a_bare_script_dll_is_installed_into_the_scripts_folder(tmp_path: Path) -> None:
    _write_assembly(tmp_path / "GTZ.dll")
    _write_assembly(tmp_path / "NativePI.dll")
    layout = PackageLayout.detect(
        _inventory(tmp_path, "GTZ.dll", "NativePI.dll"), "Grand Theft Zombies"
    )
    mapper = GtaVPathMapper()

    for name in ("GTZ.dll", "NativePI.dll"):
        decision = mapper.decide(layout, PurePosixPath(name))
        assert decision.target is InstallTarget.SCRIPTS_FOLDER
        assert decision.relative_target == Path("scripts") / name


def test_a_script_already_under_scripts_keeps_its_subfolder(tmp_path: Path) -> None:
    _write_assembly(tmp_path / "scripts" / "MyMod" / "Cool.dll")
    layout = PackageLayout.detect(
        _inventory(tmp_path, "scripts/MyMod/Cool.dll"), "Cool"
    )

    decision = GtaVPathMapper().decide(layout, PurePosixPath("scripts/MyMod/Cool.dll"))

    assert decision.target is InstallTarget.SCRIPTS_FOLDER
    assert decision.relative_target == Path("scripts/MyMod/Cool.dll")


def test_nativeui_is_a_script_library_not_a_root_file(tmp_path: Path) -> None:
    _write_assembly(tmp_path / "NativeUI.dll")
    layout = PackageLayout.detect(_inventory(tmp_path, "NativeUI.dll"), "NativeUI")

    decision = GtaVPathMapper().decide(layout, PurePosixPath("NativeUI.dll"))

    assert decision.target is InstallTarget.SCRIPTS_FOLDER
    assert decision.relative_target == Path("scripts/NativeUI.dll")


def test_debug_symbols_follow_their_assembly(tmp_path: Path) -> None:
    _write_assembly(tmp_path / "ZombiesMod" / "ZombiesMod.dll")
    (tmp_path / "ZombiesMod" / "ZombiesMod.pdb").write_bytes(b"symbols")
    layout = PackageLayout.detect(
        _inventory(tmp_path, "ZombiesMod/ZombiesMod.dll", "ZombiesMod/ZombiesMod.pdb"),
        "Simple Zombie Mod",
    )

    decision = GtaVPathMapper().decide(layout, PurePosixPath("ZombiesMod/ZombiesMod.pdb"))

    assert decision.target is InstallTarget.SCRIPTS_FOLDER
    assert decision.relative_target == Path("scripts/ZombiesMod.pdb")


def test_an_orphan_pdb_is_not_treated_as_a_script(tmp_path: Path) -> None:
    (tmp_path / "notes.pdb").write_bytes(b"symbols")
    layout = PackageLayout.detect(_inventory(tmp_path, "notes.pdb"), "Orphan")

    decision = GtaVPathMapper().decide(layout, PurePosixPath("notes.pdb"))

    assert decision.target is InstallTarget.MODS_FOLDER


def test_a_script_using_nativeui_declares_the_dependency(tmp_path: Path) -> None:
    _write_assembly(tmp_path / "ZombiesMod.dll", libraries=("NativeUI",))

    classification = ModAnalyzer(default_rules()).analyze(
        _inventory(tmp_path, "ZombiesMod.dll"), "ZB123.zip"
    )
    dependencies = DependencyResolver().resolve(classification)

    assert "requires_nativeui" in classification.tags
    assert "NativeUI" in {item.display_name for item in dependencies}


def test_nativeui_does_not_depend_on_itself(tmp_path: Path) -> None:
    _write_assembly(tmp_path / "NativeUI.dll", libraries=("NativeUI",))

    classification = ModAnalyzer(default_rules()).analyze(
        _inventory(tmp_path, "NativeUI.dll"), "NativeUI"
    )

    assert "requires_nativeui" not in classification.tags


def test_a_bare_script_dll_classifies_as_a_dotnet_script(tmp_path: Path) -> None:
    _write_assembly(tmp_path / "GTZ.dll")
    _write_assembly(tmp_path / "NativePI.dll")

    classification = ModAnalyzer(default_rules()).analyze(
        _inventory(tmp_path, "GTZ.dll", "NativePI.dll"), "Grand Theft Zombies 0.25a.zip"
    )

    assert classification.primary is ModKind.SCRIPT_HOOK_DOTNET
    assert "requires_shvdn" in classification.tags

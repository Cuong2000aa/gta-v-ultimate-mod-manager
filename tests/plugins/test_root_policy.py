"""Tests for the whitelist that implements the absolute safety rule."""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from gta_mod_manager.models.enums import InstallTarget
from gta_mod_manager.plugins.gta_v.root_policy import RootInstallPolicy


@pytest.fixture()
def policy() -> RootInstallPolicy:
    """Return the default GTA V root policy."""
    return RootInstallPolicy()


@pytest.mark.parametrize(
    "path",
    [
        "GTA5.exe",
        "common.rpf",
        "x64a.rpf",
        "update/update.rpf",
        "steam_api64.dll",
    ],
)
def test_original_game_files_are_protected(policy: RootInstallPolicy, path: str) -> None:
    assert policy.is_protected(PurePosixPath(path))
    assert not policy.evaluate(PurePosixPath(path)).allowed


def test_an_rpf_inside_the_mods_folder_is_not_protected(policy: RootInstallPolicy) -> None:
    assert not policy.is_protected(PurePosixPath("mods/update/update.rpf"))


@pytest.mark.parametrize(
    "name",
    ["ScriptHookV.dll", "dinput8.dll", "OpenIV.asi", "trainer.asi", "enblocal.ini"],
)
def test_whitelisted_loose_files_may_live_in_the_root(
    policy: RootInstallPolicy, name: str
) -> None:
    verdict = policy.evaluate(PurePosixPath(name))

    assert verdict.allowed
    assert verdict.target is InstallTarget.GAME_ROOT


@pytest.mark.parametrize("name", ["vehicles.meta", "dlc.rpf", "adder2.yft", "random.dat"])
def test_everything_else_is_refused_in_the_root(
    policy: RootInstallPolicy, name: str
) -> None:
    assert not policy.evaluate(PurePosixPath(name)).allowed


def test_scripts_and_lml_map_onto_their_own_zones(policy: RootInstallPolicy) -> None:
    scripts = policy.evaluate(PurePosixPath("scripts/Cool.dll"))
    lml = policy.evaluate(PurePosixPath("lml/pack/content.xml"))

    assert scripts.target is InstallTarget.SCRIPTS_FOLDER
    assert lml.target is InstallTarget.LML_FOLDER


def test_other_whitelisted_folders_map_to_the_game_root(policy: RootInstallPolicy) -> None:
    verdict = policy.evaluate(PurePosixPath("reshade-shaders/Shaders/foo.fx"))

    assert verdict.allowed
    assert verdict.target is InstallTarget.GAME_ROOT


def test_a_custom_policy_can_narrow_the_whitelist() -> None:
    strict = RootInstallPolicy(file_patterns=("*.asi",), directories=())

    assert strict.evaluate(PurePosixPath("mod.asi")).allowed
    assert not strict.evaluate(PurePosixPath("ScriptHookV.dll")).allowed
    assert not strict.evaluate(PurePosixPath("scripts/Cool.dll")).allowed

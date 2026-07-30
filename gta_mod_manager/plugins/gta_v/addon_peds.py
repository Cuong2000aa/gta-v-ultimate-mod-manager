"""Creates and updates the manager-owned add-on ped DLC pack.

AddonPeds Editor's Rebuild button is a GUI-only step. This module does the
same job natively:

1. Maintain ``mods/update/x64/dlcpacks/umm_peds/dlc.rpf``.
2. Import ``.ydd`` / ``.yft`` / ``.ymt`` / ``.ytd`` into nested ``peds.rpf``.
3. Append a male ambient ``Item`` to ``peds.meta`` for each new model name.
4. Callers register ``dlcpacks:/umm_peds/`` in ``dlclist.xml`` separately.

The pack is OPEN-encrypted so OpenIV.asi can load it, matching every other
mods-folder archive this manager writes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from xml.etree import ElementTree

from fivefury import RpfArchive
from fivefury.crypto import OPEN_ENCRYPTION

from gta_mod_manager.core import constants
from gta_mod_manager.core.exceptions import InstallError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.ped_assets import PED_SET_SUFFIXES, model_stem
from gta_mod_manager.models.install_plan import ArchiveMemberImport
from gta_mod_manager.plugins.gta_v.rpf_archive import (
    force_open_encryption,
    materialize_resources_for_write,
)
from gta_mod_manager.utils import fs
from gta_mod_manager.utils.xml_tools import parse_xml_text

_LOGGER = get_logger("plugins.gta_v.addon_peds")

#: Prefix stored on :class:`~gta_mod_manager.models.mod_package.InstalledFileRecord`
#: archive members so uninstall can scrub ``peds.meta`` entries.
PED_META_MEMBER_PREFIX = "pedmeta:"

_SETUP2_XML = """<?xml version="1.0" encoding="UTF-8"?>
<SSetupData>
  <deviceName>dlc_{pack}</deviceName>
  <datFile>content.xml</datFile>
  <timeStamp>01/01/2024 00:00:00</timeStamp>
  <nameHash>{pack}</nameHash>
  <contentChangeSetGroups>
    <Item>
      <NameHash>GROUP_STARTUP</NameHash>
      <ContentChangeSets>
        <Item>{pack}_AUTOGEN</Item>
      </ContentChangeSets>
    </Item>
  </contentChangeSetGroups>
  <type>EXTRACONTENT_COMPAT_PACK</type>
  <order value="25" />
</SSetupData>
"""

_CONTENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CDataFileMgr__ContentsOfDataFileXml>
  <disabledFiles />
  <includedXmlFiles />
  <includedDataFiles />
  <dataFiles>
    <Item>
      <filename>dlc_{pack}:/{meta}</filename>
      <fileType>PED_METADATA_FILE</fileType>
      <overlay value="false" />
      <disabled value="true" />
      <persistent value="false" />
    </Item>
    <Item>
      <filename>dlc_{pack}:/{stream}</filename>
      <fileType>PEDSTREAM_FILE</fileType>
      <overlay value="false" />
      <disabled value="true" />
      <persistent value="true" />
    </Item>
  </dataFiles>
  <contentChangeSets>
    <Item>
      <changeSetName>{pack}_AUTOGEN</changeSetName>
      <filesToDisable />
      <filesToEnable>
        <Item>dlc_{pack}:/{meta}</Item>
        <Item>dlc_{pack}:/{stream}</Item>
      </filesToEnable>
      <txdToLoad />
      <txdToUnload />
      <residentResources />
      <unregisterResources />
    </Item>
  </contentChangeSets>
  <patchFiles />
</CDataFileMgr__ContentsOfDataFileXml>
"""

_EMPTY_PEDS_META = """<?xml version="1.0" encoding="UTF-8"?>
<CPedModelInfo__InitDataList>
  <InitDatas>
  </InitDatas>
</CPedModelInfo__InitDataList>
"""

_PED_ITEM_TEMPLATE = """\
      <Item>
         <Name>{name}</Name>
         <ClipDictionaryName>move_m@generic</ClipDictionaryName>
         <ExpressionSetName>expr_set_ambient_male</ExpressionSetName>
         <Pedtype>CIVMALE</Pedtype>
         <MovementClipSet>move_m@business@c</MovementClipSet>
         <StrafeClipSet>move_ped_strafing</StrafeClipSet>
         <MovementToStrafeClipSet>move_ped_to_strafe</MovementToStrafeClipSet>
         <InjuredStrafeClipSet>move_strafe_injured</InjuredStrafeClipSet>
         <FullBodyDamageClipSet>dam_ko</FullBodyDamageClipSet>
         <AdditiveDamageClipSet>dam_ad</AdditiveDamageClipSet>
         <DefaultGestureClipSet>ANIM_GROUP_GESTURE_M_GENERIC</DefaultGestureClipSet>
         <FacialClipsetGroupName>facial_clipset_group_gen_male</FacialClipsetGroupName>
         <DefaultVisemeClipSet>ANIM_GROUP_VISEMES_M_LO</DefaultVisemeClipSet>
         <PoseMatcherName>Male</PoseMatcherName>
         <PoseMatcherProneName>Male_prone</PoseMatcherProneName>
         <GetupSetHash>NMBS_SLOW_GETUPS</GetupSetHash>
         <CreatureMetadataName>ambientPed_upperWrinkles</CreatureMetadataName>
         <DecisionMakerName>DEFAULT</DecisionMakerName>
         <MotionTaskDataSetName>STANDARD_PED</MotionTaskDataSetName>
         <DefaultTaskDataSetName>STANDARD_PED</DefaultTaskDataSetName>
         <PedCapsuleName>STANDARD_MALE</PedCapsuleName>
         <RelationshipGroup>CIVMALE</RelationshipGroup>
         <NavCapabilitiesName>STANDARD_PED</NavCapabilitiesName>
         <PerceptionInfo>DEFAULT_PERCEPTION</PerceptionInfo>
         <DefaultBrawlingStyle>BS_AI</DefaultBrawlingStyle>
         <DefaultUnarmedWeapon>WEAPON_UNARMED</DefaultUnarmedWeapon>
         <Personality>SERVICEMALES</Personality>
         <CombatInfo>DEFAULT</CombatInfo>
         <VfxInfoName>VFXPEDINFO_HUMAN_GENERIC</VfxInfoName>
         <AmbientClipsForFlee>FLEE</AmbientClipsForFlee>
         <AbilityType>SAT_NONE</AbilityType>
         <ThermalBehaviour>TB_WARM</ThermalBehaviour>
         <SuperlodType>SLOD_HUMAN</SuperlodType>
         <ScenarioPopStreamingSlot>SCENARIO_POP_STREAMING_NORMAL</ScenarioPopStreamingSlot>
         <DefaultSpawningPreference>DSP_NORMAL</DefaultSpawningPreference>
         <IsStreamedGfx value="false" />
      </Item>
"""


def addon_peds_pack_dir(game_root: Path) -> Path:
    """Return ``mods/update/x64/dlcpacks/umm_peds`` under ``game_root``."""
    return (
        game_root
        / constants.MODS_FOLDER_NAME
        / Path(*constants.DLC_PACKS_RELATIVE.split("/"))
        / constants.ADDON_PEDS_PACK_NAME
    )


def addon_peds_dlc_path(game_root: Path) -> Path:
    """Return the absolute path of the manager ped pack ``dlc.rpf``."""
    return addon_peds_pack_dir(game_root) / "dlc.rpf"


def ped_meta_member(stem: str) -> str:
    """Return the journal marker for a ``peds.meta`` model entry."""
    return f"{PED_META_MEMBER_PREFIX}{stem.strip().lower()}"


def import_addon_peds(
    dlc_path: Path, members: Sequence[ArchiveMemberImport]
) -> tuple[str, ...]:
    """Ensure the pack exists and import ``members`` into nested ``peds.rpf``.

    Also upserts ``peds.meta`` entries for every distinct model stem present in
    ``members``. Returns the sorted model stems that were registered.
    """
    if not members:
        return ()
    for member in members:
        if not member.source_path.is_file():
            raise InstallError(
                "An add-on ped source file is missing",
                source=str(member.source_path),
                member_path=member.member_path,
            )

    fs.ensure_directory(dlc_path.parent)
    stems = sorted(
        {
            model_stem(Path(member.member_path).name)
            for member in members
            if Path(member.member_path).suffix.lower() in PED_SET_SUFFIXES
        }
    )
    if not stems:
        raise InstallError(
            "No ped model files were provided for the add-on ped pack",
            target=str(dlc_path),
        )

    payloads: dict[str, bytes] = {
        Path(member.member_path).name: member.source_path.read_bytes() for member in members
    }

    try:
        if dlc_path.is_file():
            _update_existing_pack(dlc_path, payloads, stems)
        else:
            _create_pack(dlc_path, payloads, stems)
    except InstallError:
        raise
    except Exception as error:  # noqa: BLE001
        raise InstallError(
            "Could not update the add-on ped pack",
            target=str(dlc_path),
            detail=str(error),
        ) from error

    _LOGGER.info(
        "Imported %d ped file(s) / %d model(s) into %s",
        len(payloads),
        len(stems),
        dlc_path,
    )
    return tuple(stems)


def remove_addon_peds(dlc_path: Path, stems: Iterable[str]) -> int:
    """Remove model files and ``peds.meta`` entries for ``stems``.

    Returns the number of model stems removed from metadata (0 when the pack
    is missing or already clean).
    """
    wanted = {stem.strip().lower() for stem in stems if stem and stem.strip()}
    if not wanted or not dlc_path.is_file():
        return 0

    try:
        with RpfArchive.from_path(str(dlc_path)) as archive:
            meta_entry = archive.find_entry(constants.ADDON_PEDS_META_MEMBER)
            meta_text = (
                archive.read_entry_bytes(meta_entry).decode("utf-8", errors="replace")
                if meta_entry is not None
                else _EMPTY_PEDS_META
            )
            new_meta, removed = _strip_ped_meta_items(meta_text, wanted)
            archive.add(constants.ADDON_PEDS_META_MEMBER, new_meta.encode("utf-8"))

            stream_entry = archive.find_entry(constants.ADDON_PEDS_STREAM_ARCHIVE)
            if stream_entry is not None:
                nested = archive.load_nested_archive(stream_entry)
                if nested is not None:
                    _remove_stems_from_stream(nested, wanted)

            materialize_resources_for_write(archive)
            force_open_encryption(archive)
            archive.save(str(dlc_path))
    except Exception as error:  # noqa: BLE001
        raise InstallError(
            "Could not remove models from the add-on ped pack",
            target=str(dlc_path),
            detail=str(error),
        ) from error

    _LOGGER.info("Removed %d ped model(s) from %s", removed, dlc_path)
    return removed


def _create_pack(dlc_path: Path, payloads: Mapping[str, bytes], stems: Sequence[str]) -> None:
    """Write a brand-new manager ped pack containing ``payloads``."""
    pack = constants.ADDON_PEDS_PACK_NAME
    archive = RpfArchive.empty("dlc")
    archive.encryption = OPEN_ENCRYPTION
    archive.add(
        "setup2.xml",
        _SETUP2_XML.format(pack=pack).encode("utf-8"),
    )
    archive.add(
        "content.xml",
        _CONTENT_XML.format(
            pack=pack,
            meta=constants.ADDON_PEDS_META_MEMBER,
            stream=constants.ADDON_PEDS_STREAM_ARCHIVE,
        ).encode("utf-8"),
    )
    archive.add(
        constants.ADDON_PEDS_META_MEMBER,
        _build_peds_meta((), stems).encode("utf-8"),
    )
    _entry, nested = archive.add_nested_archive(constants.ADDON_PEDS_STREAM_ARCHIVE)
    for name, data in payloads.items():
        nested.add(name, data)
    archive.save(str(dlc_path))


def _update_existing_pack(
    dlc_path: Path, payloads: Mapping[str, bytes], stems: Sequence[str]
) -> None:
    """Merge ``payloads`` and ``stems`` into an existing manager ped pack."""
    with RpfArchive.from_path(str(dlc_path)) as archive:
        meta_entry = archive.find_entry(constants.ADDON_PEDS_META_MEMBER)
        if meta_entry is None:
            existing_meta = _EMPTY_PEDS_META
        else:
            existing_meta = archive.read_entry_bytes(meta_entry).decode(
                "utf-8", errors="replace"
            )
        archive.add(
            constants.ADDON_PEDS_META_MEMBER,
            _merge_peds_meta(existing_meta, stems).encode("utf-8"),
        )

        stream_entry = archive.find_entry(constants.ADDON_PEDS_STREAM_ARCHIVE)
        if stream_entry is None:
            _entry, nested = archive.add_nested_archive(constants.ADDON_PEDS_STREAM_ARCHIVE)
        else:
            nested = archive.load_nested_archive(stream_entry)
            if nested is None:
                raise InstallError(
                    "Could not open nested peds.rpf inside the add-on ped pack",
                    target=str(dlc_path),
                )
        for name, data in payloads.items():
            nested.add(name, data)

        materialize_resources_for_write(archive)
        force_open_encryption(archive)
        archive.save(str(dlc_path))


def _build_peds_meta(_existing_names: Iterable[str], stems: Sequence[str]) -> str:
    """Return a fresh ``peds.meta`` containing only ``stems``."""
    return _merge_peds_meta(_EMPTY_PEDS_META, stems)


def _merge_peds_meta(existing_xml: str, stems: Sequence[str]) -> str:
    """Append missing ``Item`` blocks for ``stems`` into ``existing_xml``."""
    root = _parse_meta_root(existing_xml)
    init = root.find("InitDatas")
    if init is None:
        init = ElementTree.SubElement(root, "InitDatas")
    present = {
        (item.findtext("Name") or "").strip().lower()
        for item in init.findall("Item")
    }
    for stem in stems:
        if stem.lower() in present:
            continue
        item_xml = _PED_ITEM_TEMPLATE.format(name=stem)
        init.append(ElementTree.fromstring(item_xml))
        present.add(stem.lower())
    return _serialize_meta(root)


def _strip_ped_meta_items(existing_xml: str, stems: set[str]) -> tuple[str, int]:
    """Remove ``Item`` blocks whose ``Name`` is in ``stems``."""
    root = _parse_meta_root(existing_xml)
    init = root.find("InitDatas")
    if init is None:
        return _serialize_meta(root), 0
    removed = 0
    for item in list(init.findall("Item")):
        name = (item.findtext("Name") or "").strip().lower()
        if name in stems:
            init.remove(item)
            removed += 1
    return _serialize_meta(root), removed


def _parse_meta_root(text: str) -> ElementTree.Element:
    """Parse ``peds.meta``, recovering to an empty document when broken."""
    try:
        result = parse_xml_text(text)
        return result.root
    except Exception:  # noqa: BLE001
        _LOGGER.warning("peds.meta was unreadable; regenerating an empty document")
        return ElementTree.fromstring(_EMPTY_PEDS_META)


def _serialize_meta(root: ElementTree.Element) -> str:
    """Return ``root`` as an XML document with the XML declaration."""
    body = ElementTree.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def _remove_stems_from_stream(nested: RpfArchive, stems: set[str]) -> None:
    """Delete every stream member whose model stem is in ``stems``."""
    for entry in list(nested.iter_entries()):
        name = getattr(entry, "name", "") or ""
        if Path(name).suffix.lower() not in PED_SET_SUFFIXES:
            continue
        if model_stem(name) not in stems:
            continue
        parent = getattr(entry, "parent", None)
        if parent is not None and hasattr(parent, "files"):
            parent.files.remove(entry)
            nested._invalidate_index()

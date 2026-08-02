"""Parses (and repairs) the vehicle metadata files a GTA V mod ships.

Handled documents:

* ``vehicles.meta``     - model names, txd, handling id, manufacturer
* ``handling.meta``     - handling ids and mass
* ``carvariations.meta``/``carcols.meta`` - referenced model names
* ``content.xml`` / ``setup2.xml``        - add-on DLC pack descriptors

When the meta files live *inside* an encrypted ``dlc.rpf`` (the usual OpenIV
add-on layout), the parser prefers spawn phrases written in the package
ReadMe / INSTALL text, then falls back to model names found as ``.yft``
strings in the archive, then to the DLC pack folder name. Packages that
ship both an Add-On and a Replace folder report the Replace spawn code,
matching the install preference.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

from gta_mod_manager.core import constants
from gta_mod_manager.core.exceptions import ValidationError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.mod_file import FileInventory
from gta_mod_manager.models.variant_selection import VariantSelection
from gta_mod_manager.models.vehicle import (
    DlcPackDefinition,
    HandlingDefinition,
    VehicleDefinition,
    VehicleManifest,
)
from gta_mod_manager.plugins.gta_v import readme_spawn
from gta_mod_manager.plugins.gta_v.layout import (
    ADDON_VARIANT_NAMES,
    REPLACE_VARIANT_NAMES,
    path_under_named_folders,
)
from gta_mod_manager.utils import xml_tools

_LOGGER = get_logger("plugins.gta_v.vehicle_meta")

#: Asset suffixes that are LODs / variants of a model, not spawnable names.
_NON_SPAWN_SUFFIXES: tuple[str, ...] = (
    "_hi",
    "_lod",
    "_slod",
    "_livery",
    "_damaged",
    "_garage",
)

#: Fragments of an asset name that never form a spawn code on their own.
_MODEL_NOISE_NAMES: frozenset[str] = frozenset(
    {"hi", "lod", "dlc", "vehicle", "vehicles", "template", "null", "prop"}
)

#: Naming used by tuning parts (``sesto_int_roll.yft``, ``cara2_bumfa.yft``),
#: which ride along in the same archive as the car but cannot be spawned.
_PART_NAME_FRAGMENTS: tuple[str, ...] = (
    "_int_",
    "_ext_",
    "_bon",
    "_spoil",
    "_roll",
    "_wing",
    "_cage",
    "_roof",
    "_bumper",
    "_skirt",
    "_bumf",
    "_bumr",
    "_bum",
    "_hood",
    "_grill",
    "_exh",
    "_liv",
    "_arch",
    "_split",
    "_fend",
    "_door",
    "_mir",
    "_seat",
    "_steer",
)

#: Trainers reject anything shorter, and short matches are usually noise.
_MINIMUM_MODEL_NAME_LENGTH = 3

#: A package declaring more vehicles than this ships a game-wide meta dump
#: (the "all vanilla cars" file some authors include), so the assets it
#: actually contains describe the mod far better than the document does.
_META_ENTRY_SANITY_LIMIT = 20

#: ``name.yft`` / ``name.ytd`` embedded as ASCII inside an ``.rpf`` archive.
_RPF_MODEL_PATTERN = re.compile(rb"([a-zA-Z0-9_]{2,40})\.(yft|ytd)\x00?")


class VehicleMetaParser:
    """Extracts vehicle information from an extracted package."""

    def parse(
        self,
        inventory: FileInventory,
        selection: VariantSelection | None = None,
    ) -> VehicleManifest:
        """Return everything that can be learned about the package's vehicles."""
        repaired: list[Path] = []
        handling = self._parse_handling(inventory, repaired)
        dual = self._is_dual(inventory)
        chosen = selection or (
            VariantSelection(addon=False, replace=True)
            if dual
            else VariantSelection(addon=True, replace=True)
        )
        include_addon = (not dual) or chosen.addon
        include_replace = (not dual) or chosen.replace
        packs = self._parse_dlc_packs(inventory, repaired) if include_addon else []
        vehicles = self._collect_vehicles(
            inventory,
            packs,
            repaired,
            include_addon=include_addon,
            include_replace=include_replace,
            dual=dual,
        )
        return VehicleManifest(
            vehicles=tuple(vehicles),
            handling=tuple(handling),
            dlc_packs=tuple(packs),
            repaired_files=tuple(repaired),
        )

    def _collect_vehicles(
        self,
        inventory: FileInventory,
        packs: list[DlcPackDefinition],
        repaired: list[Path],
        *,
        include_addon: bool,
        include_replace: bool,
        dual: bool,
    ) -> list[VehicleDefinition]:
        """Return the spawn codes, from the most reliable source available.

        Priority:

        1. When only Replace is selected on a dual package, use that half.
        2. When only Add-On is selected, use packs / meta / readme (skip Replace).
        3. When both are selected, union Replace spawn codes with Add-On ones.
        4. Spawn phrases in the packaged ReadMe / INSTALL / INSTRUCTION files.
        5. A real ``vehicles.meta`` (ignored when it is clearly a vanilla dump).
        6. Model files (``.yft``) and names embedded in ``dlc.rpf``.
        7. The DLC pack folder name.
        """
        if dual and include_replace and not include_addon:
            replace_only = self._replace_half(inventory, packs, repaired)
            if replace_only:
                return replace_only

        if dual and include_addon and include_replace:
            replace_half = self._replace_half(inventory, packs, repaired)
            addon_half = self._addon_half(inventory, packs, repaired)
            merged = self._deduplicate([*replace_half, *addon_half])
            if merged:
                return merged

        if dual and include_addon and not include_replace:
            addon_only = self._addon_half(inventory, packs, repaired)
            if addon_only:
                return addon_only

        from_readme = self._infer_from_readme(inventory)
        if from_readme:
            return from_readme

        declared = self._parse_vehicles(inventory, repaired) or self._infer_from_variations(
            inventory, repaired
        )
        if declared and len(declared) <= _META_ENTRY_SANITY_LIMIT:
            return declared

        observed = self._drop_part_like(
            self._deduplicate(
                [
                    *self._infer_from_rpf_assets(inventory, packs),
                    *self._infer_from_loose_assets(
                        inventory, skip_addon_when_dual=dual and include_replace
                    ),
                ]
            )
        )
        if observed:
            return observed
        return declared or self._infer_from_pack_names(inventory, packs)

    def _addon_half(
        self,
        inventory: FileInventory,
        packs: list[DlcPackDefinition],
        repaired: list[Path],
    ) -> list[VehicleDefinition]:
        """Return spawn codes drawn from the Add-On half of a dual package."""
        from_readme = self._infer_from_readme(inventory, addon_only=True)
        if from_readme:
            return from_readme
        declared = self._parse_vehicles(inventory, repaired) or self._infer_from_variations(
            inventory, repaired
        )
        addon_files = {
            file.absolute_path
            for file in inventory.files
            if path_under_named_folders(file.relative_path, ADDON_VARIANT_NAMES)
        }
        filtered = [
            vehicle
            for vehicle in declared
            if vehicle.source_file is None or vehicle.source_file in addon_files
        ]
        if filtered and len(filtered) <= _META_ENTRY_SANITY_LIMIT:
            return filtered
        observed = self._drop_part_like(
            self._deduplicate(
                [
                    *self._infer_from_rpf_assets(inventory, packs),
                    *self._infer_from_loose_assets(inventory, addon_only=True),
                ]
            )
        )
        return observed or self._infer_from_pack_names(inventory, packs)

    def _replace_half(
        self,
        inventory: FileInventory,
        packs: list[DlcPackDefinition],
        repaired: list[Path],
    ) -> list[VehicleDefinition]:
        """Return spawn codes drawn only from the Replace half of a dual package."""
        del packs  # replace installs do not use DLC packs
        assets = self._drop_part_like(
            self._infer_from_loose_assets(inventory, replace_only=True)
        )
        if assets:
            return assets

        replace_files = {
            file.absolute_path
            for file in inventory.files
            if path_under_named_folders(file.relative_path, REPLACE_VARIANT_NAMES)
        }
        declared = [
            vehicle
            for vehicle in (
                self._parse_vehicles(inventory, repaired)
                or self._infer_from_variations(inventory, repaired)
            )
            if vehicle.source_file in replace_files
        ]
        if declared and len(declared) <= _META_ENTRY_SANITY_LIMIT:
            return declared

        from_readme = self._infer_from_readme(inventory, replace_only=True)
        if from_readme:
            return from_readme
        return assets

    @staticmethod
    def _is_dual(inventory: FileInventory) -> bool:
        """Return whether the package ships both an Add-On and a Replace half."""
        folders = {part for item in inventory.files for part in item.parts_lower[:-1]}
        return bool(folders & ADDON_VARIANT_NAMES) and bool(folders & REPLACE_VARIANT_NAMES)

    @staticmethod
    def _prefers_replace(inventory: FileInventory) -> bool:
        """Compatibility helper: dual packages defaulted to Replace historically."""
        return VehicleMetaParser._is_dual(inventory)

    def _infer_from_readme(
        self,
        inventory: FileInventory,
        *,
        replace_only: bool = False,
        addon_only: bool = False,
    ) -> list[VehicleDefinition]:
        """Return spawn codes the author wrote into the package documentation."""
        found: list[VehicleDefinition] = []
        for code, source in readme_spawn.extract_spawn_codes(inventory):
            if replace_only or addon_only:
                relative = next(
                    (
                        file.relative_path
                        for file in inventory.files
                        if file.absolute_path == source
                    ),
                    None,
                )
                if relative is None:
                    continue
                if replace_only and not path_under_named_folders(
                    relative, REPLACE_VARIANT_NAMES
                ):
                    continue
                if addon_only and not path_under_named_folders(
                    relative, ADDON_VARIANT_NAMES
                ):
                    continue
            found.append(VehicleDefinition(model_name=code, source_file=source))
        return found

    def _infer_from_loose_assets(
        self,
        inventory: FileInventory,
        *,
        replace_only: bool = False,
        addon_only: bool = False,
        skip_addon_when_dual: bool = False,
    ) -> list[VehicleDefinition]:
        """Return the models named by the ``.yft`` files shipped in the package.

        Replacement mods rename their model after the vanilla car they take
        over (``buffalo2.yft``), which *is* the spawn code the user needs.
        Tuning parts usually ship as ``.yft`` only; real cars include a
        matching ``.ytd``, so complete pairs win when both are present.
        """
        models: dict[str, VehicleDefinition] = {}
        textures: set[str] = set()
        for file in inventory.by_suffix(".yft", ".ytd"):
            if replace_only and not path_under_named_folders(
                file.relative_path, REPLACE_VARIANT_NAMES
            ):
                continue
            if addon_only and not path_under_named_folders(
                file.relative_path, ADDON_VARIANT_NAMES
            ):
                continue
            if (
                skip_addon_when_dual
                and path_under_named_folders(file.relative_path, ADDON_VARIANT_NAMES)
            ):
                continue
            name = file.absolute_path.stem.lower()
            if name.endswith("_hi"):
                name = name[: -len("_hi")]
            if not self._is_spawnable_model(name):
                continue
            if file.suffix == ".ytd":
                textures.add(name)
                continue
            models.setdefault(
                name, VehicleDefinition(model_name=name, source_file=file.absolute_path)
            )
        complete = {name: models[name] for name in models if name in textures}
        preferred = complete or models
        return list(preferred.values())

    def _parse_vehicles(
        self, inventory: FileInventory, repaired: list[Path]
    ) -> list[VehicleDefinition]:
        """Read every ``vehicles.meta`` in the package."""
        found: list[VehicleDefinition] = []
        for file in inventory.by_name(constants.VEHICLES_META):
            root = self._load(file.absolute_path, repaired)
            if root is None:
                continue
            for item in xml_tools.iter_elements(root, "Item"):
                model = xml_tools.find_text(item, "modelName")
                if not model:
                    continue
                found.append(
                    VehicleDefinition(
                        model_name=model.lower(),
                        handling_id=xml_tools.find_text(item, "handlingId") or None,
                        txd_name=xml_tools.find_text(item, "txdName") or None,
                        manufacturer=self._manufacturer(item),
                        vehicle_class=xml_tools.find_attribute(item, "vehicleClass", "value"),
                        source_file=file.absolute_path,
                    )
                )
        return found

    def _parse_handling(
        self, inventory: FileInventory, repaired: list[Path]
    ) -> list[HandlingDefinition]:
        """Read every ``handling.meta`` in the package."""
        found: list[HandlingDefinition] = []
        for file in inventory.by_name(constants.HANDLING_META):
            root = self._load(file.absolute_path, repaired)
            if root is None:
                continue
            for item in xml_tools.iter_elements(root, "Item"):
                handling_id = xml_tools.find_text(item, "handlingName")
                if not handling_id:
                    continue
                found.append(
                    HandlingDefinition(
                        handling_id=handling_id.upper(),
                        mass=self._float_attribute(item, "fMass"),
                        source_file=file.absolute_path,
                    )
                )
        return found

    def _parse_dlc_packs(
        self, inventory: FileInventory, repaired: list[Path]
    ) -> list[DlcPackDefinition]:
        """Describe every add-on DLC pack declared by the package."""
        packs_by_name: dict[str, DlcPackDefinition] = {}
        setup_files = {
            file.absolute_path.parent: file for file in inventory.by_name(constants.SETUP2_XML)
        }
        content_files = {
            file.absolute_path.parent: file for file in inventory.by_name(constants.CONTENT_XML)
        }

        for directory in sorted(set(setup_files) | set(content_files)):
            setup = setup_files.get(directory)
            content = content_files.get(directory)
            device_name: str | None = None
            order: int | None = None

            if setup is not None:
                root = self._load(setup.absolute_path, repaired)
                if root is not None:
                    device_name = xml_tools.find_text(root, "deviceName") or None
                    order = self._int_text(root, "order")

            # The folder name is what goes into dlcpacks and dlclist.xml;
            # deviceName is a separate identifier used inside setup2.xml.
            pack_name = directory.name.lower()
            packs_by_name[pack_name] = DlcPackDefinition(
                pack_name=pack_name,
                device_name=device_name,
                dlc_order=order,
                content_xml=content.absolute_path if content else None,
                setup_xml=setup.absolute_path if setup else None,
            )

        # Many OpenIV add-ons ship only ``<pack>/dlc.rpf`` with no loose XML.
        for file in inventory.by_name("dlc.rpf"):
            pack_name = file.relative_path.parent.name.lower()
            if not pack_name or pack_name in {
                "dlcpacks",
                constants.MODS_FOLDER_NAME,
                "x64",
                ".",
            }:
                continue
            packs_by_name.setdefault(pack_name, DlcPackDefinition(pack_name=pack_name))

        return list(packs_by_name.values())

    def _infer_from_variations(
        self, inventory: FileInventory, repaired: list[Path]
    ) -> list[VehicleDefinition]:
        """Fall back to ``carvariations.meta`` when ``vehicles.meta`` is absent.

        Replacement mods often ship only colour variations, which still name
        the model they target.
        """
        found: list[VehicleDefinition] = []
        for file in inventory.by_name(constants.CARVARIATIONS_META, constants.CARCOLS_META):
            root = self._load(file.absolute_path, repaired)
            if root is None:
                continue
            for item in xml_tools.iter_elements(root, "Item"):
                model = xml_tools.find_text(item, "modelName")
                if model:
                    found.append(
                        VehicleDefinition(
                            model_name=model.lower(), source_file=file.absolute_path
                        )
                    )
        return found

    def _infer_from_rpf_assets(
        self, inventory: FileInventory, packs: list[DlcPackDefinition]
    ) -> list[VehicleDefinition]:
        """Read spawnable model names from ``.yft``/``.ytd`` strings inside RPFs.

        Add-on packs almost always bury ``vehicles.meta`` inside ``dlc.rpf``.
        The mesh names (``lykan.yft``) are still stored as plain ASCII, so a
        trainer spawn code can be recovered without decrypting the archive.

        A car ships both a model and its texture dictionary, while tuning
        parts only ship a model, so names seen as ``.yft`` *and* ``.ytd`` are
        kept in preference to the rest. When the pack folder has a clear name,
        leftover template models that do not match it (common when authors
        reuse another car's RPF) are dropped as well.
        """
        found: dict[str, VehicleDefinition] = {}
        models: set[str] = set()
        textures: set[str] = set()
        for file in inventory.by_suffix(".rpf"):
            try:
                payload = file.absolute_path.read_bytes()
            except OSError as error:
                _LOGGER.debug("Could not read %s for model names: %s", file.name, error)
                continue
            for match in _RPF_MODEL_PATTERN.finditer(payload):
                name = match.group(1).decode("ascii", errors="ignore").lower()
                if not self._is_spawnable_model(name):
                    continue
                target = models if match.group(2) == b"yft" else textures
                target.add(name)
                found.setdefault(
                    name, VehicleDefinition(model_name=name, source_file=file.absolute_path)
                )

        complete = {name: found[name] for name in found if name in models & textures}
        preferred = self._prefer_pack_matching_models(complete or found, packs)
        if preferred:
            _LOGGER.info(
                "Inferred spawn code(s) from RPF assets: %s",
                ", ".join(sorted(vehicle.model_name for vehicle in preferred)),
            )
        return preferred

    @staticmethod
    def _prefer_pack_matching_models(
        found: dict[str, VehicleDefinition], packs: list[DlcPackDefinition]
    ) -> list[VehicleDefinition]:
        """Keep models that match a DLC pack name when that filter is useful."""
        if not found:
            return []
        pack_names = {pack.pack_name.lower() for pack in packs}
        if not pack_names:
            return list(found.values())
        matched = [
            vehicle
            for name, vehicle in found.items()
            if name in pack_names or any(name.startswith(f"{pack}_") for pack in pack_names)
        ]
        return matched or list(found.values())

    def _infer_from_pack_names(
        self, inventory: FileInventory, packs: list[DlcPackDefinition]
    ) -> list[VehicleDefinition]:
        """Use the DLC pack folder name when no model asset name was found.

        Authors almost always name the pack after the spawn code
        (``dlcpacks/lykan/dlc.rpf`` -> spawn ``lykan``).
        """
        del inventory  # kept for symmetry with the other infer helpers
        return [
            VehicleDefinition(model_name=pack.pack_name)
            for pack in packs
            if self._is_spawnable_model(pack.pack_name)
        ]

    @staticmethod
    def _drop_part_like(vehicles: list[VehicleDefinition]) -> list[VehicleDefinition]:
        """Remove tuning parts, unless that would leave nothing to show."""
        cars = [
            vehicle
            for vehicle in vehicles
            if not any(part in vehicle.model_name for part in _PART_NAME_FRAGMENTS)
        ]
        return cars or vehicles

    @staticmethod
    def _deduplicate(vehicles: list[VehicleDefinition]) -> list[VehicleDefinition]:
        """Return ``vehicles`` without repeating a model name."""
        unique: dict[str, VehicleDefinition] = {}
        for vehicle in vehicles:
            unique.setdefault(vehicle.model_name, vehicle)
        return list(unique.values())

    @staticmethod
    def _is_spawnable_model(name: str) -> bool:
        """Return whether ``name`` looks like a trainer spawn code."""
        lowered = name.lower()
        if len(lowered) < _MINIMUM_MODEL_NAME_LENGTH or not lowered[0].isalpha():
            return False
        if lowered in _MODEL_NOISE_NAMES:
            return False
        return not any(lowered.endswith(suffix) for suffix in _NON_SPAWN_SUFFIXES)

    @staticmethod
    def _manufacturer(item: ElementTree.Element) -> str | None:
        """Return the manufacturer declared by a vehicle item, if any."""
        for tag in ("vehicleMakeName", "manufacturer"):
            value = xml_tools.find_text(item, tag)
            if value:
                return value
        return None

    @staticmethod
    def _float_attribute(item: ElementTree.Element, tag: str) -> float | None:
        """Return a numeric ``value`` attribute as float, when parseable."""
        raw = xml_tools.find_attribute(item, tag, "value")
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _int_text(root: ElementTree.Element, tag: str) -> int | None:
        """Return the integer ``value`` attribute of ``tag``, when parseable."""
        raw = xml_tools.find_attribute(root, tag, "value") or xml_tools.find_text(root, tag)
        try:
            return int(raw) if raw else None
        except ValueError:
            return None

    @staticmethod
    def _load(path: Path, repaired: list[Path]) -> ElementTree.Element | None:
        """Parse ``path``, recording it when a repair was necessary."""
        try:
            result = xml_tools.load_xml(path)
        except ValidationError as error:
            _LOGGER.warning("Skipping unparseable meta file %s: %s", path.name, error)
            return None
        if result.was_repaired:
            repaired.append(path)
        return result.root

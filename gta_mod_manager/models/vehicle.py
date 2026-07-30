"""Domain objects describing vehicles declared by a mod package."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VehicleDefinition:
    """A vehicle entry parsed out of ``vehicles.meta``.

    Attributes:
        model_name: Spawn code, e.g. ``adder``. Always lowercase.
        handling_id: Identifier linking the vehicle to ``handling.meta``.
        txd_name: Texture dictionary name.
        manufacturer: Manufacturer label when the meta file declares one.
        vehicle_class: Class such as ``VC_SUPER``.
        source_file: Meta file the definition came from.
    """

    model_name: str
    handling_id: str | None = None
    txd_name: str | None = None
    manufacturer: str | None = None
    vehicle_class: str | None = None
    source_file: Path | None = None

    @property
    def spawn_code(self) -> str:
        """Return the code used with trainers to spawn the vehicle."""
        return self.model_name


@dataclass(frozen=True, slots=True)
class HandlingDefinition:
    """A handling entry parsed out of ``handling.meta``."""

    handling_id: str
    mass: float | None = None
    source_file: Path | None = None


@dataclass(frozen=True, slots=True)
class DlcPackDefinition:
    """An add-on DLC pack described by ``content.xml`` / ``setup2.xml``.

    Attributes:
        pack_name: Folder name of the pack, e.g. ``adder2``.
        device_name: ``deviceName`` declared in ``setup2.xml``.
        dlc_order: Optional load order hint from ``setup2.xml``.
        content_xml: Location of the pack's ``content.xml``.
        setup_xml: Location of the pack's ``setup2.xml``.
    """

    pack_name: str
    device_name: str | None = None
    dlc_order: int | None = None
    content_xml: Path | None = None
    setup_xml: Path | None = None

    @property
    def dlclist_entry(self) -> str:
        """Return the line that must be added to ``dlclist.xml``."""
        return f"dlcpacks:/{self.pack_name}/"


@dataclass(frozen=True, slots=True)
class VehicleManifest:
    """Everything the vehicle parser learned about a package."""

    vehicles: tuple[VehicleDefinition, ...] = field(default_factory=tuple)
    handling: tuple[HandlingDefinition, ...] = field(default_factory=tuple)
    dlc_packs: tuple[DlcPackDefinition, ...] = field(default_factory=tuple)
    repaired_files: tuple[Path, ...] = field(default_factory=tuple)

    @property
    def is_addon(self) -> bool:
        """Return whether the package ships its own DLC pack."""
        return bool(self.dlc_packs)

    @property
    def is_empty(self) -> bool:
        """Return whether no vehicle information was found at all."""
        return not (self.vehicles or self.handling or self.dlc_packs)

    @property
    def spawn_codes(self) -> tuple[str, ...]:
        """Return every spawn code declared by the package."""
        return tuple(vehicle.spawn_code for vehicle in self.vehicles)

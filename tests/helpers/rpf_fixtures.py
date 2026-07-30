"""Write a minimal OPEN ``update.rpf`` containing ``dlclist.xml``."""

from __future__ import annotations

from pathlib import Path

from fivefury import RpfArchive
from fivefury.crypto import OPEN_ENCRYPTION

_DEFAULT_DLC_LIST = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<CDataFileMgr__ContentsOfDataFileXml>\n"
    "  <Paths>\n"
    "    <Item>dlcpacks:/mpChristmas/</Item>\n"
    "  </Paths>\n"
    "</CDataFileMgr__ContentsOfDataFileXml>\n"
)


def write_minimal_update_rpf(
    path: Path, *, dlclist_xml: str = _DEFAULT_DLC_LIST
) -> Path:
    """Create ``path`` as an OPEN RPF with ``common/data/dlclist.xml``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = RpfArchive.empty("update.rpf")
    archive.encryption = OPEN_ENCRYPTION
    archive.add_file("common/data/dlclist.xml", dlclist_xml.encode("utf-8"))
    archive.save(str(path))
    return path

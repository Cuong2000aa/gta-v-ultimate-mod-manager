"""Tests for the tolerant XML reader and the meta-file repair routines."""

from __future__ import annotations

from pathlib import Path

import pytest

from gta_mod_manager.core.exceptions import ValidationError
from gta_mod_manager.utils import xml_tools

_VALID = '<?xml version="1.0" encoding="UTF-8"?>\n<Root><Item>value</Item></Root>'


def test_valid_documents_are_parsed_without_repairs() -> None:
    result = xml_tools.parse_xml_text(_VALID)

    assert not result.was_repaired
    assert xml_tools.find_text(result.root, "Item") == "value"


def test_repairing_removes_the_byte_order_mark_and_control_characters() -> None:
    text, repairs = xml_tools.repair_xml_text("\ufeff<Root>\x00<Item>v</Item></Root>")

    assert text.startswith("<Root>")
    assert any("byte order mark" in repair for repair in repairs)
    assert any("control characters" in repair for repair in repairs)


def test_a_document_with_a_bom_still_parses() -> None:
    result = xml_tools.parse_xml_text("\ufeff" + _VALID)

    assert xml_tools.find_text(result.root, "Item") == "value"


def test_bare_ampersands_are_escaped() -> None:
    result = xml_tools.parse_xml_text("<Root><Item>Smith & Wesson</Item></Root>")

    assert xml_tools.find_text(result.root, "Item") == "Smith & Wesson"
    assert any("ampersand" in repair for repair in result.repairs)


def test_trailing_junk_is_dropped() -> None:
    result = xml_tools.parse_xml_text("<Root><Item>v</Item></Root> installed by hand")

    assert xml_tools.find_text(result.root, "Item") == "v"
    assert result.was_repaired


def test_a_document_broken_beyond_repair_raises() -> None:
    with pytest.raises(ValidationError):
        xml_tools.parse_xml_text("<Root><Item>unclosed")


def test_read_text_handles_cp1252_bytes(tmp_path: Path) -> None:
    target = tmp_path / "vehicles.meta"
    target.write_bytes("<Root><Item>Fahrzeug \xe4\xf6\xfc</Item></Root>".encode("cp1252"))

    text = xml_tools.read_text(target)

    assert "Fahrzeug" in text


def test_load_and_save_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "handling.meta"
    source.write_text(_VALID, encoding="utf-8")

    loaded = xml_tools.load_xml(source)
    destination = tmp_path / "out.meta"
    xml_tools.save_xml(destination, loaded.root)

    assert xml_tools.find_text(xml_tools.load_xml(destination).root, "Item") == "value"


def test_iter_elements_is_case_insensitive() -> None:
    root = xml_tools.parse_xml_text("<Root><Item/><item/><Other/></Root>").root

    assert len(xml_tools.iter_elements(root, "item")) == 2


def test_find_attribute_returns_none_when_absent() -> None:
    root = xml_tools.parse_xml_text("<Root><Mass value='1800'/></Root>").root

    assert xml_tools.find_attribute(root, "Mass", "value") == "1800"
    assert xml_tools.find_attribute(root, "Mass", "unit") is None
    assert xml_tools.find_attribute(root, "Missing", "value") is None

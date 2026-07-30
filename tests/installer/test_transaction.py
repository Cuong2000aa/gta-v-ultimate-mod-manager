"""Tests for the journalled transaction that makes installs reversible."""

from __future__ import annotations

from pathlib import Path

import pytest

from gta_mod_manager.core.exceptions import RollbackError
from gta_mod_manager.installer.transaction import JournalEntry, Transaction
from gta_mod_manager.models.enums import FileAction


def test_rollback_deletes_files_that_were_created(tmp_path: Path) -> None:
    created = tmp_path / "game" / "new.dll"
    created.parent.mkdir()
    created.write_bytes(b"installed")

    with Transaction(scratch_dir=tmp_path / "scratch") as transaction:
        transaction.record(JournalEntry(action=FileAction.COPY, target=created))
        undone = transaction.rollback()

    assert undone == 1
    assert not created.exists()


def test_rollback_restores_files_that_were_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "game" / "config.ini"
    target.parent.mkdir()
    target.write_text("original", encoding="utf-8")

    with Transaction(scratch_dir=tmp_path / "scratch") as transaction:
        stash = transaction.stash_existing(target)
        target.write_text("modified", encoding="utf-8")
        transaction.record(
            JournalEntry(
                action=FileAction.OVERWRITE, target=target, replaced_backup=stash
            )
        )
        transaction.rollback()

    assert target.read_text(encoding="utf-8") == "original"


def test_rollback_removes_only_empty_directories(tmp_path: Path) -> None:
    empty = tmp_path / "game" / "empty"
    populated = tmp_path / "game" / "populated"
    empty.mkdir(parents=True)
    populated.mkdir(parents=True)
    (populated / "kept.txt").write_text("x", encoding="utf-8")

    with Transaction(scratch_dir=tmp_path / "scratch") as transaction:
        transaction.record(JournalEntry(action=FileAction.CREATE_DIRECTORY, target=empty))
        transaction.record(
            JournalEntry(action=FileAction.CREATE_DIRECTORY, target=populated)
        )
        undone = transaction.rollback()

    assert undone == 1
    assert not empty.exists()
    assert (populated / "kept.txt").exists()


def test_steps_are_undone_in_reverse_order(tmp_path: Path) -> None:
    root = tmp_path / "game" / "a" / "b"
    root.mkdir(parents=True)

    with Transaction(scratch_dir=tmp_path / "scratch") as transaction:
        transaction.record(
            JournalEntry(action=FileAction.CREATE_DIRECTORY, target=root.parent)
        )
        transaction.record(JournalEntry(action=FileAction.CREATE_DIRECTORY, target=root))
        transaction.rollback()

    assert not root.exists()
    assert not root.parent.exists()


def test_stashing_a_missing_file_returns_none(tmp_path: Path) -> None:
    with Transaction(scratch_dir=tmp_path / "scratch") as transaction:
        assert transaction.stash_existing(tmp_path / "absent.ini") is None


def test_commit_drops_the_scratch_folder(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    target = tmp_path / "config.ini"
    target.write_text("original", encoding="utf-8")

    with Transaction(scratch_dir=scratch) as transaction:
        transaction.stash_existing(target)
        transaction.commit()

    assert transaction.is_committed
    assert not scratch.exists()


def test_leaving_the_block_with_an_error_rolls_back(tmp_path: Path) -> None:
    created = tmp_path / "new.dll"
    created.write_bytes(b"installed")

    with pytest.raises(RuntimeError), Transaction(
        scratch_dir=tmp_path / "scratch"
    ) as transaction:
        transaction.record(JournalEntry(action=FileAction.COPY, target=created))
        raise RuntimeError("installation exploded")

    assert not created.exists()


def test_a_failing_undo_is_reported_but_the_rest_is_attempted(tmp_path: Path) -> None:
    first = tmp_path / "first.dll"
    second = tmp_path / "second.dll"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    missing_stash = tmp_path / "scratch" / "gone.bin"

    transaction = Transaction(scratch_dir=tmp_path / "scratch")
    transaction.record(JournalEntry(action=FileAction.COPY, target=first))
    transaction.record(
        JournalEntry(
            action=FileAction.OVERWRITE,
            target=tmp_path / "locked" / "deep" / "x.dll",
            replaced_backup=missing_stash,
        )
    )
    transaction.record(JournalEntry(action=FileAction.COPY, target=second))

    transaction.rollback()

    assert not first.exists()
    assert not second.exists()


def test_rollback_raises_when_a_step_truly_fails(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    target = tmp_path / "file.dll"
    target.write_bytes(b"x")

    def explode(_path: Path) -> bool:
        raise OSError("access denied")

    monkeypatch.setattr("gta_mod_manager.installer.transaction.fs.delete_file", explode)
    transaction = Transaction(scratch_dir=tmp_path / "scratch")
    transaction.record(JournalEntry(action=FileAction.COPY, target=target))

    with pytest.raises(RollbackError):
        transaction.rollback()

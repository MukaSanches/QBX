from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from qbx.api import inspect, pack, unpack
from qbx.core import QBXError, _safe_relpath


def _atomic_repack(
    archive: Path,
    source_root: Path,
    *,
    comment: str = "",
    repair_budget_pct: float = 5.0,
) -> dict:
    archive = archive.resolve()
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{archive.stem}-repack-",
        suffix=".qbx",
        dir=str(archive.parent),
    )
    os.close(fd)
    temp_archive = Path(temp_name)
    try:
        result = pack(
            source_root,
            temp_archive,
            profile="resilient",
            repair_budget_pct=repair_budget_pct,
            comment=comment,
        )
        os.replace(temp_archive, archive)
        result["archive"] = archive.stat().st_size
        return result
    except Exception:
        try:
            temp_archive.unlink()
        except FileNotFoundError:
            pass
        raise


def add_sources(
    archive: str | Path,
    sources: list[str | Path],
    *,
    overwrite_entries: bool = True,
    repair_budget_pct: float = 5.0,
) -> dict:
    archive = Path(archive)
    if not archive.exists():
        raise QBXError(f"Archive does not exist: {archive}")
    if not sources:
        raise QBXError("No sources selected")

    manifest = inspect(archive)
    comment = str(manifest.get("comment", ""))

    with tempfile.TemporaryDirectory(prefix="qbx-add-") as td:
        root = Path(td) / "content"
        unpack(archive, root, overwrite=False)

        for source_value in sources:
            source = Path(source_value)
            if not source.exists():
                raise QBXError(f"Source does not exist: {source}")
            target = root / source.name
            if source.is_dir():
                if target.exists() and not overwrite_entries:
                    raise QBXError(f"Entry already exists: {source.name}")
                shutil.copytree(source, target, dirs_exist_ok=overwrite_entries)
            elif source.is_file():
                if target.exists() and not overwrite_entries:
                    raise QBXError(f"Entry already exists: {source.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            else:
                raise QBXError(f"Unsupported source type: {source}")

        return _atomic_repack(
            archive,
            root,
            comment=comment,
            repair_budget_pct=repair_budget_pct,
        )


def delete_entries(
    archive: str | Path,
    entries: list[str],
    *,
    repair_budget_pct: float = 5.0,
) -> dict:
    archive = Path(archive)
    if not entries:
        raise QBXError("No archive entries selected")
    manifest = inspect(archive)
    comment = str(manifest.get("comment", ""))

    with tempfile.TemporaryDirectory(prefix="qbx-delete-") as td:
        root = Path(td) / "content"
        unpack(archive, root, overwrite=False)
        deleted = 0
        for entry in entries:
            rel = _safe_relpath(entry)
            target = root.joinpath(*rel.parts)
            if target.is_dir():
                shutil.rmtree(target)
                deleted += 1
            elif target.exists():
                target.unlink()
                deleted += 1
        if deleted == 0:
            raise QBXError("None of the selected entries exist in the archive")
        result = _atomic_repack(
            archive,
            root,
            comment=comment,
            repair_budget_pct=repair_budget_pct,
        )
        result["deleted_entries"] = deleted
        return result


def set_comment(
    archive: str | Path,
    comment: str,
    *,
    repair_budget_pct: float = 5.0,
) -> dict:
    archive = Path(archive)
    with tempfile.TemporaryDirectory(prefix="qbx-comment-") as td:
        root = Path(td) / "content"
        unpack(archive, root, overwrite=False)
        result = _atomic_repack(
            archive,
            root,
            comment=comment,
            repair_budget_pct=repair_budget_pct,
        )
        result["comment"] = comment
        return result

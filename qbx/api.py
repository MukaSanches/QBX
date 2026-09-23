from __future__ import annotations

from pathlib import Path

from qbx.core import QBXError
from qbx import core as v2
from qbx.resilient_v3 import (
    DEFAULT_REPAIR_BUDGET_PCT,
    MAGIC_V3,
    inspect_v3,
    pack_resilient,
    repair_v3,
    unpack_v3,
    verify_v3,
)


def _is_v3(path: str | Path) -> bool:
    p = Path(path)
    try:
        with p.open("rb") as f:
            return f.read(len(MAGIC_V3)) == MAGIC_V3
    except OSError as exc:
        raise QBXError(f"Cannot open archive: {p}") from exc


def pack(
    source: str | Path,
    output: str | Path,
    *,
    profile: str = "resilient",
    max_size_mb: float | None = None,
    max_decode_ms: float | None = None,
    repair_budget_pct: float = DEFAULT_REPAIR_BUDGET_PCT,
    comment: str | None = None,
) -> dict:
    if profile in {"resilient", "resilient-v3", "ark", "v3"}:
        return pack_resilient(
            source,
            output,
            max_size_mb=max_size_mb,
            max_decode_ms=max_decode_ms,
            repair_budget_pct=repair_budget_pct,
            comment=comment,
        )
    return v2.pack(
        source,
        output,
        profile=profile,
        max_size_mb=max_size_mb,
        max_decode_ms=max_decode_ms,
    )


def inspect(archive: str | Path) -> dict:
    return inspect_v3(archive) if _is_v3(archive) else v2.inspect(archive)


def verify(archive: str | Path) -> dict:
    return verify_v3(archive) if _is_v3(archive) else v2.verify(archive)


def unpack(
    archive: str | Path,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> dict:
    if _is_v3(archive):
        return unpack_v3(archive, destination, overwrite=overwrite)
    return v2.unpack(archive, destination, overwrite=overwrite)


def repair(
    archive: str | Path,
    output: str | Path,
    *,
    repair_budget_pct: float = DEFAULT_REPAIR_BUDGET_PCT,
) -> dict:
    if not _is_v3(archive):
        raise QBXError("Automatic repair requires a QBX V3 archive with an ARK repair lattice")
    return repair_v3(archive, output, repair_budget_pct=repair_budget_pct)

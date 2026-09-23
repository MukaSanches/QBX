from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterator, Sequence

import py7zr

from qbx.api import pack as pack_qbx, unpack as unpack_qbx
from qbx.core import QBXError


STANDARD_OUTPUTS = ("qbx", "zip", "7z", "rar")
ARCHIVE_SUFFIXES = {".qbx", ".zip", ".7z", ".rar"}


def _safe_member(name: str) -> PurePosixPath:
    value = name.replace("\\", "/")
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in {"", ".", ".."} for part in p.parts if part != "."):
        raise QBXError(f"Unsafe archive member path: {name}")
    if p.parts and ":" in p.parts[0]:
        raise QBXError(f"Unsafe archive member path: {name}")
    return p


def detect_container(path: str | Path) -> str | None:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".qbx":
        return "qbx"
    if zipfile.is_zipfile(p):
        return "zip"
    if suffix == ".7z":
        return "7z"
    if suffix == ".rar":
        return "rar"
    return None


def find_rar_executable() -> Path | None:
    configured = os.environ.get("QBX_RAR_EXE")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))

    for name in ("rar", "rar.exe", "WinRAR.exe", "winrar"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    if os.name == "nt":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env_name)
            if base:
                candidates.extend(
                    [
                        Path(base) / "WinRAR" / "rar.exe",
                        Path(base) / "WinRAR" / "WinRAR.exe",
                    ]
                )

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def output_capabilities() -> dict[str, dict]:
    rar = find_rar_executable()
    return {
        "qbx": {
            "available": True,
            "label": "QBX V3 — AGRP + ARK",
            "technology": "QBX full stack",
        },
        "zip": {
            "available": True,
            "label": "ZIP — compatibilidade máxima",
            "technology": "standard ZIP/Deflate",
        },
        "7z": {
            "available": True,
            "label": "7z — LZMA2",
            "technology": "standard 7z/LZMA2",
        },
        "rar": {
            "available": rar is not None,
            "label": (
                "RAR5 — melhor compressão padrão"
                if rar is not None
                else "RAR5 — requer WinRAR/RAR instalado"
            ),
            "technology": "standard RAR5 via installed RAR/WinRAR",
            "executable": str(rar) if rar else None,
        },
    }


def _extract_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as zf:
        members = zf.infolist()
        for info in members:
            rel = _safe_member(info.filename)
            # Reject Unix symlink entries instead of materializing links.
            mode = (info.external_attr >> 16) & 0xFFFF
            if (mode & 0o170000) == 0o120000:
                raise QBXError(f"ZIP symbolic links are not accepted: {info.filename}")

            target = destination.joinpath(*rel.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)


def _extract_7z(source: Path, destination: Path) -> None:
    with py7zr.SevenZipFile(source, mode="r") as archive:
        names = archive.getnames()
        for name in names:
            _safe_member(name)
        archive.extractall(path=destination)


def _rar_list(executable: Path, source: Path) -> list[str]:
    proc = subprocess.run(
        [str(executable), "lb", "-c-", str(source)],
        text=True,
        capture_output=True,
        errors="replace",
    )
    if proc.returncode != 0:
        raise QBXError(
            "RAR/WinRAR could not list the archive. "
            f"Exit code {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _extract_rar(source: Path, destination: Path) -> None:
    executable = find_rar_executable()
    if executable is None:
        raise QBXError(
            "RAR input requires RAR/WinRAR installed. "
            "Install WinRAR or point QBX_RAR_EXE to rar.exe/WinRAR.exe."
        )

    for name in _rar_list(executable, source):
        _safe_member(name)

    destination.mkdir(parents=True, exist_ok=True)
    dest_arg = str(destination.resolve()) + os.sep
    proc = subprocess.run(
        [str(executable), "x", "-o+", "-idq", str(source.resolve()), dest_arg],
        text=True,
        capture_output=True,
        errors="replace",
    )
    if proc.returncode != 0:
        raise QBXError(
            "RAR/WinRAR could not extract the archive. "
            f"Exit code {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )


def _extract_container(source: Path, destination: Path, kind: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if kind == "qbx":
        unpack_qbx(source, destination, overwrite=False)
    elif kind == "zip":
        _extract_zip(source, destination)
    elif kind == "7z":
        _extract_7z(source, destination)
    elif kind == "rar":
        _extract_rar(source, destination)
    else:
        raise QBXError(f"Unsupported source container: {kind}")


def _copy_source(source: Path, destination: Path) -> None:
    target = destination / source.name
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    elif source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    else:
        raise QBXError(f"Unsupported source type: {source}")


@contextlib.contextmanager
def prepared_logical_root(
    sources: Sequence[str | Path],
    *,
    optimize_source_archives: bool,
) -> Iterator[tuple[Path, dict]]:
    values = [Path(x).resolve() for x in sources]
    if not values:
        raise QBXError("No sources selected")
    for source in values:
        if not source.exists():
            raise QBXError(f"Source does not exist: {source}")

    # Preserve the intuitive "folder contents become archive root" behavior.
    if len(values) == 1 and values[0].is_dir():
        yield values[0], {
            "optimized_inputs": 0,
            "source_containers": [],
            "logical_transform": False,
        }
        return

    with tempfile.TemporaryDirectory(prefix="qbx-bridge-") as td:
        root = Path(td) / "logical"
        root.mkdir()
        optimized = 0
        container_types: list[str] = []

        for source in values:
            kind = detect_container(source) if source.is_file() else None
            if optimize_source_archives and kind is not None:
                container_types.append(kind)
                optimized += 1
                if len(values) == 1:
                    target = root
                else:
                    stem = source.name
                    for suffix in (".qbx", ".zip", ".7z", ".rar"):
                        if stem.lower().endswith(suffix):
                            stem = stem[: -len(suffix)]
                            break
                    target = root / (stem or "archive")
                _extract_container(source, target, kind)
            else:
                _copy_source(source, root)

        yield root, {
            "optimized_inputs": optimized,
            "source_containers": container_types,
            "logical_transform": optimized > 0,
        }


def _write_zip(root: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as zf:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if path.is_dir():
                if not any(path.iterdir()):
                    zf.writestr(rel.rstrip("/") + "/", b"")
            elif path.is_file():
                zf.write(path, rel)


def _write_7z(root: Path, output: Path) -> None:
    with py7zr.SevenZipFile(output, mode="w") as archive:
        for path in sorted(root.iterdir()):
            if path.is_dir():
                archive.writeall(path, arcname=path.name)
            elif path.is_file():
                archive.write(path, arcname=path.name)


def _write_rar(root: Path, output: Path) -> None:
    executable = find_rar_executable()
    if executable is None:
        raise QBXError(
            "Creating standard RAR5 requires an installed RAR/WinRAR executable. "
            "QBX does not bundle or reimplement the proprietary RAR encoder."
        )

    if output.exists():
        output.unlink()

    proc = subprocess.run(
        [
            str(executable),
            "a",
            "-r",
            "-m5",
            "-s",
            "-ma5",
            "-ep1",
            "-idq",
            str(output.resolve()),
            "*",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        errors="replace",
    )
    if proc.returncode != 0:
        raise QBXError(
            "RAR/WinRAR could not create the archive. "
            f"Exit code {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )


def create_archive(
    sources: Sequence[str | Path],
    output: str | Path,
    *,
    output_format: str,
    optimize_source_archives: bool = True,
    qbx_profile: str = "resilient",
    max_size_mb: float | None = None,
    max_decode_ms: float | None = None,
    repair_budget_pct: float = 5.0,
    comment: str | None = None,
) -> dict:
    fmt = output_format.lower().lstrip(".")
    if fmt not in STANDARD_OUTPUTS:
        raise QBXError(f"Unsupported output format: {output_format}")

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    expected_suffix = f".{fmt}"
    if output.suffix.lower() != expected_suffix:
        output = output.with_suffix(expected_suffix)

    with prepared_logical_root(
        sources,
        optimize_source_archives=optimize_source_archives,
    ) as (root, preparation):
        if fmt == "qbx":
            result = pack_qbx(
                root,
                output,
                profile=qbx_profile,
                max_size_mb=max_size_mb,
                max_decode_ms=max_decode_ms,
                repair_budget_pct=repair_budget_pct,
                comment=comment,
            )
            result.update(
                {
                    "output_format": "qbx",
                    "output": str(output),
                    "optimized_source_archives": preparation["optimized_inputs"],
                    "source_containers": preparation["source_containers"],
                    "logical_transform": preparation["logical_transform"],
                    "format_technology": "QBX CDC + dedup + multi-codec + AGRP + ARK",
                }
            )
            return result

        if output.exists():
            output.unlink()

        if fmt == "zip":
            _write_zip(root, output)
            technology = "standard ZIP/Deflate"
        elif fmt == "7z":
            _write_7z(root, output)
            technology = "standard 7z/LZMA2"
        else:
            _write_rar(root, output)
            technology = "standard RAR5 via installed RAR/WinRAR"

        size = output.stat().st_size
        return {
            "ok": True,
            "output_format": fmt,
            "output": str(output),
            "archive": size,
            "optimized_source_archives": preparation["optimized_inputs"],
            "source_containers": preparation["source_containers"],
            "logical_transform": preparation["logical_transform"],
            "format_technology": technology,
            "qbx_resilience_embedded": False,
            "note": (
                "Standard ZIP/7z/RAR outputs keep their native format. "
                "QBX AGRP/ARK metadata is only embedded in .qbx archives."
            ),
        }

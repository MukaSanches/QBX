from __future__ import annotations

import hashlib
import json
import lzma
import os
import stat
import struct
import tempfile
import time
import zlib
from collections import OrderedDict
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterator

import zstandard as zstd

MAGIC = b"QBX2\r\n\x1a\n"
FORMAT_VERSION = 2
HASH_NAME = "sha256"

MIN_CHUNK = 32 * 1024
TARGET_CHUNK = 128 * 1024
MAX_CHUNK = 512 * 1024
MASK = TARGET_CHUNK - 1
MAX_MANIFEST_BYTES = 64 * 1024 * 1024
MAX_STORED_BLOCK_BYTES = MAX_CHUNK * 3

U64 = struct.Struct(">Q")
BLOCK_META = struct.Struct(">BQQ")

CODEC_RAW = 0
CODEC_ZSTD = 1
CODEC_ZLIB = 2
CODEC_LZMA = 3

CODEC_NAMES = {
    CODEC_RAW: "raw",
    CODEC_ZSTD: "zstd",
    CODEC_ZLIB: "zlib",
    CODEC_LZMA: "lzma",
}

NAME_TO_CODEC = {v: k for k, v in CODEC_NAMES.items()}

GEAR = tuple(
    int.from_bytes(
        hashlib.sha256(f"QBX-GEAR-{i}".encode("ascii")).digest()[:8],
        "big",
    )
    for i in range(256)
)


class QBXError(Exception):
    """Raised for invalid, unsafe, unsupported, or corrupted QBX data."""


def digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def hexdigest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hexdigest(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _read_exact(f: BinaryIO, size: int, label: str) -> bytes:
    data = f.read(size)
    if len(data) != size:
        raise QBXError(f"Truncated QBX while reading {label}")
    return data


def _safe_relpath(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise QBXError("Invalid empty archive path")
    if "\x00" in value or "\\" in value:
        raise QBXError(f"Unsafe archive path: {value!r}")

    p = PurePosixPath(value)
    if p.is_absolute():
        raise QBXError(f"Unsafe absolute archive path: {value!r}")
    if not p.parts or any(part in ("", ".", "..") for part in p.parts):
        raise QBXError(f"Unsafe archive path: {value!r}")
    if ":" in p.parts[0]:
        raise QBXError(f"Unsafe drive-like archive path: {value!r}")
    return p


def _destination(root: Path, rel: str) -> Path:
    p = _safe_relpath(rel)
    root = root.resolve()
    target = root.joinpath(*p.parts).resolve()
    if target != root and root not in target.parents:
        raise QBXError(f"Archive path escapes destination: {rel}")
    return target


def chunks(data: bytes) -> Iterator[bytes]:
    """Content-defined chunking for in-memory data."""
    if not data:
        return

    start = 0
    rolling = 0
    for i, byte in enumerate(data):
        rolling = ((rolling << 1) + GEAR[byte]) & 0xFFFFFFFFFFFFFFFF
        size = i - start + 1
        if size >= MIN_CHUNK and ((rolling & MASK) == 0 or size >= MAX_CHUNK):
            yield data[start : i + 1]
            start = i + 1
            rolling = 0

    if start < len(data):
        yield data[start:]


def iter_file_chunks(path: Path, read_size: int = 1024 * 1024) -> Iterator[bytes]:
    """Bounded-memory content-defined chunking for files."""
    buf = bytearray()
    rolling = 0

    with path.open("rb") as f:
        while True:
            batch = f.read(read_size)
            if not batch:
                break

            for byte in batch:
                buf.append(byte)
                rolling = ((rolling << 1) + GEAR[byte]) & 0xFFFFFFFFFFFFFFFF
                size = len(buf)

                if size >= MIN_CHUNK and (
                    (rolling & MASK) == 0 or size >= MAX_CHUNK
                ):
                    yield bytes(buf)
                    buf.clear()
                    rolling = 0

    if buf:
        yield bytes(buf)


class CodecEngine:
    def __init__(self, profile: str = "balanced"):
        if profile not in {"fast", "balanced", "smallest"}:
            raise QBXError(f"Unknown compression profile: {profile}")
        self.profile = profile

    def _zstd_level(self) -> int:
        return {"fast": 3, "balanced": 8, "smallest": 19}[self.profile]

    def candidates(self, raw: bytes) -> list[tuple[int, bytes]]:
        candidates: list[tuple[int, bytes]] = [(CODEC_RAW, raw)]

        zc = zstd.ZstdCompressor(
            level=self._zstd_level(),
            threads=0,
            write_checksum=True,
            write_content_size=True,
            write_dict_id=False,
        )
        candidates.append((CODEC_ZSTD, zc.compress(raw)))

        if self.profile != "fast":
            zlevel = 6 if self.profile == "balanced" else 9
            candidates.append((CODEC_ZLIB, zlib.compress(raw, zlevel)))

            preset = 3 if self.profile == "balanced" else 6
            candidates.append((CODEC_LZMA, lzma.compress(raw, preset=preset)))

        return candidates

    def choose(self, raw: bytes) -> tuple[int, bytes]:
        options = self.candidates(raw)
        best_codec, best_payload = min(
            options,
            key=lambda item: (len(item[1]), item[0]),
        )

        # Avoid spending CPU/format complexity for negligible savings.
        if best_codec != CODEC_RAW and len(best_payload) >= len(raw) - 16:
            return CODEC_RAW, raw
        return best_codec, best_payload

    @staticmethod
    def decode(codec: int, payload: bytes, expected_size: int) -> bytes:
        try:
            if codec == CODEC_RAW:
                raw = payload
            elif codec == CODEC_ZSTD:
                raw = zstd.ZstdDecompressor().decompress(
                    payload,
                    max_output_size=max(expected_size, 1),
                )
            elif codec == CODEC_ZLIB:
                raw = zlib.decompress(payload)
            elif codec == CODEC_LZMA:
                raw = lzma.decompress(payload)
            else:
                raise QBXError(f"Unsupported QBX codec id: {codec}")
        except QBXError:
            raise
        except Exception as exc:
            name = CODEC_NAMES.get(codec, str(codec))
            raise QBXError(f"Failed to decode {name} block") from exc

        if len(raw) != expected_size:
            raise QBXError(
                f"Decoded block size mismatch: expected {expected_size}, "
                f"got {len(raw)}"
            )
        return raw


def decode(codec: str, payload: bytes) -> bytes:
    """Compatibility helper retained for early research code."""
    codec_id = NAME_TO_CODEC.get(codec)
    if codec_id is None:
        raise QBXError(f"Unsupported codec: {codec}")
    if codec_id == CODEC_RAW:
        return payload
    if codec_id == CODEC_ZSTD:
        return zstd.ZstdDecompressor().decompress(payload)
    if codec_id == CODEC_ZLIB:
        return zlib.decompress(payload)
    return lzma.decompress(payload)


def _collect(source: Path) -> tuple[Path, list[Path], list[str]]:
    source = source.resolve()

    if not source.exists():
        raise QBXError(f"Source does not exist: {source}")
    if source.is_symlink():
        raise QBXError("Symbolic links are not accepted as archive roots")

    if source.is_file():
        return source.parent, [source], []

    files: list[Path] = []
    directories: list[str] = []

    for p in sorted(source.rglob("*"), key=lambda x: x.as_posix()):
        if p.is_symlink():
            raise QBXError(f"Symbolic links are not supported: {p}")
        if p.is_dir():
            directories.append(p.relative_to(source).as_posix())
        elif p.is_file():
            files.append(p)
        else:
            raise QBXError(f"Unsupported filesystem object: {p}")

    return source, files, directories


def _validate_manifest(manifest: object) -> dict:
    if not isinstance(manifest, dict):
        raise QBXError("QBX manifest must be an object")
    if manifest.get("format") != "QBX":
        raise QBXError("Invalid QBX format identifier")
    if manifest.get("version") != FORMAT_VERSION:
        raise QBXError(
            f"Unsupported QBX version: {manifest.get('version')!r}; "
            f"expected {FORMAT_VERSION}"
        )

    files = manifest.get("files")
    directories = manifest.get("directories", [])
    stats = manifest.get("statistics")

    if not isinstance(files, list) or not isinstance(directories, list):
        raise QBXError("Malformed QBX manifest collections")
    if not isinstance(stats, dict):
        raise QBXError("Malformed QBX manifest statistics")

    seen_paths: set[str] = set()

    for rel in directories:
        if not isinstance(rel, str):
            raise QBXError("Directory path must be a string")
        _safe_relpath(rel)
        if rel in seen_paths:
            raise QBXError(f"Duplicate archive path: {rel}")
        seen_paths.add(rel)

    for entry in files:
        if not isinstance(entry, dict):
            raise QBXError("Malformed file entry")
        rel = entry.get("path")
        if not isinstance(rel, str):
            raise QBXError("File path must be a string")
        _safe_relpath(rel)
        if rel in seen_paths:
            raise QBXError(f"Duplicate archive path: {rel}")
        seen_paths.add(rel)

        size = entry.get("size")
        file_hash = entry.get("sha256")
        refs = entry.get("blocks")

        if not isinstance(size, int) or size < 0:
            raise QBXError(f"Invalid file size for {rel}")
        if (
            not isinstance(file_hash, str)
            or len(file_hash) != 64
            or any(c not in "0123456789abcdef" for c in file_hash)
        ):
            raise QBXError(f"Invalid SHA-256 for {rel}")
        if not isinstance(refs, list):
            raise QBXError(f"Invalid block list for {rel}")

        for ref in refs:
            if (
                not isinstance(ref, str)
                or len(ref) != 64
                or any(c not in "0123456789abcdef" for c in ref)
            ):
                raise QBXError(f"Invalid block reference in {rel}")

    unique_blocks = stats.get("unique_blocks")
    if not isinstance(unique_blocks, int) or unique_blocks < 0:
        raise QBXError("Invalid unique block count")

    return manifest


def pack(
    source: str | Path,
    output: str | Path,
    *,
    profile: str = "balanced",
    max_size_mb: float | None = None,
    max_decode_ms: float | None = None,
) -> dict:
    if profile in {"adaptive", "adaptive-v2"}:
        from qbx.adaptive_v2 import pack_adaptive

        return pack_adaptive(
            source,
            output,
            max_size_mb=max_size_mb,
            max_decode_ms=max_decode_ms,
        )

    started = time.perf_counter()
    source = Path(source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    root, files, directories = _collect(source)
    engine = CodecEngine(profile)

    file_entries: list[dict] = []
    block_meta: dict[str, dict] = {}
    total_input = 0
    logical_chunks = 0

    with tempfile.TemporaryDirectory(
        prefix="qbx-blocks-",
        dir=str(output.parent.resolve()),
    ) as tmp:
        block_dir = Path(tmp)

        for path in files:
            rel = path.relative_to(root).as_posix()
            _safe_relpath(rel)

            refs: list[str] = []
            file_hash = hashlib.sha256()
            file_size = 0

            for raw in iter_file_chunks(path):
                logical_chunks += 1
                file_hash.update(raw)
                file_size += len(raw)

                block_hash = hexdigest(raw)
                refs.append(block_hash)

                if block_hash in block_meta:
                    continue

                codec, payload = engine.choose(raw)
                payload_path = block_dir / block_hash
                payload_path.write_bytes(payload)

                block_meta[block_hash] = {
                    "codec": codec,
                    "raw_size": len(raw),
                    "stored_size": len(payload),
                    "path": payload_path,
                }

            total_input += file_size

            file_entries.append(
                {
                    "path": rel,
                    "size": file_size,
                    "sha256": file_hash.hexdigest(),
                    "blocks": refs,
                    "mode": stat.S_IMODE(path.stat().st_mode),
                }
            )

        manifest = {
            "format": "QBX",
            "version": FORMAT_VERSION,
            "hash": HASH_NAME,
            "compression_profile": profile,
            "chunking": {
                "algorithm": "gear-content-defined",
                "min": MIN_CHUNK,
                "target": TARGET_CHUNK,
                "max": MAX_CHUNK,
            },
            "features": [
                "content-defined-chunking",
                "global-deduplication",
                "adaptive-codec-selection",
                "bounded-memory-file-chunking",
                "sha256-block-integrity",
                "sha256-file-integrity",
                "safe-path-extraction",
                "deterministic-layout",
            ],
            "directories": directories,
            "files": file_entries,
            "statistics": {
                "input_bytes": total_input,
                "file_count": len(file_entries),
                "directory_count": len(directories),
                "chunk_references": logical_chunks,
                "unique_blocks": len(block_meta),
            },
        }

        manifest_bytes = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        if len(manifest_bytes) > MAX_MANIFEST_BYTES:
            raise QBXError("QBX manifest exceeds safety limit")

        fd, temp_name = tempfile.mkstemp(
            prefix=".qbx-write-",
            suffix=".tmp",
            dir=str(output.parent.resolve()),
        )

        try:
            with os.fdopen(fd, "wb") as out:
                out.write(MAGIC)
                out.write(U64.pack(len(manifest_bytes)))
                out.write(manifest_bytes)

                ordered = sorted(block_meta)
                out.write(U64.pack(len(ordered)))

                for block_hash in ordered:
                    meta = block_meta[block_hash]
                    payload = Path(meta["path"]).read_bytes()

                    if len(payload) != meta["stored_size"]:
                        raise QBXError("Temporary block changed during archive build")

                    out.write(bytes.fromhex(block_hash))
                    out.write(
                        BLOCK_META.pack(
                            meta["codec"],
                            meta["raw_size"],
                            meta["stored_size"],
                        )
                    )
                    out.write(payload)

                out.flush()
                os.fsync(out.fileno())

            os.replace(temp_name, output)

        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    archive_size = output.stat().st_size
    elapsed = time.perf_counter() - started

    return {
        "format_version": FORMAT_VERSION,
        "profile": profile,
        "files": len(file_entries),
        "directories": len(directories),
        "original": total_input,
        "archive": archive_size,
        "ratio": archive_size / total_input if total_input else 0.0,
        "logical_chunks": logical_chunks,
        "unique_chunks": len(block_meta),
        "deduplicated_chunks": logical_chunks - len(block_meta),
        "seconds": elapsed,
        "archive_sha256": file_hexdigest(output),
    }


def _open_manifest(archive: Path) -> tuple[BinaryIO, dict]:
    f = archive.open("rb")
    try:
        magic = _read_exact(f, len(MAGIC), "magic")
        if magic != MAGIC:
            raise QBXError("Invalid QBX magic")

        manifest_len = U64.unpack(_read_exact(f, 8, "manifest length"))[0]
        if manifest_len > MAX_MANIFEST_BYTES:
            raise QBXError("QBX manifest exceeds safety limit")

        raw = _read_exact(f, manifest_len, "manifest")
        try:
            manifest = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise QBXError("Invalid QBX manifest JSON") from exc

        return f, _validate_manifest(manifest)
    except Exception:
        f.close()
        raise


def _scan_index(f: BinaryIO, manifest: dict) -> dict[str, tuple[int, int, int, int]]:
    count = U64.unpack(_read_exact(f, 8, "block count"))[0]
    expected = manifest["statistics"]["unique_blocks"]
    if count != expected:
        raise QBXError(
            f"Block count mismatch: header={count}, manifest={expected}"
        )

    index: dict[str, tuple[int, int, int, int]] = {}

    for _ in range(count):
        raw_digest = _read_exact(f, 32, "block digest")
        block_hash = raw_digest.hex()
        codec, raw_size, stored_size = BLOCK_META.unpack(
            _read_exact(f, BLOCK_META.size, "block metadata")
        )

        if codec not in CODEC_NAMES:
            raise QBXError(f"Unknown codec id {codec}")
        if raw_size <= 0 or raw_size > MAX_CHUNK:
            raise QBXError(f"Invalid raw block size: {raw_size}")
        if stored_size <= 0 or stored_size > MAX_STORED_BLOCK_BYTES:
            raise QBXError(f"Invalid stored block size: {stored_size}")
        if block_hash in index:
            raise QBXError(f"Duplicate block record: {block_hash}")

        offset = f.tell()
        _read_exact(f, stored_size, "block payload")
        index[block_hash] = (offset, codec, raw_size, stored_size)

    if f.read(1):
        raise QBXError("Unexpected trailing data after QBX blocks")

    return index


def inspect(archive: str | Path) -> dict:
    f, manifest = _open_manifest(Path(archive))
    try:
        return manifest
    finally:
        f.close()


def _block_loader(
    f: BinaryIO,
    index: dict[str, tuple[int, int, int, int]],
    *,
    cache_limit: int = 32,
):
    cache: OrderedDict[str, bytes] = OrderedDict()

    def load(block_hash: str) -> bytes:
        cached = cache.get(block_hash)
        if cached is not None:
            cache.move_to_end(block_hash)
            return cached

        try:
            offset, codec, raw_size, stored_size = index[block_hash]
        except KeyError as exc:
            raise QBXError(f"Missing block referenced by file: {block_hash}") from exc

        f.seek(offset)
        payload = _read_exact(f, stored_size, "indexed block payload")
        raw = CodecEngine.decode(codec, payload, raw_size)

        if hexdigest(raw) != block_hash:
            raise QBXError(f"Block SHA-256 mismatch: {block_hash}")

        cache[block_hash] = raw
        cache.move_to_end(block_hash)
        while len(cache) > cache_limit:
            cache.popitem(last=False)

        return raw

    return load


def verify(archive: str | Path) -> dict:
    started = time.perf_counter()
    archive = Path(archive)

    f, manifest = _open_manifest(archive)
    try:
        index = _scan_index(f, manifest)
        load = _block_loader(f, index)

        for block_hash in index:
            load(block_hash)

        for entry in manifest["files"]:
            h = hashlib.sha256()
            size = 0
            for block_hash in entry["blocks"]:
                raw = load(block_hash)
                h.update(raw)
                size += len(raw)

            if size != entry["size"]:
                raise QBXError(f"File size mismatch: {entry['path']}")
            if h.hexdigest() != entry["sha256"]:
                raise QBXError(f"File SHA-256 mismatch: {entry['path']}")

        return {
            "ok": True,
            "format_version": FORMAT_VERSION,
            "files": len(manifest["files"]),
            "blocks": len(index),
            "archive_sha256": file_hexdigest(archive),
            "seconds": time.perf_counter() - started,
        }
    finally:
        f.close()


def unpack(
    archive: str | Path,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> dict:
    started = time.perf_counter()
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)

    f, manifest = _open_manifest(Path(archive))
    try:
        index = _scan_index(f, manifest)
        load = _block_loader(f, index)

        for rel in manifest.get("directories", []):
            _destination(destination, rel).mkdir(parents=True, exist_ok=True)

        written = 0

        for entry in manifest["files"]:
            target = _destination(destination, entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.exists() and not overwrite:
                raise QBXError(
                    f"Refusing to overwrite existing path: {target}. "
                    "Use overwrite=True or --overwrite."
                )

            fd, temp_name = tempfile.mkstemp(
                prefix=".qbx-extract-",
                dir=str(target.parent),
            )

            try:
                h = hashlib.sha256()
                size = 0

                with os.fdopen(fd, "wb") as out:
                    for block_hash in entry["blocks"]:
                        raw = load(block_hash)
                        out.write(raw)
                        h.update(raw)
                        size += len(raw)

                    out.flush()
                    os.fsync(out.fileno())

                if size != entry["size"]:
                    raise QBXError(
                        f"Reconstructed size mismatch: {entry['path']}"
                    )
                if h.hexdigest() != entry["sha256"]:
                    raise QBXError(
                        f"Reconstructed SHA-256 mismatch: {entry['path']}"
                    )

                os.replace(temp_name, target)
                try:
                    os.chmod(target, int(entry.get("mode", 0o644)))
                except OSError:
                    pass
                written += size

            except Exception:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
                raise

        return {
            "ok": True,
            "format_version": FORMAT_VERSION,
            "files": len(manifest["files"]),
            "bytes": written,
            "seconds": time.perf_counter() - started,
        }
    finally:
        f.close()

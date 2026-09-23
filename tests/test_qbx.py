import hashlib
import json
import random
import struct

import pytest

from qbx.core import (
    MAGIC,
    FORMAT_VERSION,
    QBXError,
    hexdigest,
    inspect,
    pack,
    unpack,
    verify,
)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_roundtrip_and_verify(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    nested = src / "nested"
    nested.mkdir()
    (src / "empty-dir").mkdir()

    repeated = (b"QBX" * 100000) + (b"A" * 200000)
    (src / "a.bin").write_bytes(repeated)
    (src / "b.bin").write_bytes(repeated)
    (nested / "empty.bin").write_bytes(b"")

    rng = random.Random(20260923)
    (nested / "random.bin").write_bytes(rng.randbytes(350000))

    archive = tmp_path / "x.qbx"
    dst = tmp_path / "dst"

    stats = pack(src, archive, profile="balanced")
    checked = verify(archive)
    restored = unpack(archive, dst)

    assert checked["ok"] is True
    assert restored["ok"] is True
    assert stats["deduplicated_chunks"] > 0
    assert (dst / "empty-dir").is_dir()

    for original in src.rglob("*"):
        if original.is_file():
            copy = dst / original.relative_to(src)
            assert copy.exists()
            assert file_hash(original) == file_hash(copy)


def test_profiles_roundtrip(tmp_path):
    src = tmp_path / "data.bin"
    src.write_bytes((bytes(range(256)) * 1000) + b"Z" * 200000)

    for profile in ("fast", "balanced", "smallest"):
        archive = tmp_path / f"{profile}.qbx"
        out = tmp_path / f"out-{profile}"

        result = pack(src, archive, profile=profile)
        assert result["profile"] == profile
        assert verify(archive)["ok"] is True
        unpack(archive, out)
        assert file_hash(src) == file_hash(out / src.name)


def test_deterministic_archive(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.txt").write_bytes(b"deterministic-qbx\n" * 10000)

    a = tmp_path / "a.qbx"
    b = tmp_path / "b.qbx"

    pack(src, a, profile="balanced")
    pack(src, b, profile="balanced")

    assert a.read_bytes() == b.read_bytes()


def test_corruption_is_detected(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "data.bin").write_bytes(b"CORRUPTION-CHECK" * 50000)

    archive = tmp_path / "bad.qbx"
    pack(src, archive)

    raw = bytearray(archive.read_bytes())
    raw[-1] ^= 0xFF
    archive.write_bytes(raw)

    with pytest.raises(QBXError):
        verify(archive)


def test_unpack_refuses_overwrite_by_default(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "file.txt").write_text("original")

    archive = tmp_path / "x.qbx"
    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "file.txt").write_text("do not replace")

    pack(src, archive)

    with pytest.raises(QBXError, match="Refusing to overwrite"):
        unpack(archive, dst)

    unpack(archive, dst, overwrite=True)
    assert (dst / "file.txt").read_text() == "original"


def test_manifest_rejects_path_traversal(tmp_path):
    archive = tmp_path / "unsafe.qbx"
    manifest = {
        "format": "QBX",
        "version": FORMAT_VERSION,
        "hash": "sha256",
        "compression_profile": "balanced",
        "chunking": {},
        "features": [],
        "directories": [],
        "files": [
            {
                "path": "../escape.txt",
                "size": 0,
                "sha256": hexdigest(b""),
                "blocks": [],
                "mode": 0o644,
            }
        ],
        "statistics": {
            "input_bytes": 0,
            "file_count": 1,
            "directory_count": 0,
            "chunk_references": 0,
            "unique_blocks": 0,
        },
    }
    raw = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    with archive.open("wb") as f:
        f.write(MAGIC)
        f.write(struct.pack(">Q", len(raw)))
        f.write(raw)
        f.write(struct.pack(">Q", 0))

    with pytest.raises(QBXError, match="Unsafe archive path"):
        inspect(archive)


def test_invalid_magic(tmp_path):
    archive = tmp_path / "nope.qbx"
    archive.write_bytes(b"not-a-qbx")

    with pytest.raises(QBXError):
        verify(archive)

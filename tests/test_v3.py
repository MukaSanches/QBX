import hashlib
import random
from pathlib import Path

from qbx.api import inspect, pack, repair, unpack, verify
from qbx.core import pack as pack_v2
from qbx.resilient_v3 import record_index_v3


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_correlated_corpus(root: Path) -> None:
    root.mkdir()
    rng = random.Random(20260923)
    base = bytearray(rng.randbytes(16 * 1024))
    for i in range(7):
        value = bytearray(base)
        for j in range(18 + i * 5):
            pos = (i * 911 + j * 353) % len(value)
            value[pos] ^= ((i + 1) * (j + 3)) & 0xFF or 1
        (root / f"version-{i}.bin").write_bytes(bytes(value))
    text = b"QBX V3 repeated text\n" * 6000
    (root / "notes.txt").write_bytes(text)
    (root / "notes-copy.txt").write_bytes(text)


def assert_tree_equal(a: Path, b: Path) -> None:
    for original in sorted(p for p in a.rglob("*") if p.is_file()):
        copy = b / original.relative_to(a)
        assert copy.exists()
        assert file_hash(original) == file_hash(copy)


def test_v3_roundtrip_manifest_and_ark(tmp_path):
    src = tmp_path / "src"
    build_correlated_corpus(src)
    archive = tmp_path / "v3.qbx"
    restored = tmp_path / "restored"

    result = pack(src, archive, profile="resilient", repair_budget_pct=8.0, comment="v3-test")
    manifest = inspect(archive)
    checked = verify(archive)
    unpack(archive, restored)

    assert result["format_version"] == 3
    assert result["planner"] == "AGRP+ARK"
    assert manifest["version"] == 3
    assert manifest["product_version"] == "3.0.0"
    assert manifest["planner"]["name"] == "AGRP+ARK"
    assert manifest["comment"] == "v3-test"
    assert manifest["statistics"]["repair_edges"] > 0
    assert checked["ok"] is True
    assert checked["healthy"] is True
    assert_tree_equal(src, restored)


def test_v3_recovers_corrupted_primary_record(tmp_path):
    src = tmp_path / "src"
    build_correlated_corpus(src)
    archive = tmp_path / "recoverable.qbx"
    pack(src, archive, profile="resilient", repair_budget_pct=10.0)

    manifest, index = record_index_v3(archive)
    assert manifest["repair_edges"]
    protected_hash = manifest["repair_edges"][0]["a"]
    offset, _codec, _raw_size, stored_size = index[protected_hash]
    assert stored_size > 4

    raw = bytearray(archive.read_bytes())
    raw[offset + stored_size // 2] ^= 0x5A
    archive.write_bytes(raw)

    checked = verify(archive)
    assert checked["ok"] is True
    assert checked["degraded"] is True
    assert checked["recovered_blocks"] >= 1

    restored = tmp_path / "restored"
    unpack(archive, restored)
    assert_tree_equal(src, restored)

    repaired = tmp_path / "repaired.qbx"
    result = repair(archive, repaired, repair_budget_pct=10.0)
    assert result["ok"] is True
    clean = verify(repaired)
    assert clean["ok"] is True
    assert clean["healthy"] is True


def test_api_reads_v2_archives(tmp_path):
    source = tmp_path / "legacy.txt"
    source.write_bytes(b"QBX V2 compatibility\n" * 5000)
    archive = tmp_path / "legacy.qbx"
    restored = tmp_path / "legacy-out"

    pack_v2(source, archive, profile="balanced")
    manifest = inspect(archive)
    assert manifest["version"] == 2
    assert verify(archive)["ok"] is True
    unpack(archive, restored)
    assert file_hash(source) == file_hash(restored / source.name)

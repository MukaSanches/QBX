from __future__ import annotations

import hashlib
import json
import random
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from qbx.api import inspect, pack, unpack, verify
from qbx.core import pack as pack_v2, unpack as unpack_v2, verify as verify_v2
from qbx.resilient_v3 import record_index_v3

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks" / "results" / "v3_latest.json"


def build_dataset(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260923)

    base = bytearray(rng.randbytes(16 * 1024))
    for i in range(14):
        value = bytearray(base)
        for j in range(18 + i * 4):
            pos = (i * 977 + j * 409) % len(value)
            value[pos] ^= ((i + 3) * (j + 5)) & 0xFF or 1
        (root / f"revision-{i:02d}.bin").write_bytes(bytes(value))

    text = b"QBX V3 benchmark text: AGRP + ARK\n" * 40000
    (root / "text.txt").write_bytes(text)
    (root / "text-copy.txt").write_bytes(text)
    (root / "pattern.bin").write_bytes(bytes(range(256)) * 4000)
    random_data = rng.randbytes(1_000_000)
    (root / "random.bin").write_bytes(random_data)
    (root / "random-copy.bin").write_bytes(random_data)


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(path.relative_to(root).as_posix().encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()


def total_size(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="qbx-v3-benchmark-") as td:
        base = Path(td)
        src = base / "dataset"
        build_dataset(src)
        expected = tree_hash(src)
        original = total_size(src)

        report: dict = {
            "benchmark": "QBX V3 product benchmark",
            "dataset_bytes": original,
            "dataset_sha256": expected,
            "profiles": {},
            "recovery": {},
        }

        archive_v2 = base / "v2-adaptive.qbx"
        out_v2 = base / "out-v2"
        t0 = time.perf_counter()
        v2_result = pack_v2(src, archive_v2, profile="adaptive")
        v2_pack = time.perf_counter() - t0
        verify_v2(archive_v2)
        t0 = time.perf_counter()
        unpack_v2(archive_v2, out_v2)
        v2_unpack = time.perf_counter() - t0
        if tree_hash(out_v2) != expected:
            raise RuntimeError("QBX V2 round-trip mismatch")
        report["profiles"]["qbx_v2_adaptive"] = {
            "archive_bytes": archive_v2.stat().st_size,
            "ratio": archive_v2.stat().st_size / original,
            "pack_seconds": v2_pack,
            "unpack_seconds": v2_unpack,
            "planner": v2_result.get("planner"),
        }

        archive_v3 = base / "v3-resilient.qbx"
        out_v3 = base / "out-v3"
        t0 = time.perf_counter()
        v3_result = pack(src, archive_v3, profile="resilient", repair_budget_pct=8.0)
        v3_pack = time.perf_counter() - t0
        clean_check = verify(archive_v3)
        t0 = time.perf_counter()
        unpack(archive_v3, out_v3)
        v3_unpack = time.perf_counter() - t0
        if tree_hash(out_v3) != expected:
            raise RuntimeError("QBX V3 round-trip mismatch")
        manifest = inspect(archive_v3)
        report["profiles"]["qbx_v3_resilient"] = {
            "archive_bytes": archive_v3.stat().st_size,
            "ratio": archive_v3.stat().st_size / original,
            "pack_seconds": v3_pack,
            "unpack_seconds": v3_unpack,
            "planner": v3_result.get("planner"),
            "repair_edges": v3_result.get("repair_edges"),
            "protected_blocks": v3_result.get("protected_blocks"),
            "repair_payload_bytes": v3_result.get("repair_payload_bytes"),
            "repair_overhead_pct": v3_result.get("repair_overhead_pct"),
            "ark_search_examined": v3_result.get("ark_search_examined"),
            "ark_search_feasible": v3_result.get("ark_search_feasible"),
            "healthy": clean_check.get("healthy"),
        }

        zip_path = base / "baseline.zip"
        t0 = time.perf_counter()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for path in sorted(p for p in src.rglob("*") if p.is_file()):
                zf.write(path, path.relative_to(src))
        zip_pack = time.perf_counter() - t0
        zip_out = base / "zip-out"
        t0 = time.perf_counter()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(zip_out)
        zip_unpack = time.perf_counter() - t0
        if tree_hash(zip_out) != expected:
            raise RuntimeError("ZIP round-trip mismatch")
        report["profiles"]["zip_deflate_9"] = {
            "archive_bytes": zip_path.stat().st_size,
            "ratio": zip_path.stat().st_size / original,
            "pack_seconds": zip_pack,
            "unpack_seconds": zip_unpack,
        }

        if not manifest.get("repair_edges"):
            raise RuntimeError("V3 benchmark produced no ARK repair edges")
        damaged = base / "v3-damaged.qbx"
        shutil.copy2(archive_v3, damaged)
        damaged_manifest, index = record_index_v3(damaged)
        protected_hash = damaged_manifest["repair_edges"][0]["a"]
        offset, _codec, _raw_size, stored_size = index[protected_hash]
        raw = bytearray(damaged.read_bytes())
        raw[offset + max(1, stored_size // 2)] ^= 0xA5
        damaged.write_bytes(raw)

        t0 = time.perf_counter()
        recovered_check = verify(damaged)
        recovery_seconds = time.perf_counter() - t0
        recovered_out = base / "recovered-out"
        unpack(damaged, recovered_out)
        recovered_tree_hash = tree_hash(recovered_out)
        if recovered_tree_hash != expected:
            raise RuntimeError("ARK recovery produced mismatched data")

        report["recovery"] = {
            "damaged_primary_hash": protected_hash,
            "verify_ok": recovered_check.get("ok"),
            "degraded": recovered_check.get("degraded"),
            "damaged_records": recovered_check.get("damaged_records"),
            "recovered_blocks": recovered_check.get("recovered_blocks"),
            "recovery_seconds": recovery_seconds,
            "tree_sha256_match": recovered_tree_hash == expected,
        }

        report["gate"] = bool(
            report["recovery"]["verify_ok"]
            and report["recovery"]["recovered_blocks"]
            and report["recovery"]["tree_sha256_match"]
            and manifest["version"] == 3
            and manifest["planner"]["name"] == "AGRP+ARK"
        )

        OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        print(f"Report: {OUTPUT}")
        if not report["gate"]:
            raise SystemExit(2)
        print("QBX V3 PRODUCT BENCHMARK GATE: PASS")


if __name__ == "__main__":
    main()

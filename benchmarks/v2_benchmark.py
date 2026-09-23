from __future__ import annotations

import hashlib
import json
import random
import tempfile
import time
import zipfile
from pathlib import Path

from qbx.core import pack, unpack, verify


def build_dataset(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260923)
    text = b"QBX 2.0 benchmark dataset\n" * 50000
    random_data = rng.randbytes(1_000_000)
    (root / "text.txt").write_bytes(text)
    (root / "text-copy.txt").write_bytes(text)
    (root / "pattern.bin").write_bytes(bytes(range(256)) * 4000)
    (root / "random.bin").write_bytes(random_data)
    (root / "random-copy.bin").write_bytes(random_data)


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(path.relative_to(root).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def total_size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="qbx-v2-bench-") as td:
        base = Path(td)
        src = base / "dataset"
        build_dataset(src)
        expected_hash = tree_hash(src)
        original = total_size(src)
        report = {
            "dataset_bytes": original,
            "dataset_sha256": expected_hash,
            "qbx": {},
        }

        for profile in ("balanced", "smallest", "adaptive"):
            archive = base / f"{profile}.qbx"
            restored = base / f"restored-{profile}"

            t0 = time.perf_counter()
            packed = pack(src, archive, profile=profile)
            pack_seconds = time.perf_counter() - t0

            verify(archive)

            t0 = time.perf_counter()
            unpack(archive, restored)
            unpack_seconds = time.perf_counter() - t0

            if tree_hash(restored) != expected_hash:
                raise RuntimeError(f"{profile} round trip mismatch")

            report["qbx"][profile] = {
                "archive_bytes": archive.stat().st_size,
                "ratio": archive.stat().st_size / original,
                "pack_seconds": pack_seconds,
                "unpack_seconds": unpack_seconds,
                "planner": packed.get("planner"),
                "estimated_decode_improvement_pct": packed.get(
                    "estimated_decode_improvement_pct"
                ),
            }

        zip_path = base / "baseline.zip"
        t0 = time.perf_counter()
        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as zf:
            for path in sorted(p for p in src.rglob("*") if p.is_file()):
                zf.write(path, path.relative_to(src))
        zip_pack_seconds = time.perf_counter() - t0

        zip_out = base / "zip-out"
        t0 = time.perf_counter()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(zip_out)
        zip_unpack_seconds = time.perf_counter() - t0

        report["zip_deflate_9"] = {
            "archive_bytes": zip_path.stat().st_size,
            "ratio": zip_path.stat().st_size / original,
            "pack_seconds": zip_pack_seconds,
            "unpack_seconds": zip_unpack_seconds,
        }

        out = Path("benchmarks/results/v2_latest.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

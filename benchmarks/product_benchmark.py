from __future__ import annotations

import json
import random
import tempfile
import time
import zipfile
from pathlib import Path

from qbx.core import pack, unpack, verify


def dataset(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260923)

    (root / "text.txt").write_bytes(
        b"QBX adaptive archive product benchmark\n" * 120000
    )
    (root / "pattern.bin").write_bytes(bytes(range(256)) * 20000)

    random_data = rng.randbytes(2_000_000)
    (root / "random.bin").write_bytes(random_data)
    (root / "random-copy.bin").write_bytes(random_data)


def tree_size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="qbx-benchmark-") as td:
        td = Path(td)
        src = td / "dataset"
        dataset(src)
        original = tree_size(src)

        report = {"dataset_bytes": original, "qbx": {}, "zip_deflate_9": {}}

        for profile in ("fast", "balanced", "smallest"):
            archive = td / f"{profile}.qbx"
            restored = td / f"restored-{profile}"

            t0 = time.perf_counter()
            packed = pack(src, archive, profile=profile)
            pack_time = time.perf_counter() - t0

            verified = verify(archive)

            t0 = time.perf_counter()
            unpack(archive, restored)
            unpack_time = time.perf_counter() - t0

            report["qbx"][profile] = {
                "bytes": archive.stat().st_size,
                "ratio": archive.stat().st_size / original,
                "pack_seconds": pack_time,
                "unpack_seconds": unpack_time,
                "deduplicated_chunks": packed["deduplicated_chunks"],
                "verified": verified["ok"],
            }

        zip_path = td / "baseline.zip"

        t0 = time.perf_counter()
        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as zf:
            for path in sorted(src.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(src))
        zip_pack = time.perf_counter() - t0

        zip_out = td / "zip-out"
        t0 = time.perf_counter()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(zip_out)
        zip_unpack = time.perf_counter() - t0

        report["zip_deflate_9"] = {
            "bytes": zip_path.stat().st_size,
            "ratio": zip_path.stat().st_size / original,
            "pack_seconds": zip_pack,
            "unpack_seconds": zip_unpack,
        }

        out = Path("benchmarks/product_benchmark_latest.json")
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

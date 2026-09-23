from __future__ import annotations

import hashlib
import json
import random
import tempfile
import time
import zipfile
from pathlib import Path

from qbx.api import pack as pack_qbx, unpack as unpack_qbx
from qbx.bridge import create_archive

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks" / "results" / "v3_2_bridge.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260923)

    with tempfile.TemporaryDirectory(prefix="qbx-bridge-bench-") as td:
        root = Path(td)
        source_zip = root / "nested-source.zip"

        repeated_random = rng.randbytes(768 * 1024)
        text = (b"QBX 3.2 universal bridge benchmark\n" * 30000)

        with zipfile.ZipFile(
            source_zip,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as zf:
            zf.writestr("random-A.bin", repeated_random)
            zf.writestr("random-B.bin", repeated_random)
            zf.writestr("text-A.txt", text)
            zf.writestr("text-B.txt", text)

        direct = root / "direct.qbx"
        optimized = root / "optimized.qbx"

        t0 = time.perf_counter()
        direct_result = pack_qbx(
            source_zip,
            direct,
            profile="resilient",
            repair_budget_pct=0.0,
        )
        direct_seconds = time.perf_counter() - t0

        t0 = time.perf_counter()
        optimized_result = create_archive(
            [source_zip],
            optimized,
            output_format="qbx",
            optimize_source_archives=True,
            qbx_profile="resilient",
            repair_budget_pct=5.0,
        )
        optimized_seconds = time.perf_counter() - t0

        restored = root / "restored"
        unpack_qbx(optimized, restored)

        logical_ok = (
            (restored / "random-A.bin").read_bytes() == repeated_random
            and (restored / "random-B.bin").read_bytes() == repeated_random
            and (restored / "text-A.txt").read_bytes() == text
            and (restored / "text-B.txt").read_bytes() == text
        )

        output_7z = root / "optimized.7z"
        seven = create_archive(
            [source_zip],
            output_7z,
            output_format="7z",
            optimize_source_archives=True,
        )

        output_zip = root / "optimized.zip"
        zipped = create_archive(
            [source_zip],
            output_zip,
            output_format="zip",
            optimize_source_archives=True,
        )

        report = {
            "benchmark": "QBX 3.2 universal archive bridge",
            "source_zip_bytes": source_zip.stat().st_size,
            "source_zip_sha256": sha256(source_zip),
            "direct_qbx": {
                "archive_bytes": direct.stat().st_size,
                "seconds": direct_seconds,
                "ratio_vs_source_zip": direct.stat().st_size / source_zip.stat().st_size,
                "logical_transform": False,
                "result": {
                    "unique_chunks": direct_result.get("unique_chunks"),
                    "repair_edges": direct_result.get("repair_edges"),
                },
            },
            "optimized_qbx": {
                "archive_bytes": optimized.stat().st_size,
                "seconds": optimized_seconds,
                "ratio_vs_source_zip": optimized.stat().st_size / source_zip.stat().st_size,
                "optimized_source_archives": optimized_result.get("optimized_source_archives"),
                "logical_transform": optimized_result.get("logical_transform"),
                "repair_edges": optimized_result.get("repair_edges"),
                "deduplicated_chunks": optimized_result.get("deduplicated_chunks"),
            },
            "optimized_7z": {
                "archive_bytes": output_7z.stat().st_size,
                "technology": seven.get("format_technology"),
            },
            "optimized_zip": {
                "archive_bytes": output_zip.stat().st_size,
                "technology": zipped.get("format_technology"),
            },
            "logical_content_roundtrip": logical_ok,
        }

        report["qbx_size_improvement_pct_vs_direct"] = (
            (direct.stat().st_size - optimized.stat().st_size)
            / direct.stat().st_size
            * 100.0
        )
        report["gate"] = bool(
            logical_ok
            and optimized_result.get("optimized_source_archives") == 1
            and optimized.stat().st_size < direct.stat().st_size
        )

        OUTPUT.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        print(f"Report: {OUTPUT}")
        if not report["gate"]:
            raise SystemExit(2)
        print("QBX 3.2 UNIVERSAL BRIDGE BENCHMARK: PASS")


if __name__ == "__main__":
    main()

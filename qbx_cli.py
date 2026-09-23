from __future__ import annotations

import argparse
import json
from pathlib import Path

from qbx import __version__
from qbx.api import inspect, pack, repair, unpack, verify
from qbx.core import QBXError


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qbx",
        description="QBX 3.0 archive engine with AGRP global planning and ARK repair lattice",
    )
    parser.add_argument("--version", action="version", version=f"QBX {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pack", help="Create a QBX archive")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument(
        "--profile",
        choices=["resilient", "adaptive", "fast", "balanced", "smallest"],
        default="resilient",
        help="resilient = QBX V3 AGRP+ARK (default)",
    )
    p.add_argument("--max-size-mb", type=float, default=None)
    p.add_argument("--max-decode-ms", type=float, default=None)
    p.add_argument(
        "--repair-budget-pct",
        type=float,
        default=5.0,
        help="Maximum V3 repair payload budget as percent of primary payload (default: 5)",
    )
    p.add_argument("--comment", default=None, help="Optional archive comment")

    p = sub.add_parser("unpack", aliases=["extract"], help="Extract a QBX archive safely")
    p.add_argument("archive")
    p.add_argument("destination")
    p.add_argument("--overwrite", action="store_true")

    p = sub.add_parser("verify", aliases=["test"], help="Verify data and ARK recovery paths")
    p.add_argument("archive")

    p = sub.add_parser("repair", help="Reconstruct a recoverable QBX V3 archive into a clean file")
    p.add_argument("archive")
    p.add_argument("output", nargs="?", default=None)
    p.add_argument("--repair-budget-pct", type=float, default=5.0)

    p = sub.add_parser("list", aliases=["info"], help="Show archive manifest and planner metadata")
    p.add_argument("archive")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.cmd == "pack":
            result = pack(
                args.source,
                args.output,
                profile=args.profile,
                max_size_mb=args.max_size_mb,
                max_decode_ms=args.max_decode_ms,
                repair_budget_pct=args.repair_budget_pct,
                comment=args.comment,
            )
        elif args.cmd in {"unpack", "extract"}:
            result = unpack(args.archive, args.destination, overwrite=args.overwrite)
        elif args.cmd in {"verify", "test"}:
            result = verify(args.archive)
        elif args.cmd == "repair":
            source = Path(args.archive)
            output = args.output or str(source.with_name(source.stem + "-repaired.qbx"))
            result = repair(source, output, repair_budget_pct=args.repair_budget_pct)
        else:
            manifest = inspect(args.archive)
            result = {
                "format": manifest["format"],
                "version": manifest["version"],
                "product_version": manifest.get("product_version"),
                "compression_profile": manifest.get("compression_profile"),
                "comment": manifest.get("comment", ""),
                "planner": manifest.get("planner"),
                "statistics": manifest["statistics"],
                "features": manifest.get("features", []),
                "directories": manifest.get("directories", []),
                "files": [
                    {
                        "path": item["path"],
                        "size": item["size"],
                        "sha256": item["sha256"],
                        "blocks": len(item["blocks"]),
                    }
                    for item in manifest["files"]
                ],
            }
        emit(result)
    except QBXError as exc:
        raise SystemExit(f"QBX error: {exc}") from exc


if __name__ == "__main__":
    main()

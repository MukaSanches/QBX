from __future__ import annotations

import argparse
import json

from qbx import __version__
from qbx.core import QBXError, inspect, pack, unpack, verify


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qbx",
        description="QBX adaptive archive engine",
    )
    parser.add_argument("--version", action="version", version=f"QBX {__version__}")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pack", help="Create a QBX archive")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument(
        "--profile",
        choices=["fast", "balanced", "smallest"],
        default="balanced",
        help="Compression objective (default: balanced)",
    )

    p = sub.add_parser("unpack", help="Extract a QBX archive safely")
    p.add_argument("archive")
    p.add_argument("destination")
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing destination files",
    )

    p = sub.add_parser("verify", help="Verify all blocks and reconstructed files")
    p.add_argument("archive")

    p = sub.add_parser("list", help="Show archive manifest")
    p.add_argument("archive")

    return parser


def main() -> None:
    args = build_parser().parse_args()

    try:
        if args.cmd == "pack":
            result = pack(args.source, args.output, profile=args.profile)
        elif args.cmd == "unpack":
            result = unpack(
                args.archive,
                args.destination,
                overwrite=args.overwrite,
            )
        elif args.cmd == "verify":
            result = verify(args.archive)
        else:
            manifest = inspect(args.archive)
            result = {
                "format": manifest["format"],
                "version": manifest["version"],
                "compression_profile": manifest["compression_profile"],
                "statistics": manifest["statistics"],
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

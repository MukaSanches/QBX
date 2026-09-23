import argparse
import json

from qbx.core import pack, unpack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qbx",
        description="QBX adaptive archive research engine",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    pack_parser = sub.add_parser("pack", help="Create a QBX archive")
    pack_parser.add_argument("source")
    pack_parser.add_argument("output")

    unpack_parser = sub.add_parser("unpack", help="Extract a QBX archive")
    unpack_parser.add_argument("archive")
    unpack_parser.add_argument("destination")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.cmd == "pack":
        result = pack(args.source, args.output)
    else:
        result = unpack(args.archive, args.destination)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

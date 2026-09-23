from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import stat
import tempfile
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from qbx import __version__
from qbx.adaptive_v2 import _global_plan, _profile_block
from qbx.core import (
    BLOCK_META,
    CODEC_NAMES,
    CODEC_ZLIB,
    HASH_NAME,
    MAX_CHUNK,
    MAX_MANIFEST_BYTES,
    MAX_STORED_BLOCK_BYTES,
    U64,
    CodecEngine,
    QBXError,
    _collect,
    _destination,
    _read_exact,
    _safe_relpath,
    file_hexdigest,
    hexdigest,
    iter_file_chunks,
)

MAGIC_V3 = b"QBX3\r\n\x1a\n"
FORMAT_VERSION_V3 = 3
PRODUCT_VERSION = __version__
DEFAULT_REPAIR_BUDGET_PCT = 5.0
ARK_GROUP_SIZE = 7
ARK_CANDIDATE_LIMIT = 14
ARK_MAX_EDGES = 8
ARK_MAX_FAILED_EDGES = 2
REPAIR_METADATA_ESTIMATE = 96


@dataclass(frozen=True)
class RepairCandidate:
    a: str
    b: str
    payload: bytes
    repair_hash: str
    raw_size: int
    stored_size: int


def _xor_padded(a: bytes, b: bytes) -> bytes:
    size = max(len(a), len(b))
    aa = a.ljust(size, b"\x00")
    bb = b.ljust(size, b"\x00")
    return bytes(x ^ y for x, y in zip(aa, bb))


def _recover_other(known: bytes, delta: bytes, target_size: int) -> bytes:
    size = len(delta)
    padded = known.ljust(size, b"\x00")
    if len(padded) != size:
        raise QBXError("Repair delta is shorter than the known block")
    return bytes(x ^ y for x, y in zip(padded, delta))[:target_size]


def _graph_connected(nodes: tuple[str, ...], edges: tuple[RepairCandidate, ...]) -> bool:
    if len(nodes) <= 1:
        return True
    reachable = {nodes[0]}
    changed = True
    while changed:
        changed = False
        for edge in edges:
            if edge.a in reachable and edge.b not in reachable:
                reachable.add(edge.b)
                changed = True
            elif edge.b in reachable and edge.a not in reachable:
                reachable.add(edge.a)
                changed = True
    return len(reachable) == len(nodes)


def _survivability(
    nodes: tuple[str, ...],
    edges: tuple[RepairCandidate, ...],
) -> tuple[int, int, tuple[int, ...]]:
    survived = 0
    total = 0
    levels: list[int] = []
    max_failed = min(ARK_MAX_FAILED_EDGES, len(edges))
    for lost_count in range(max_failed + 1):
        level_ok = 0
        for lost_indices in itertools.combinations(range(len(edges)), lost_count):
            lost = set(lost_indices)
            active = tuple(edge for i, edge in enumerate(edges) if i not in lost)
            total += 1
            if _graph_connected(nodes, active):
                survived += 1
                level_ok += 1
        levels.append(level_ok)
    while len(levels) < ARK_MAX_FAILED_EDGES + 1:
        levels.append(0)
    return survived, total, tuple(levels)


def _cheapest_connected(
    nodes: tuple[str, ...],
    candidates: list[RepairCandidate],
) -> list[RepairCandidate]:
    parent = {node: node for node in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    selected: list[RepairCandidate] = []
    for edge in sorted(candidates, key=lambda e: (e.stored_size, e.a, e.b)):
        ra, rb = find(edge.a), find(edge.b)
        if ra == rb:
            continue
        parent[ra] = rb
        selected.append(edge)
        if len(selected) == len(nodes) - 1:
            break
    return selected if len(selected) == len(nodes) - 1 else []


def _bounded_ark_plan(
    nodes: tuple[str, ...],
    candidates: list[RepairCandidate],
    byte_budget: int,
) -> tuple[list[RepairCandidate], dict]:
    """Bounded exact ARK search for one small production group.

    The scientific ARK-2 experiment exhaustively searched its full 7-node
    instance. Production archives can contain thousands of blocks, so V3
    applies the same survivability objective to independent groups, keeps a
    deterministic candidate frontier, and then exactly enumerates that bounded
    frontier under a byte budget.
    """
    if len(nodes) < 2 or byte_budget <= 0 or not candidates:
        return [], {"examined": 0, "feasible": 0, "survived": 0, "total": 0}

    mst = _cheapest_connected(nodes, candidates)
    if not mst:
        return [], {"examined": 0, "feasible": 0, "survived": 0, "total": 0}

    must_keep = {(e.a, e.b) for e in mst}
    ordered = sorted(candidates, key=lambda e: (e.stored_size, e.a, e.b))
    frontier = list(mst)
    for edge in ordered:
        if (edge.a, edge.b) in must_keep:
            continue
        frontier.append(edge)
        if len(frontier) >= ARK_CANDIDATE_LIMIT:
            break

    min_edges = len(nodes) - 1
    max_edges = min(ARK_MAX_EDGES, len(frontier))
    best: tuple[RepairCandidate, ...] | None = None
    best_key: tuple | None = None
    best_metrics = (0, 0, (0, 0, 0))
    examined = 0
    feasible = 0

    for edge_count in range(min_edges, max_edges + 1):
        for combo in itertools.combinations(frontier, edge_count):
            examined += 1
            stored = sum(e.stored_size for e in combo)
            if stored > byte_budget or not _graph_connected(nodes, combo):
                continue
            feasible += 1
            survived, total, levels = _survivability(nodes, combo)
            key = (survived, levels[2], levels[1], -stored, -edge_count)
            if best_key is None or key > best_key:
                best = combo
                best_key = key
                best_metrics = (survived, total, levels)

    if best is None:
        mst_cost = sum(e.stored_size for e in mst)
        if mst_cost <= byte_budget:
            best = tuple(mst)
            best_metrics = _survivability(nodes, best)
        else:
            return [], {
                "examined": examined,
                "feasible": feasible,
                "survived": 0,
                "total": 0,
            }

    survived, total, levels = best_metrics
    return list(best), {
        "examined": examined,
        "feasible": feasible,
        "survived": survived,
        "total": total,
        "rate": survived / total if total else 0.0,
        "levels": list(levels),
    }


def _make_repair_candidates(
    nodes: tuple[str, ...],
    raw_paths: dict[str, Path],
) -> list[RepairCandidate]:
    candidates: list[RepairCandidate] = []
    for a, b in itertools.combinations(nodes, 2):
        raw_a = raw_paths[a].read_bytes()
        raw_b = raw_paths[b].read_bytes()
        delta = _xor_padded(raw_a, raw_b)
        payload = zlib.compress(delta, 9)
        candidates.append(
            RepairCandidate(
                a=a,
                b=b,
                payload=payload,
                repair_hash=hexdigest(delta),
                raw_size=len(delta),
                stored_size=len(payload) + REPAIR_METADATA_ESTIMATE,
            )
        )
    return candidates


def _build_repair_lattice(
    ordered_hashes: list[str],
    raw_paths: dict[str, Path],
    primary_stored: dict[str, int],
    repair_budget_pct: float,
) -> tuple[list[dict], dict[str, dict], dict]:
    all_edges: list[dict] = []
    repair_records: dict[str, dict] = {}
    total_examined = 0
    total_feasible = 0
    protected: set[str] = set()
    group_reports: list[dict] = []

    # Cluster by raw block size before forming ARK groups.  Content-defined
    # chunks that differ radically in size are generally poor XOR repair
    # partners and can make a cheap connected lattice infeasible under a
    # strict repair-byte budget.  Size ordering is deterministic, scalable,
    # and keeps same-sized version-like blocks together for the bounded exact
    # search.
    grouped_hashes = sorted(
        ordered_hashes,
        key=lambda h: (raw_paths[h].stat().st_size, h),
    )

    for start in range(0, len(grouped_hashes), ARK_GROUP_SIZE):
        group = tuple(grouped_hashes[start : start + ARK_GROUP_SIZE])
        if len(group) < 2:
            continue

        candidates = _make_repair_candidates(group, raw_paths)
        baseline = _cheapest_connected(group, candidates)
        if not baseline:
            continue

        baseline_budget = sum(e.stored_size for e in baseline)
        extras = [
            e
            for e in sorted(candidates, key=lambda e: e.stored_size)
            if e not in baseline
        ][:2]
        baseline_budget += sum(e.stored_size for e in extras)
        pct_budget = math.floor(
            sum(primary_stored[h] for h in group) * (repair_budget_pct / 100.0)
        )
        byte_budget = min(baseline_budget, pct_budget)
        if byte_budget <= 0:
            continue

        selected, report = _bounded_ark_plan(group, candidates, byte_budget)
        total_examined += report.get("examined", 0)
        total_feasible += report.get("feasible", 0)
        if not selected:
            continue

        for edge in selected:
            protected.update((edge.a, edge.b))
            all_edges.append(
                {
                    "a": edge.a,
                    "b": edge.b,
                    "repair": edge.repair_hash,
                    "delta_size": edge.raw_size,
                    "stored_size": len(edge.payload),
                }
            )
            repair_records.setdefault(
                edge.repair_hash,
                {
                    "codec": CODEC_ZLIB,
                    "raw_size": edge.raw_size,
                    "stored_size": len(edge.payload),
                    "payload": edge.payload,
                },
            )

        group_reports.append(
            {
                "nodes": len(group),
                "candidate_edges": len(candidates),
                "selected_edges": len(selected),
                "byte_budget": byte_budget,
                "selected_bytes": sum(e.stored_size for e in selected),
                **report,
            }
        )

    return all_edges, repair_records, {
        "name": "ARK",
        "version": 2,
        "group_size": ARK_GROUP_SIZE,
        "candidate_limit": ARK_CANDIDATE_LIMIT,
        "max_edges_per_group": ARK_MAX_EDGES,
        "failure_depth": ARK_MAX_FAILED_EDGES,
        "repair_budget_pct": repair_budget_pct,
        "protected_blocks": len(protected),
        "repair_edges": len(all_edges),
        "repair_records": len(repair_records),
        "search_examined": total_examined,
        "search_feasible": total_feasible,
        "groups": group_reports,
    }


def pack_resilient(
    source: str | Path,
    output: str | Path,
    *,
    max_size_mb: float | None = None,
    max_decode_ms: float | None = None,
    repair_budget_pct: float = DEFAULT_REPAIR_BUDGET_PCT,
    comment: str | None = None,
) -> dict:
    started = time.perf_counter()
    source = Path(source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not (0.0 <= repair_budget_pct <= 100.0):
        raise QBXError("repair_budget_pct must be between 0 and 100")
    if max_size_mb is not None and max_size_mb <= 0:
        raise QBXError("--max-size-mb must be positive")
    if max_decode_ms is not None and max_decode_ms <= 0:
        raise QBXError("--max-decode-ms must be positive")

    max_size_bytes = (
        math.floor(max_size_mb * 1024 * 1024)
        if max_size_mb is not None
        else None
    )
    max_decode_ns = (
        math.floor(max_decode_ms * 1_000_000)
        if max_decode_ms is not None
        else None
    )

    root, files, directories = _collect(source)
    file_entries: list[dict] = []
    total_input = 0
    logical_chunks = 0

    with tempfile.TemporaryDirectory(
        prefix="qbx-v3-",
        dir=str(output.parent.resolve()),
    ) as td:
        temp_root = Path(td)
        raw_dir = temp_root / "raw"
        candidate_dir = temp_root / "candidates"
        raw_dir.mkdir()
        candidate_dir.mkdir()

        blocks = {}
        raw_paths: dict[str, Path] = {}
        first_seen: list[str] = []

        for path in files:
            rel = path.relative_to(root).as_posix()
            _safe_relpath(rel)
            refs: list[str] = []
            h = hashlib.sha256()
            file_size = 0

            for raw in iter_file_chunks(path):
                logical_chunks += 1
                h.update(raw)
                file_size += len(raw)
                block_hash = hexdigest(raw)
                refs.append(block_hash)
                if block_hash not in blocks:
                    raw_path = raw_dir / block_hash
                    raw_path.write_bytes(raw)
                    raw_paths[block_hash] = raw_path
                    first_seen.append(block_hash)
                    blocks[block_hash] = _profile_block(
                        raw,
                        block_hash,
                        candidate_dir,
                    )

            total_input += file_size
            stat_value = path.stat()
            file_entries.append(
                {
                    "path": rel,
                    "size": file_size,
                    "sha256": h.hexdigest(),
                    "blocks": refs,
                    "mode": stat.S_IMODE(stat_value.st_mode),
                    "mtime_ns": stat_value.st_mtime_ns,
                }
            )

        ordered_hashes = first_seen
        planned_blocks = [blocks[h] for h in ordered_hashes]
        plan = _global_plan(
            planned_blocks,
            max_size_bytes=max_size_bytes,
            max_decode_ns=max_decode_ns,
        )

        primary_records: dict[str, dict] = {}
        primary_stored: dict[str, int] = {}
        block_sizes: dict[str, int] = {}
        codec_histogram: dict[str, int] = {}

        for block_hash, block, selected_index in zip(
            ordered_hashes,
            planned_blocks,
            plan["selection"],
        ):
            candidate = block.candidates[selected_index]
            payload = Path(candidate.payload_path).read_bytes()
            primary_records[block_hash] = {
                "codec": candidate.codec,
                "raw_size": block.raw_size,
                "stored_size": len(payload),
                "payload": payload,
            }
            primary_stored[block_hash] = len(payload)
            block_sizes[block_hash] = block.raw_size
            key = (
                candidate.name
                if candidate.level is None
                else f"{candidate.name}:{candidate.level}"
            )
            codec_histogram[key] = codec_histogram.get(key, 0) + 1

        repair_edges, repair_records, ark_report = _build_repair_lattice(
            ordered_hashes,
            raw_paths,
            primary_stored,
            repair_budget_pct,
        )

        all_records = dict(primary_records)
        for repair_hash, record in repair_records.items():
            all_records.setdefault(repair_hash, record)

        repair_payload_bytes = sum(
            record["stored_size"]
            for h, record in repair_records.items()
            if h not in primary_records
        )
        primary_payload_bytes = sum(
            record["stored_size"] for record in primary_records.values()
        )

        planner_manifest = {
            "name": "AGRP+ARK",
            "version": 3,
            "primary": {
                "name": "AGRP",
                "version": 2,
                "baseline_stored_bytes": plan["baseline_stored"],
                "planned_stored_bytes": plan["stored"],
                "baseline_decode_ns": plan["baseline_decode_ns"],
                "planned_decode_ns": plan["decode_ns"],
                "size_budget_bytes": plan["size_budget"],
                "decode_budget_ns": plan["decode_budget_ns"],
                "peak_dp_states": plan["peak_states"],
                "codec_histogram": codec_histogram,
            },
            "repair": ark_report,
        }

        manifest = {
            "format": "QBX",
            "version": FORMAT_VERSION_V3,
            "product_version": PRODUCT_VERSION,
            "hash": HASH_NAME,
            "compression_profile": "resilient-v3",
            "comment": comment or "",
            "chunking": {
                "algorithm": "gear-content-defined",
                "min": 32 * 1024,
                "target": 128 * 1024,
                "max": 512 * 1024,
            },
            "features": [
                "content-defined-chunking",
                "global-deduplication",
                "pareto-representation-pruning",
                "adaptive-global-representation-planning",
                "goal-constrained-optimization",
                "ark-repair-lattice",
                "counterfactual-repair-representations",
                "sha256-block-integrity",
                "sha256-file-integrity",
                "self-repair-corrupt-blocks",
                "safe-path-extraction",
            ],
            "planner": planner_manifest,
            "directories": directories,
            "files": file_entries,
            "block_sizes": block_sizes,
            "repair_edges": repair_edges,
            "statistics": {
                "input_bytes": total_input,
                "file_count": len(file_entries),
                "directory_count": len(directories),
                "chunk_references": logical_chunks,
                "unique_blocks": len(primary_records),
                "repair_edges": len(repair_edges),
                "repair_records": len(repair_records),
                "record_count": len(all_records),
                "primary_payload_bytes": primary_payload_bytes,
                "repair_payload_bytes": repair_payload_bytes,
            },
        }

        manifest_bytes = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        if len(manifest_bytes) > MAX_MANIFEST_BYTES:
            raise QBXError("QBX V3 manifest exceeds safety limit")

        fd, temp_name = tempfile.mkstemp(
            prefix=".qbx-v3-write-",
            suffix=".tmp",
            dir=str(output.parent.resolve()),
        )
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(MAGIC_V3)
                out.write(U64.pack(len(manifest_bytes)))
                out.write(manifest_bytes)
                out.write(U64.pack(len(all_records)))
                for record_hash in sorted(all_records):
                    record = all_records[record_hash]
                    payload = record["payload"]
                    out.write(bytes.fromhex(record_hash))
                    out.write(
                        BLOCK_META.pack(
                            record["codec"],
                            record["raw_size"],
                            len(payload),
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
    return {
        "ok": True,
        "format_version": FORMAT_VERSION_V3,
        "product_version": PRODUCT_VERSION,
        "profile": "resilient-v3",
        "planner": "AGRP+ARK",
        "files": len(file_entries),
        "directories": len(directories),
        "original": total_input,
        "archive": archive_size,
        "ratio": archive_size / total_input if total_input else 0.0,
        "logical_chunks": logical_chunks,
        "unique_chunks": len(primary_records),
        "deduplicated_chunks": logical_chunks - len(primary_records),
        "repair_edges": len(repair_edges),
        "protected_blocks": ark_report["protected_blocks"],
        "repair_payload_bytes": repair_payload_bytes,
        "repair_overhead_pct": (
            repair_payload_bytes / max(1, primary_payload_bytes)
        )
        * 100.0,
        "ark_search_examined": ark_report["search_examined"],
        "ark_search_feasible": ark_report["search_feasible"],
        "seconds": time.perf_counter() - started,
        "archive_sha256": file_hexdigest(output),
    }


def _validate_v3_manifest(manifest: object) -> dict:
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != "QBX"
        or manifest.get("version") != FORMAT_VERSION_V3
    ):
        raise QBXError("Invalid QBX V3 manifest")

    files = manifest.get("files")
    directories = manifest.get("directories", [])
    stats = manifest.get("statistics")
    block_sizes = manifest.get("block_sizes")
    edges = manifest.get("repair_edges", [])
    if (
        not isinstance(files, list)
        or not isinstance(directories, list)
        or not isinstance(stats, dict)
        or not isinstance(block_sizes, dict)
        or not isinstance(edges, list)
    ):
        raise QBXError("Malformed QBX V3 manifest collections")

    seen: set[str] = set()
    for rel in directories:
        if not isinstance(rel, str):
            raise QBXError("Directory path must be a string")
        _safe_relpath(rel)
        if rel in seen:
            raise QBXError(f"Duplicate archive path: {rel}")
        seen.add(rel)

    for entry in files:
        if not isinstance(entry, dict):
            raise QBXError("Malformed file entry")
        rel = entry.get("path")
        if not isinstance(rel, str):
            raise QBXError("File path must be a string")
        _safe_relpath(rel)
        if rel in seen:
            raise QBXError(f"Duplicate archive path: {rel}")
        seen.add(rel)
        if not isinstance(entry.get("size"), int) or entry["size"] < 0:
            raise QBXError(f"Invalid file size for {rel}")
        file_hash = entry.get("sha256")
        if not isinstance(file_hash, str) or len(file_hash) != 64:
            raise QBXError(f"Invalid file SHA-256 for {rel}")
        refs = entry.get("blocks")
        if not isinstance(refs, list):
            raise QBXError(f"Invalid block list for {rel}")
        for ref in refs:
            if ref not in block_sizes:
                raise QBXError(f"Missing block size metadata: {ref}")

    for block_hash, size in block_sizes.items():
        if (
            not isinstance(block_hash, str)
            or len(block_hash) != 64
            or not isinstance(size, int)
            or not (0 < size <= MAX_CHUNK)
        ):
            raise QBXError("Invalid V3 block-size metadata")

    for edge in edges:
        if (
            not isinstance(edge, dict)
            or edge.get("a") not in block_sizes
            or edge.get("b") not in block_sizes
        ):
            raise QBXError("Invalid ARK repair edge")
        repair_hash = edge.get("repair")
        if not isinstance(repair_hash, str) or len(repair_hash) != 64:
            raise QBXError("Invalid ARK repair hash")

    record_count = stats.get("record_count")
    if not isinstance(record_count, int) or record_count < len(block_sizes):
        raise QBXError("Invalid V3 record count")
    return manifest


def _open_v3(archive: Path) -> tuple[BinaryIO, dict]:
    f = archive.open("rb")
    try:
        magic = _read_exact(f, len(MAGIC_V3), "V3 magic")
        if magic != MAGIC_V3:
            raise QBXError("Invalid QBX V3 magic")

        manifest_len = U64.unpack(
            _read_exact(f, 8, "manifest length")
        )[0]
        if manifest_len > MAX_MANIFEST_BYTES:
            raise QBXError("QBX V3 manifest exceeds safety limit")

        raw = _read_exact(f, manifest_len, "manifest")
        try:
            manifest = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise QBXError("Invalid QBX V3 manifest JSON") from exc

        return f, _validate_v3_manifest(manifest)
    except Exception:
        f.close()
        raise


def _scan_v3(
    f: BinaryIO,
    manifest: dict,
) -> dict[str, tuple[int, int, int, int]]:
    count = U64.unpack(_read_exact(f, 8, "record count"))[0]
    if count != manifest["statistics"]["record_count"]:
        raise QBXError("QBX V3 record count mismatch")

    index: dict[str, tuple[int, int, int, int]] = {}
    for _ in range(count):
        record_hash = _read_exact(f, 32, "record digest").hex()
        codec, raw_size, stored_size = BLOCK_META.unpack(
            _read_exact(f, BLOCK_META.size, "record metadata")
        )
        if codec not in CODEC_NAMES:
            raise QBXError(f"Unknown codec id {codec}")
        if raw_size <= 0 or raw_size > MAX_CHUNK:
            raise QBXError(f"Invalid record raw size: {raw_size}")
        if stored_size <= 0 or stored_size > MAX_STORED_BLOCK_BYTES:
            raise QBXError(f"Invalid record stored size: {stored_size}")
        if record_hash in index:
            raise QBXError(f"Duplicate V3 record: {record_hash}")

        offset = f.tell()
        _read_exact(f, stored_size, "record payload")
        index[record_hash] = (offset, codec, raw_size, stored_size)

    if f.read(1):
        raise QBXError("Unexpected trailing data after QBX V3 records")
    return index


class _V3Store:
    def __init__(
        self,
        f: BinaryIO,
        index: dict[str, tuple[int, int, int, int]],
        manifest: dict,
    ):
        self.f = f
        self.index = index
        self.manifest = manifest
        self.cache: dict[str, bytes] = {}
        self.bad_records: set[str] = set()
        self.recovered_blocks: set[str] = set()
        self.edges_by_block: dict[str, list[dict]] = {}
        for edge in manifest.get("repair_edges", []):
            self.edges_by_block.setdefault(edge["a"], []).append(edge)
            self.edges_by_block.setdefault(edge["b"], []).append(edge)

    def load_record(self, record_hash: str) -> bytes:
        if record_hash in self.cache:
            return self.cache[record_hash]
        if record_hash in self.bad_records:
            raise QBXError(f"Corrupted V3 record: {record_hash}")

        try:
            offset, codec, raw_size, stored_size = self.index[record_hash]
        except KeyError as exc:
            self.bad_records.add(record_hash)
            raise QBXError(f"Missing V3 record: {record_hash}") from exc

        try:
            self.f.seek(offset)
            payload = _read_exact(
                self.f,
                stored_size,
                "indexed V3 payload",
            )
            raw = CodecEngine.decode(codec, payload, raw_size)
            if hexdigest(raw) != record_hash:
                raise QBXError(f"Record SHA-256 mismatch: {record_hash}")
        except Exception as exc:
            self.bad_records.add(record_hash)
            if isinstance(exc, QBXError):
                raise
            raise QBXError(
                f"Failed to decode V3 record: {record_hash}"
            ) from exc

        self.cache[record_hash] = raw
        return raw

    def load_data(
        self,
        block_hash: str,
        stack: set[str] | None = None,
    ) -> bytes:
        if block_hash in self.cache:
            return self.cache[block_hash]

        try:
            return self.load_record(block_hash)
        except QBXError:
            pass

        stack = set() if stack is None else set(stack)
        if block_hash in stack:
            raise QBXError(
                f"ARK recovery cycle reached for block: {block_hash}"
            )
        stack.add(block_hash)

        target_size = self.manifest["block_sizes"].get(block_hash)
        if target_size is None:
            raise QBXError(f"Unknown V3 data block: {block_hash}")

        for edge in self.edges_by_block.get(block_hash, []):
            other = (
                edge["b"]
                if edge["a"] == block_hash
                else edge["a"]
            )
            try:
                delta = self.load_record(edge["repair"])
                other_raw = self.load_data(other, stack)
                candidate = _recover_other(
                    other_raw,
                    delta,
                    target_size,
                )
                if hexdigest(candidate) == block_hash:
                    self.cache[block_hash] = candidate
                    self.recovered_blocks.add(block_hash)
                    return candidate
            except QBXError:
                continue

        raise QBXError(
            f"ARK could not recover data block: {block_hash}"
        )


def inspect_v3(archive: str | Path) -> dict:
    f, manifest = _open_v3(Path(archive))
    f.close()
    return manifest


def _prepare_store(
    archive: Path,
) -> tuple[BinaryIO, dict, _V3Store]:
    f, manifest = _open_v3(archive)
    try:
        index = _scan_v3(f, manifest)
        return f, manifest, _V3Store(f, index, manifest)
    except Exception:
        f.close()
        raise


def verify_v3(archive: str | Path) -> dict:
    started = time.perf_counter()
    archive = Path(archive)
    f, manifest, store = _prepare_store(archive)
    try:
        for block_hash in manifest["block_sizes"]:
            store.load_data(block_hash)

        for entry in manifest["files"]:
            h = hashlib.sha256()
            size = 0
            for block_hash in entry["blocks"]:
                raw = store.load_data(block_hash)
                h.update(raw)
                size += len(raw)

            if size != entry["size"]:
                raise QBXError(
                    f"File size mismatch: {entry['path']}"
                )
            if h.hexdigest() != entry["sha256"]:
                raise QBXError(
                    f"File SHA-256 mismatch: {entry['path']}"
                )

        repair_hashes = {
            edge["repair"]
            for edge in manifest.get("repair_edges", [])
        }
        good_repairs = 0
        for repair_hash in repair_hashes:
            try:
                store.load_record(repair_hash)
                good_repairs += 1
            except QBXError:
                pass

        return {
            "ok": True,
            "healthy": len(store.bad_records) == 0,
            "degraded": len(store.bad_records) > 0,
            "format_version": FORMAT_VERSION_V3,
            "files": len(manifest["files"]),
            "blocks": len(manifest["block_sizes"]),
            "repair_edges": len(
                manifest.get("repair_edges", [])
            ),
            "repair_records_valid": good_repairs,
            "damaged_records": len(store.bad_records),
            "recovered_blocks": len(store.recovered_blocks),
            "recovered_block_hashes": sorted(
                store.recovered_blocks
            ),
            "archive_sha256": file_hexdigest(archive),
            "seconds": time.perf_counter() - started,
        }
    finally:
        f.close()


def unpack_v3(
    archive: str | Path,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> dict:
    started = time.perf_counter()
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)

    f, manifest, store = _prepare_store(Path(archive))
    try:
        for rel in manifest.get("directories", []):
            _destination(
                destination,
                rel,
            ).mkdir(parents=True, exist_ok=True)

        written = 0
        for entry in manifest["files"]:
            target = _destination(
                destination,
                entry["path"],
            )
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            if target.exists() and not overwrite:
                raise QBXError(
                    f"Refusing to overwrite existing path: {target}. "
                    "Use overwrite=True or --overwrite."
                )

            fd, temp_name = tempfile.mkstemp(
                prefix=".qbx-v3-extract-",
                dir=str(target.parent),
            )
            try:
                h = hashlib.sha256()
                size = 0
                with os.fdopen(fd, "wb") as out:
                    for block_hash in entry["blocks"]:
                        raw = store.load_data(block_hash)
                        out.write(raw)
                        h.update(raw)
                        size += len(raw)
                    out.flush()
                    os.fsync(out.fileno())

                if (
                    size != entry["size"]
                    or h.hexdigest() != entry["sha256"]
                ):
                    raise QBXError(
                        f"Reconstructed integrity mismatch: "
                        f"{entry['path']}"
                    )

                os.replace(temp_name, target)
                try:
                    os.chmod(
                        target,
                        int(entry.get("mode", 0o644)),
                    )
                    mtime_ns = entry.get("mtime_ns")
                    if isinstance(mtime_ns, int):
                        os.utime(
                            target,
                            ns=(mtime_ns, mtime_ns),
                        )
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
            "format_version": FORMAT_VERSION_V3,
            "files": len(manifest["files"]),
            "bytes": written,
            "recovered_blocks": len(
                store.recovered_blocks
            ),
            "seconds": time.perf_counter() - started,
        }
    finally:
        f.close()


def repair_v3(
    archive: str | Path,
    output: str | Path,
    *,
    repair_budget_pct: float = DEFAULT_REPAIR_BUDGET_PCT,
) -> dict:
    """Reconstruct every recoverable file and build a clean V3 archive."""
    archive = Path(archive)
    output = Path(output)

    if archive.resolve() == output.resolve():
        raise QBXError(
            "Repair output must be different from the damaged archive"
        )

    with tempfile.TemporaryDirectory(
        prefix="qbx-v3-repair-"
    ) as td:
        restored = Path(td) / "restored"
        unpack_result = unpack_v3(
            archive,
            restored,
            overwrite=False,
        )
        packed = pack_resilient(
            restored,
            output,
            repair_budget_pct=repair_budget_pct,
        )
        checked = verify_v3(output)
        if not checked["ok"]:
            raise QBXError(
                "Repaired archive failed verification"
            )

        return {
            "ok": True,
            "source": str(archive),
            "output": str(output),
            "recovered_blocks": unpack_result[
                "recovered_blocks"
            ],
            "archive_sha256": packed[
                "archive_sha256"
            ],
        }


def record_index_v3(
    archive: str | Path,
) -> tuple[dict, dict[str, tuple[int, int, int, int]]]:
    """Testing/benchmark helper: return manifest plus physical record index."""
    f, manifest = _open_v3(Path(archive))
    try:
        index = _scan_v3(f, manifest)
        return manifest, index
    finally:
        f.close()

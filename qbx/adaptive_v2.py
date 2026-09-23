from __future__ import annotations

import hashlib
import json
import lzma
import math
import os
import stat
import tempfile
import time
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

import zstandard as zstd

from qbx.core import (
    BLOCK_META,
    CODEC_LZMA,
    CODEC_RAW,
    CODEC_ZLIB,
    CODEC_ZSTD,
    FORMAT_VERSION,
    HASH_NAME,
    MAGIC,
    MAX_MANIFEST_BYTES,
    U64,
    QBXError,
    _collect,
    _safe_relpath,
    file_hexdigest,
    hexdigest,
    iter_file_chunks,
)


@dataclass(frozen=True)
class Candidate:
    codec: int
    name: str
    level: int | None
    stored_size: int
    encode_ns: int
    decode_ns: int
    payload_path: str


@dataclass(frozen=True)
class PlannedBlock:
    block_hash: str
    raw_size: int
    candidates: tuple[Candidate, ...]


def _dominates(a: Candidate, b: Candidate) -> bool:
    return (
        a.stored_size <= b.stored_size
        and a.encode_ns <= b.encode_ns
        and a.decode_ns <= b.decode_ns
        and (
            a.stored_size < b.stored_size
            or a.encode_ns < b.encode_ns
            or a.decode_ns < b.decode_ns
        )
    )


def _pareto(candidates: list[Candidate]) -> tuple[Candidate, ...]:
    result: list[Candidate] = []
    for i, candidate in enumerate(candidates):
        if any(
            i != j and _dominates(other, candidate)
            for j, other in enumerate(candidates)
        ):
            continue
        result.append(candidate)

    result.sort(
        key=lambda c: (
            c.stored_size,
            c.decode_ns,
            c.encode_ns,
            c.name,
            -1 if c.level is None else c.level,
        )
    )
    return tuple(result)


def _candidate_specs(raw: bytes):
    yield CODEC_RAW, "raw", None, (lambda value: value), (lambda value: value)

    for level in (1, 3, 9, 19):
        # O próprio contêiner QBX já valida cada bloco com SHA-256.
        # O checksum interno do frame Zstandard seria uma segunda verificação
        # redundante e adiciona 4 bytes a cada frame comprimido.
        compressor = zstd.ZstdCompressor(
            level=level,
            threads=0,
            write_checksum=False,
            write_content_size=True,
            write_dict_id=False,
        )
        decompressor = zstd.ZstdDecompressor()
        yield (
            CODEC_ZSTD,
            "zstd",
            level,
            compressor.compress,
            lambda payload, d=decompressor, size=len(raw): d.decompress(
                payload, max_output_size=max(1, size)
            ),
        )

    for level in (1, 6, 9):
        yield (
            CODEC_ZLIB,
            "deflate",
            level,
            lambda value, lv=level: zlib.compress(value, lv),
            zlib.decompress,
        )

    for level in (3, 6):
        yield (
            CODEC_LZMA,
            "lzma",
            level,
            lambda value, lv=level: lzma.compress(value, preset=lv),
            lzma.decompress,
        )


def _profile_block(
    raw: bytes,
    block_hash: str,
    candidate_dir: Path,
) -> PlannedBlock:
    candidates: list[Candidate] = []

    for index, (codec, name, level, encode, decode) in enumerate(
        _candidate_specs(raw)
    ):
        # One warm-up establishes codec correctness without contaminating
        # the measured pass with first-call initialization.
        warm = encode(raw)
        if decode(warm) != raw:
            raise QBXError(f"{name} level={level} failed warm-up round trip")

        start = time.perf_counter_ns()
        payload = encode(raw)
        encode_ns = time.perf_counter_ns() - start

        start = time.perf_counter_ns()
        restored = decode(payload)
        decode_ns = time.perf_counter_ns() - start

        if restored != raw:
            raise QBXError(f"{name} level={level} failed measured round trip")

        payload_path = candidate_dir / f"{block_hash}.{index}.bin"
        payload_path.write_bytes(payload)

        candidates.append(
            Candidate(
                codec=codec,
                name=name,
                level=level,
                stored_size=len(payload),
                encode_ns=max(1, encode_ns),
                decode_ns=max(1, decode_ns),
                payload_path=str(payload_path),
            )
        )

    frontier = _pareto(candidates)
    if not frontier:
        raise QBXError("Adaptive planner produced an empty Pareto frontier")

    return PlannedBlock(
        block_hash=block_hash,
        raw_size=len(raw),
        candidates=frontier,
    )


def _totals(blocks: list[PlannedBlock], selection: tuple[int, ...]):
    stored = encode_ns = decode_ns = 0
    for block, selected in zip(blocks, selection):
        choice = block.candidates[selected]
        stored += choice.stored_size
        encode_ns += choice.encode_ns
        decode_ns += choice.decode_ns
    return stored, encode_ns, decode_ns


def _local_smallest(blocks: list[PlannedBlock]) -> tuple[int, ...]:
    return tuple(
        min(
            range(len(block.candidates)),
            key=lambda i: (
                block.candidates[i].stored_size,
                block.candidates[i].encode_ns,
                block.candidates[i].decode_ns,
            ),
        )
        for block in blocks
    )


def _global_plan(
    blocks: list[PlannedBlock],
    *,
    max_size_bytes: int | None,
    max_decode_ns: int | None,
) -> dict:
    if not blocks:
        return {
            "selection": tuple(),
            "score": 0.0,
            "stored": 0,
            "encode_ns": 0,
            "decode_ns": 0,
            "peak_states": 1,
            "baseline_stored": 0,
            "baseline_decode_ns": 0,
            "size_budget": 0,
            "decode_budget_ns": 0,
        }

    baseline = _local_smallest(blocks)
    baseline_stored, baseline_encode, baseline_decode = _totals(blocks, baseline)

    size_budget = (
        max_size_bytes
        if max_size_bytes is not None
        else max(baseline_stored, math.ceil(baseline_stored * 1.035))
    )

    requested_decode = (
        max_decode_ns
        if max_decode_ns is not None
        else max(1, math.ceil(baseline_decode * 0.90))
    )

    raw_total = max(1, sum(block.raw_size for block in blocks))
    max_encode = max(
        1,
        sum(max(c.encode_ns for c in block.candidates) for block in blocks),
    )
    max_decode = max(
        1,
        sum(max(c.decode_ns for c in block.candidates) for block in blocks),
    )

    def cost(candidate: Candidate) -> float:
        return (
            0.50 * candidate.stored_size / raw_total
            + 0.20 * candidate.encode_ns / max_encode
            + 0.30 * candidate.decode_ns / max_decode
        )

    def attempt(decode_budget: int):
        size_bucket = max(1, size_budget // 2048)
        decode_bucket = max(1, decode_budget // 2048)

        # (quantized size, quantized decode) ->
        # (score, selection, stored, encode, decode)
        states = {(0, 0): (0.0, tuple(), 0, 0, 0)}
        peak_states = 1

        for block in blocks:
            nxt: dict[tuple[int, int], tuple] = {}

            for old in states.values():
                old_score, old_selection, old_size, old_encode, old_decode = old

                for candidate_index, candidate in enumerate(block.candidates):
                    new_size = old_size + candidate.stored_size
                    new_decode = old_decode + candidate.decode_ns

                    if new_size > size_budget or new_decode > decode_budget:
                        continue

                    new_encode = old_encode + candidate.encode_ns
                    new_score = old_score + cost(candidate)
                    key = (new_size // size_bucket, new_decode // decode_bucket)
                    proposed = (
                        new_score,
                        old_selection + (candidate_index,),
                        new_size,
                        new_encode,
                        new_decode,
                    )

                    current = nxt.get(key)
                    if current is None or (
                        proposed[0],
                        proposed[2],
                        proposed[4],
                        proposed[3],
                    ) < (
                        current[0],
                        current[2],
                        current[4],
                        current[3],
                    ):
                        nxt[key] = proposed

            if not nxt:
                return None

            # Keep only non-dominated DP states. The hard cap makes the
            # product planner bounded on large archives while preserving the
            # best frontier states found so far.
            values = sorted(
                nxt.values(),
                key=lambda s: (s[2], s[4], s[0], s[3]),
            )

            frontier = []
            best_score = math.inf
            best_decode_seen = math.inf
            for state in values:
                score, _, stored, _, decode_ns = state
                if score < best_score or decode_ns < best_decode_seen:
                    frontier.append(state)
                    best_score = min(best_score, score)
                    best_decode_seen = min(best_decode_seen, decode_ns)

            if len(frontier) > 4096:
                frontier = sorted(
                    frontier,
                    key=lambda s: (s[0], s[2], s[4], s[3]),
                )[:4096]

            states = {
                (state[2] // size_bucket, state[4] // decode_bucket): state
                for state in frontier
            }
            peak_states = max(peak_states, len(states))

        best = min(
            states.values(),
            key=lambda s: (s[0], s[2], s[4], s[3]),
        )

        return {
            "selection": best[1],
            "score": best[0],
            "stored": best[2],
            "encode_ns": best[3],
            "decode_ns": best[4],
            "peak_states": peak_states,
            "decode_budget_ns": decode_budget,
        }

    if max_decode_ns is not None:
        factors = (1.0,)
    else:
        factors = (1.0, 1.10, 1.25, 1.50, 2.0, 4.0)

    result = None
    for factor in factors:
        result = attempt(max(1, math.ceil(requested_decode * factor)))
        if result is not None:
            break

    if result is None:
        raise QBXError(
            "Adaptive global goal is infeasible. Increase the size/decode budget."
        )

    result.update(
        {
            "baseline_stored": baseline_stored,
            "baseline_encode_ns": baseline_encode,
            "baseline_decode_ns": baseline_decode,
            "size_budget": size_budget,
        }
    )
    return result


def pack_adaptive(
    source: str | Path,
    output: str | Path,
    *,
    max_size_mb: float | None = None,
    max_decode_ms: float | None = None,
) -> dict:
    started = time.perf_counter()
    source = Path(source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

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
        prefix="qbx-v2-",
        dir=str(output.parent.resolve()),
    ) as tmp:
        tmp_root = Path(tmp)
        candidate_dir = tmp_root / "candidates"
        candidate_dir.mkdir()

        blocks_by_hash: dict[str, PlannedBlock] = {}

        for path in files:
            rel = path.relative_to(root).as_posix()
            _safe_relpath(rel)

            refs: list[str] = []
            file_hash = hashlib.sha256()
            file_size = 0

            for raw in iter_file_chunks(path):
                logical_chunks += 1
                file_hash.update(raw)
                file_size += len(raw)

                block_hash = hexdigest(raw)
                refs.append(block_hash)

                if block_hash not in blocks_by_hash:
                    blocks_by_hash[block_hash] = _profile_block(
                        raw,
                        block_hash,
                        candidate_dir,
                    )

            total_input += file_size
            file_entries.append(
                {
                    "path": rel,
                    "size": file_size,
                    "sha256": file_hash.hexdigest(),
                    "blocks": refs,
                    "mode": stat.S_IMODE(path.stat().st_mode),
                }
            )

        ordered_hashes = sorted(blocks_by_hash)
        ordered_blocks = [blocks_by_hash[h] for h in ordered_hashes]

        plan = _global_plan(
            ordered_blocks,
            max_size_bytes=max_size_bytes,
            max_decode_ns=max_decode_ns,
        )

        block_meta: dict[str, dict] = {}
        codec_histogram: dict[str, int] = {}

        for block, selected in zip(ordered_blocks, plan["selection"]):
            candidate = block.candidates[selected]
            codec_key = (
                candidate.name
                if candidate.level is None
                else f"{candidate.name}:{candidate.level}"
            )
            codec_histogram[codec_key] = codec_histogram.get(codec_key, 0) + 1

            block_meta[block.block_hash] = {
                "codec": candidate.codec,
                "raw_size": block.raw_size,
                "stored_size": candidate.stored_size,
                "path": candidate.payload_path,
            }

        planner_manifest = {
            "name": "AGRP",
            "version": 2,
            "objective": {
                "size_weight": 0.50,
                "encode_weight": 0.20,
                "decode_weight": 0.30,
            },
            "candidate_model": [
                "raw",
                "zstd:1",
                "zstd:3",
                "zstd:9",
                "zstd:19",
                "deflate:1",
                "deflate:6",
                "deflate:9",
                "lzma:3",
                "lzma:6",
            ],
            "baseline_stored_bytes": plan["baseline_stored"],
            "planned_stored_bytes": plan["stored"],
            "baseline_decode_ns": plan["baseline_decode_ns"],
            "planned_decode_ns": plan["decode_ns"],
            "size_budget_bytes": plan["size_budget"],
            "decode_budget_ns": plan["decode_budget_ns"],
            "peak_dp_states": plan["peak_states"],
            "codec_histogram": codec_histogram,
        }

        manifest = {
            "format": "QBX",
            "version": FORMAT_VERSION,
            "product_version": "2.0.0",
            "hash": HASH_NAME,
            "compression_profile": "adaptive-v2",
            "planner": planner_manifest,
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
                "measured-codec-latency",
                "sha256-block-integrity",
                "sha256-file-integrity",
                "safe-path-extraction",
            ],
            "directories": directories,
            "files": file_entries,
            "statistics": {
                "input_bytes": total_input,
                "file_count": len(file_entries),
                "directory_count": len(directories),
                "chunk_references": logical_chunks,
                "unique_blocks": len(block_meta),
            },
        }

        manifest_bytes = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        if len(manifest_bytes) > MAX_MANIFEST_BYTES:
            raise QBXError("QBX manifest exceeds safety limit")

        fd, temp_name = tempfile.mkstemp(
            prefix=".qbx-v2-write-",
            suffix=".tmp",
            dir=str(output.parent.resolve()),
        )

        try:
            with os.fdopen(fd, "wb") as out:
                out.write(MAGIC)
                out.write(U64.pack(len(manifest_bytes)))
                out.write(manifest_bytes)
                out.write(U64.pack(len(ordered_hashes)))

                for block_hash in ordered_hashes:
                    meta = block_meta[block_hash]
                    payload = Path(meta["path"]).read_bytes()

                    if len(payload) != meta["stored_size"]:
                        raise QBXError("Adaptive candidate payload changed during build")

                    out.write(bytes.fromhex(block_hash))
                    out.write(
                        BLOCK_META.pack(
                            meta["codec"],
                            meta["raw_size"],
                            meta["stored_size"],
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
    elapsed = time.perf_counter() - started

    baseline_stored = max(1, plan["baseline_stored"])
    baseline_decode = max(1, plan["baseline_decode_ns"])

    return {
        "format_version": FORMAT_VERSION,
        "product_version": "2.0.0",
        "profile": "adaptive-v2",
        "planner": "AGRP",
        "files": len(file_entries),
        "directories": len(directories),
        "original": total_input,
        "archive": archive_size,
        "ratio": archive_size / total_input if total_input else 0.0,
        "logical_chunks": logical_chunks,
        "unique_chunks": len(block_meta),
        "deduplicated_chunks": logical_chunks - len(block_meta),
        "planned_payload_bytes": plan["stored"],
        "baseline_payload_bytes": plan["baseline_stored"],
        "payload_size_delta_pct": (
            (plan["stored"] / baseline_stored) - 1.0
        ) * 100.0,
        "estimated_decode_improvement_pct": (
            1.0 - (plan["decode_ns"] / baseline_decode)
        ) * 100.0,
        "peak_dp_states": plan["peak_states"],
        "codec_histogram": codec_histogram,
        "seconds": elapsed,
        "archive_sha256": file_hexdigest(output),
    }

# Changelog

## 2.0.0 — AGRP adaptive global planning

- Added **AGRP (Adaptive Global Representation Planner)** as the new adaptive default.
- Added measured candidate representations across RAW, Zstandard, Deflate and LZMA.
- Added Pareto pruning for block representations.
- Added bounded global dynamic planning with size and decode-latency goals.
- Added optional CLI budgets with `--max-size-mb` and `--max-decode-ms`.
- Embedded planner metadata and codec histograms in QBX manifests.
- Preserved the existing content-defined chunking, SHA-256 deduplication and verified extraction path.
- Added QBX 2.0 scientific validation documentation and raw observed results.
- Added benchmark charts to the README.
- Added a reproducible product benchmark against ZIP/Deflate.
- Added adaptive-profile round-trip and goal-validation tests.
- Updated the Windows GUI so AGRP adaptive mode is the default.
- Updated Windows installer, portable package and checksums to version 2.0.0.

### Scientific validation note

A small tested optimization instance was mapped to a one-hot QUBO and exhaustively enumerated across 262,144 states (18 binary variables). The QUBO optimum matched the original exact objective for that instance. This validates the tested mapping; it does not establish quantum advantage.

## 1.0.0-rc1 — Product candidate

- Added bounded-memory content-defined file chunking.
- Added global SHA-256 block deduplication.
- Added adaptive RAW, Zstandard, Deflate, and LZMA representations.
- Added fast, balanced, and smallest profiles.
- Added deterministic QBX v2 container layout.
- Added atomic archive creation and atomic extracted-file replacement.
- Added safe path validation and overwrite protection.
- Added complete block and reconstructed-file verification.
- Added empty-directory preservation.
- Added qbx verify and qbx list commands.
- Expanded corruption, determinism, profile, and security tests.
- Added Linux/Windows CI.
- Added automated standalone Windows executable build.
- Added reproducible product benchmark against ZIP/Deflate.

## 1.0 Technology Preview

- Initial experimental QBX container.
- Content-defined chunking.
- Global block deduplication.
- Adaptive RAW/ZLIB/LZMA selection.
- SHA-256 integrity.
- Classical planning baseline and QUBO research pipeline.

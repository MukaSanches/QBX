# Changelog

## 3.0.0 — AGRP + ARK resilient archive

- Added QBX V3 container magic and backward-compatible V2/V3 API dispatch.
- Added **ARK (Adaptive Reconstruction Knowledge Lattice)** production planner.
- Added content-addressed compressed XOR repair representations.
- Added bounded exact local survivability search under a real repair-byte budget.
- Added recursive SHA-256-authenticated recovery of corrupted primary block payloads.
- Added healthy / degraded-recoverable archive verification states.
- Added `qbx repair` to rebuild a clean V3 archive from recoverable data.
- Preserved QBX 2.0 AGRP and the `adaptive`, `fast`, `balanced`, and `smallest` profiles.
- Added a classic Windows archive-manager GUI with menu/toolbar/address/list/status layout.
- Added add, extract, test, view, delete, find, info, comment, favorites, repair and ARK-budget controls.
- Added Explorer file association and context-menu commands in the installer.
- Added V3 corruption/recovery regression tests and product benchmark.
- Added portable and installer packaging for 3.0.0.
- Added automated GitHub Release publishing from a successful main Windows build.
- Added technical V3 architecture and invention-disclosure documentation without asserting patentability.

## 2.0.0 — AGRP adaptive global planning

- Added **AGRP (Adaptive Global Representation Planner)** as the adaptive default.
- Added measured RAW/Zstandard/Deflate/LZMA candidate representations.
- Added Pareto pruning and bounded global dynamic planning.
- Added optional size/decode-latency goals and planner metadata.
- Preserved content-defined chunking, SHA-256 deduplication and verified extraction.

## 1.0.0-rc1 — Product candidate

- Added bounded-memory content-defined file chunking.
- Added global SHA-256 block deduplication.
- Added adaptive RAW, Zstandard, Deflate, and LZMA representations.
- Added Windows GUI, portable package and installer.

## 1.0 Technology Preview

- Initial experimental QBX container.
- Classical planning baseline and QUBO research pipeline.

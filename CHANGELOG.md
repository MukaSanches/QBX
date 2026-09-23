# Changelog

## 3.2.0 — Universal Archive Bridge

- Added **Universal Archive Bridge** for QBX, ZIP, 7z and RAR workflows.
- Added automatic decontainerization of selected QBX/ZIP/7z/RAR inputs before recompression.
- Added a visual output-format selector to the Windows creation dialog.
- Added standard ZIP/Deflate and 7z output.
- Added standard RAR5 output when RAR/WinRAR is installed; QBX does not bundle the proprietary RAR encoder.
- Added explicit UI messaging that full AGRP + ARK resilience is embedded only in `.qbx`.
- Added `qbx create` and `qbx formats` CLI commands.
- Added traversal-safe ZIP/7z preprocessing and validated external RAR extraction.
- Added regression tests proving an already-compressed ZIP can become a smaller QBX when decontainerization exposes duplicated logical content.
- Added `benchmarks/v3_2_bridge_benchmark.py` and release evidence `v3_2_bridge.json`.
- Preserved V2/V3 QBX read compatibility, ARK repair and existing Windows workflows.

## 3.1.0 — Classic Archive Manager UI

- Rebuilt the Windows GUI on Qt/PySide6 for a substantially more polished desktop experience.
- Added a dark classic archive-manager layout with familiar menu, toolbar, address and file-list workflow.
- Added direct filesystem browsing when no archive is open.
- Added prominent **Criar QBX** flow with source selection, output destination and advanced planning controls.
- Added V3 Resilient profile controls for AGRP size/decode goals and ARK byte budget.
- Added an in-app technology explanation for CDC, SHA-256, global deduplication, multi-codec profiling, Pareto pruning, AGRP and ARK.
- Added drag-and-drop opening and archive addition workflows.
- Preserved add, extract, test, view, delete, search, info, comments, favorites and repair.
- Kept the QBX V3 archive engine and V2 compatibility intact.
- Windows CI still performs engine self-test plus an actual packaged-GUI startup smoke test.

## 3.0.1 — Windows GUI startup hotfix

- Fixed the packaged Windows GUI crash: `_tkinter.TclError: expected integer but got "UI"`.
- Replaced the ambiguous Tcl font descriptor `Segoe UI 9` with safe named Tk font configuration.
- Added a real GUI startup smoke test that instantiates and destroys the packaged application.
- Refined the classic archive-manager toolbar for clearer actions.
- Preserved QBX V3 AGRP + ARK archive, verification, recovery and repair behavior.
- Rebuilt portable and installer packages as 3.0.1.

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

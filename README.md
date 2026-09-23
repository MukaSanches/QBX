# QBX 3.2.0

[![CI](https://github.com/MukaSanches/QBX/actions/workflows/ci.yml/badge.svg)](https://github.com/MukaSanches/QBX/actions/workflows/ci.yml)
[![Windows product](https://github.com/MukaSanches/QBX/actions/workflows/build-windows.yml/badge.svg)](https://github.com/MukaSanches/QBX/actions/workflows/build-windows.yml)

QBX is an experimental adaptive archive format and Windows archive manager. **QBX 3.2.0** combines the existing AGRP global compression planner with **ARK — Adaptive Reconstruction Knowledge Lattice**, a bounded repair-topology planner designed to make some corrupted primary block representations reconstructable without requiring quantum hardware.

## V3 pipeline

```text
files
  -> content-defined chunks
  -> SHA-256 global deduplication
  -> RAW / Zstandard / Deflate / LZMA candidates
  -> Pareto pruning
  -> AGRP primary planning
  -> ARK reversible repair candidates
  -> bounded exact repair-topology search under byte budget
  -> QBX V3 container
  -> SHA-256 verified extraction / self-recovery / repair
```

The decoder never needs a QPU. Quantum/QUBO work remains a research direction for planner optimization; no quantum-advantage claim is made.

## Windows application

The Windows GUI now follows a familiar classic archive-manager workflow with original QBX branding:

- menu bar and large command toolbar;
- address bar and folder navigation inside an archive;
- details view with name, size, block count, type, modified time and SHA-256 prefix;
- create/open/add/extract/test/view/delete/find/info/comment/favorites/repair;
- configurable ARK repair-byte budget;
- `.qbx` file association and Explorer context-menu commands when installed.

The project does not copy WinRAR source code, proprietary icons or trademarked branding.

Windows CI produces:

- `QBX-Setup-3.2.0.exe`;
- `QBX-Portable-3.2.0.zip`;
- `SHA256SUMS.txt`;
- `v3_latest.json` reproducible benchmark evidence.

The installer is not Authenticode-signed, so Windows SmartScreen may show an unknown-publisher warning.


## QBX 3.2 desktop experience

The Windows application now uses a Qt/PySide6 desktop shell designed around the familiar workflow of classic archive managers while keeping QBX branding and original runtime-drawn icons. When no archive is open, the main window browses the filesystem directly; selecting files or folders and pressing **Criar QBX** opens one visual creation dialog.

That dialog exposes the actual QBX technology instead of hiding it behind a generic compression slider: **Resilient V3** activates content-defined chunking, SHA-256 content identity, global deduplication, measured multi-codec candidates, Pareto pruning, AGRP global planning and the ARK repair lattice. Advanced users can set a target archive size, target decode cost and ARK repair-byte budget before creating the archive.

## Universal Archive Bridge

QBX 3.2 can recognize a selected `.qbx`, `.zip`, `.7z` or `.rar` input and, when **Optimize compressed input** is enabled, open that container first so the next compressor sees the logical files rather than an already-compressed byte stream.

This directly addresses the common case where a ZIP becomes a slightly larger QBX when packed as an opaque file. If the ZIP contains duplicate or related files, decontainerization lets QBX CDC and global deduplication see those relationships again.

The creation dialog now lets the user choose:

- **QBX** — full CDC + SHA-256 + deduplication + multi-codec + Pareto + AGRP + ARK stack;
- **7z** — standard 7z output;
- **ZIP** — standard ZIP/Deflate output;
- **RAR5** — standard RAR output when an installed RAR/WinRAR encoder is detected.

A standard RAR/ZIP/7z file does **not** contain the QBX ARK lattice. Keeping those outputs standard is what preserves compatibility with other archivers. RAR creation depends on the separately installed RAR/WinRAR encoder; QBX does not bundle it.

See [docs/UNIVERSAL_BRIDGE_V3.2.md](docs/UNIVERSAL_BRIDGE_V3.2.md).

## CLI

Install from source:

```bash
python -m pip install -e .
```

Create a resilient V3 archive:

```bash
qbx pack MyFolder MyArchive.qbx
```

Create/convert through the Universal Archive Bridge:

```bash
qbx create optimized.qbx existing.zip --format qbx
qbx create optimized.7z existing.zip --format 7z
qbx create optimized.zip existing.7z --format zip
qbx create optimized.rar existing.zip --format rar
qbx formats
```

Explicit V3 options:

```bash
qbx pack MyFolder MyArchive.qbx --profile resilient --repair-budget-pct 5 --comment "backup"
```

QBX 2.0 AGRP and traditional profiles remain available:

```bash
qbx pack MyFolder v2-adaptive.qbx --profile adaptive
qbx pack MyFolder fast.qbx --profile fast
qbx pack MyFolder balanced.qbx --profile balanced
qbx pack MyFolder smallest.qbx --profile smallest
```

Inspect, test and extract:

```bash
qbx list MyArchive.qbx
qbx test MyArchive.qbx
qbx extract MyArchive.qbx RestoredFolder
```

Rebuild a clean archive when V3 recovery paths can reconstruct damaged primary data:

```bash
qbx repair Damaged.qbx Repaired.qbx
```

## What ARK does

For small deterministic groups of unique blocks, V3 generates reversible pairwise repair candidates and measures their actual compressed cost. It builds a connected baseline, applies a real byte ceiling and then exactly enumerates a bounded candidate frontier to maximize topology survival under loss of up to two repair representations.

When a primary record fails decompression or hash validation, the decoder can recursively use a valid repair delta plus another surviving block. A candidate reconstruction is accepted only if its SHA-256 equals the original content-addressed block identity.

See [docs/QBX-V3.md](docs/QBX-V3.md) for the full engineering description.

## ARK-2 research evidence

The final pre-product ARK-2 experiment on its deterministic research instance reported:

- baseline: 2,929 repair bytes, 36/56 survival scenarios (64.2857143%);
- ARK: 2,920 repair bytes, 41/46 (89.1304348%);
- exact search: 1,020,680 configurations examined, 21,897 feasible;
- physical/model validation: 322 scenarios;
- 319/319 predicted-recoverable scenarios reconstructed correctly;
- 3/3 predicted-unrecoverable scenarios remained unrecoverable;
- zero false positives and zero false negatives;
- bit-perfect whenever recoverable.

Those are experimental results for the tested model and corpus, not a universal performance claim or proof of patentability.

## Reproducible V3 product benchmark

Run:

```bash
python benchmarks/v3_benchmark.py
```

The benchmark builds a deterministic corpus, exercises QBX 2.0 AGRP, QBX 3.0 resilient mode and ZIP/Deflate, verifies round trips, deliberately corrupts one ARK-protected V3 primary record, and requires the V3 decoder to reconstruct the original tree hash exactly. Results are written to `benchmarks/results/v3_latest.json`.

## Compatibility and safety

The `qbx.api` layer detects V2 and V3 archives automatically. Existing V2 archives remain readable and extractable.

QBX uses safe relative-path validation, refuses overwrite by default, performs atomic archive writes, authenticates primary and reconstructed content with SHA-256, and verifies reconstructed files end-to-end.

V3 remains an experimental format. Keep independent copies of important data until the format has broader interoperability testing, fuzzing, independent security review and long-term archival experience.

## Patent / invention status

The repository includes [docs/INVENTION_DISCLOSURE_V3.md](docs/INVENTION_DISCLOSURE_V3.md), which records the technical mechanism and possible claim directions for professional evaluation. A passing experiment or implementation does **not** make a technology patented, patent-pending, novel in the legal sense, or free of third-party rights.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python benchmarks/v3_benchmark.py
```

## License

MIT.

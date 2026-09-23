# QBX 3.0 — AGRP + ARK

QBX 3.0 keeps the QBX 2.0 content-defined chunking, global SHA-256 deduplication and AGRP primary-representation planner, then adds **ARK — Adaptive Reconstruction Knowledge Lattice**.

## Product architecture

```text
files/folders
  -> content-defined chunks
  -> SHA-256 block identity + global deduplication
  -> RAW/Zstandard/Deflate/LZMA candidates
  -> Pareto pruning
  -> AGRP primary global planning
  -> ARK bounded exact repair-lattice planning
  -> QBX V3 records + manifest
  -> verify / extract / repair with recursive recovery
```

ARK does not replace compression. It stores selected reversible relationships between primary blocks. In V3 the repair representation is a zero-padded XOR delta compressed with Deflate. Each relationship records two primary block hashes and a content-addressed repair record. If one primary payload becomes corrupt but a valid reconstruction path survives, the decoder reconstructs the missing bytes, trims to the target size and accepts them only when their SHA-256 equals the original block hash.

## ARK-2 research gate that informed V3

The final research experiment used a 7-block deterministic corpus and compared a cheap connected baseline with an exact ARK search under a byte budget.

Observed result:

- baseline: 2,929 repair bytes, 10 representations, 36/56 structural-survival scenarios = 64.2857143%;
- ARK: 2,920 repair bytes, 9 representations, 41/46 = 89.1304348%;
- improvement: +24.844720 percentage points;
- two-edge-failure survival: baseline 27/45, ARK 31/36;
- exact search: 1,020,680 configurations examined, 21,897 feasible;
- physical/model validation: 322 scenarios;
- predicted recoverable: 319, physically recovered: 319;
- predicted unrecoverable: 3, physically unrecoverable: 3;
- false positives: 0;
- false negatives: 0;
- bit-perfect whenever recoverable: true.

This result established the tested property on that experimental instance. It does not by itself establish patent novelty, universal superiority, or quantum advantage.

## Production planner

A full exact search over every pair of every block would be impractical for large archives. Production V3 therefore applies ARK in deterministic groups of up to seven unique blocks. It:

1. builds reversible pairwise repair candidates;
2. measures actual compressed repair cost;
3. constructs a cheap connected baseline;
4. enforces a user-configurable real byte budget;
5. keeps a bounded deterministic candidate frontier;
6. exactly enumerates the bounded frontier;
7. maximizes survival of the repair topology under loss of up to two repair representations;
8. uses size and edge count as tie-breakers.

The default repair budget is 5% of primary payload bytes. This is configurable from the GUI and CLI.

## Recovery semantics

`qbx verify` and extraction first attempt the primary representation. If a primary record fails decompression or SHA-256 validation, V3 recursively explores ARK relations. A reconstruction is accepted only if the computed target block hash matches the manifest's SHA-256 identity.

A V3 archive can therefore be:

- **healthy**: every record validates directly;
- **degraded but recoverable**: one or more records are damaged but every referenced file reconstructs exactly;
- **unrecoverable**: no surviving repair path can reconstruct at least one required primary block.

`qbx repair` writes a fresh clean V3 archive from recoverable data.

## Compatibility

The new `qbx.api` layer detects QBX V2 versus V3 by magic bytes. Existing V2 archives remain readable, verifiable and extractable. Traditional `fast`, `balanced`, `smallest` and V2 `adaptive` profiles remain available. `resilient` is the V3 default for the GUI and CLI.

## Windows application

The V3 Windows application uses a classic desktop archive-manager layout: menu bar, command toolbar, address bar, detailed archive list and status bar. It supports creating/opening archives, adding content, extraction, testing, viewing, deletion, search, information, comments, favorites, configurable ARK budget and repair. The installer adds `.qbx` association and Explorer context-menu commands.

The UI intentionally uses QBX branding and does not copy proprietary WinRAR artwork, icons, trademark or source code.

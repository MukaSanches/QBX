# QBX Format — Research Specification 1.0

QBX is an experimental lossless adaptive archive container.

## Current principles

1. Content-defined chunking.
2. Global content-addressed deduplication.
3. Independent representation per unique chunk.
4. Adaptive codec selection.
5. Cryptographic integrity verification.
6. Deterministic reconstruction.
7. Quantum/classical planning kept separate from byte encoding.
8. No claim of quantum advantage without reproducible benchmarks.

## Container

Magic:

`51 42 58 01`

Followed by:

- manifest length;
- UTF-8 JSON manifest;
- unique block count;
- content-addressed block records.

Each block record contains its SHA-256 identifier, codec identifier, uncompressed size, stored size, and payload.

Every reconstructed file must match its original SHA-256.

## Technology-preview warning

The binary layout is not yet frozen. Future QBX versions may intentionally break compatibility until the specification reaches a stable version.

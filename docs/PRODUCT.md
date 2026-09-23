# QBX Product Candidate

QBX 1.0.0-rc1 is a functional archive-engine candidate built around content-defined chunking, global block deduplication, adaptive per-block compression, and end-to-end integrity checks.

## What is implemented

- bounded-memory file chunking;
- content-defined chunk boundaries;
- SHA-256 block addressing;
- global deduplication across files;
- RAW, Zstandard, Deflate, and LZMA representations;
- fast, balanced, and smallest profiles;
- deterministic archive layout for the same input metadata/content;
- atomic archive writes;
- safe extraction path validation;
- refusal to overwrite by default;
- SHA-256 verification of every decoded block and reconstructed file;
- empty-directory preservation;
- list/inspect command;
- corruption detection;
- Linux and Windows CI;
- automated Windows qbx.exe build.

## Product boundary

The archive engine is completely classical and does not require quantum hardware to create or extract an archive.

The quantum work is an optional research layer for archive planning. A quantum result must not be described as an advantage unless it is compared reproducibly against strong classical baselines.

## Commands

    qbx pack SOURCE ARCHIVE.qbx --profile balanced
    qbx verify ARCHIVE.qbx
    qbx list ARCHIVE.qbx
    qbx unpack ARCHIVE.qbx OUTPUT
    qbx unpack ARCHIVE.qbx OUTPUT --overwrite

## Current limitations

This is a release candidate, not a final stable archival standard.

The Python content-defined chunker is correctness-oriented and is not yet a native high-throughput implementation. Symlinks and special filesystem objects are rejected. The binary format may still change before a stable specification is frozen. The Windows executable is not code-signed, so Windows may show an unknown-publisher warning.

## Scientific status

QBX has an experimental QUBO/QAOA research path. Simulator experiments can validate the mathematical/software pipeline, but they do not establish quantum advantage. Physical-QPU experiments, repeated trials, circuit/transpilation details, uncertainty, and classical controls are required for stronger claims.

# QBX

[![CI](https://github.com/MukaSanches/QBX/actions/workflows/ci.yml/badge.svg)](https://github.com/MukaSanches/QBX/actions/workflows/ci.yml)

QBX is an experimental adaptive archive format focused on content-defined storage, global deduplication, per-block compression selection, integrity verification, and research into classical/quantum archive planning.

## Product candidate: 1.0.0-rc1

The product branch provides a usable archive workflow:

    files and folders
        -> content-defined chunks
        -> SHA-256 block identity
        -> global deduplication
        -> RAW / Zstandard / Deflate / LZMA selection
        -> .qbx container
        -> verification
        -> safe lossless extraction

Quantum hardware is not required to create or open a QBX archive.

## Install from source

    python -m pip install -e .

For development:

    python -m pip install -e ".[dev]"

## Use

Create an archive:

    qbx pack MyFolder MyFolder.qbx --profile balanced

Profiles:

- fast: RAW + fast Zstandard;
- balanced: RAW + Zstandard + Deflate + LZMA;
- smallest: higher compression settings across all codecs.

Verify before extraction:

    qbx verify MyFolder.qbx

Inspect contents:

    qbx list MyFolder.qbx

Extract:

    qbx unpack MyFolder.qbx RestoredFolder

Existing files are not overwritten unless explicitly requested:

    qbx unpack MyFolder.qbx RestoredFolder --overwrite

## Benchmark

Run the reproducible local product benchmark:

    python benchmarks/product_benchmark.py

It compares the QBX profiles with Python ZIP/Deflate on the same generated dataset. Results are measurements for that dataset and machine, not universal compression claims.

## Windows executable

The product branch includes a GitHub Actions build for a standalone qbx.exe. The executable is tested before being uploaded as a workflow artifact. It is not currently code-signed.

## Quantum research

QBX also explores representing archive-planning decisions as QUBO problems and solving them with classical and quantum/hybrid optimization methods.

The quantum layer is a planner, not a mechanism that directly compresses arbitrary bytes. Simulator success does not establish quantum advantage.

## Safety and maturity

QBX 1.0.0-rc1 is a release candidate. Keep independent copies of important data until the format and implementation have undergone broader compatibility, fuzzing, and independent review.

See [docs/PRODUCT.md](docs/PRODUCT.md), [docs/QBX-SPEC-1.0.md](docs/QBX-SPEC-1.0.md), and [SECURITY.md](SECURITY.md).

## License

MIT.

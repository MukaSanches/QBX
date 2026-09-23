# QBX

[![CI](https://github.com/MukaSanches/QBX/actions/workflows/ci.yml/badge.svg)](https://github.com/MukaSanches/QBX/actions/workflows/ci.yml)
[![Windows product](https://github.com/MukaSanches/QBX/actions/workflows/build-windows.yml/badge.svg)](https://github.com/MukaSanches/QBX/actions/workflows/build-windows.yml)

QBX is an experimental adaptive archive format focused on content-defined storage, global deduplication, per-block compression selection, integrity verification, and research into classical/quantum archive planning.

## Product candidate: 1.0.0-rc1

The current engine supports:

    files and folders
        -> content-defined chunks
        -> SHA-256 block identity
        -> global deduplication
        -> RAW / Zstandard / Deflate / LZMA selection
        -> .qbx container
        -> verification
        -> safe lossless extraction

Quantum hardware is **not** required to create or open a QBX archive.

## Windows application

The Windows build produces:

- **QBX-Setup-1.0.0-rc1.exe** — graphical installer;
- **QBX-Portable-1.0.0-rc1.zip** — portable GUI + CLI;
- **SHA256SUMS.txt** — integrity hashes.

The graphical application lets a normal Windows user choose files/folders, create a `.qbx`, verify it, inspect its contents, and extract it without using Python or a terminal.

The installer is not yet code-signed, so Windows may show an unknown-publisher warning.

See [docs/WINDOWS.md](docs/WINDOWS.md).

## Install from source

    python -m pip install -e .

For development:

    python -m pip install -e ".[dev]"

## Command line

Create:

    qbx pack MyFolder MyFolder.qbx --profile balanced

Profiles:

- `fast`: RAW + fast Zstandard;
- `balanced`: RAW + Zstandard + Deflate + LZMA;
- `smallest`: higher compression settings across all codecs.

Verify:

    qbx verify MyFolder.qbx

Inspect:

    qbx list MyFolder.qbx

Extract:

    qbx unpack MyFolder.qbx RestoredFolder

Existing files are not overwritten unless explicitly requested:

    qbx unpack MyFolder.qbx RestoredFolder --overwrite

## Benchmark

Run:

    python benchmarks/product_benchmark.py

The benchmark compares the QBX profiles with Python ZIP/Deflate on the same reproducibly generated dataset. Results apply to that dataset and machine; they are not universal compression claims.

## Quantum research

QBX explores representing archive-planning decisions as QUBO problems and solving them with classical and quantum/hybrid optimization methods.

The quantum layer is a planner, not a mechanism that directly compresses arbitrary bytes. Simulator success does not establish quantum advantage.

## Safety and maturity

QBX 1.0.0-rc1 is a release candidate. Keep independent copies of important data until the format and implementation have undergone broader compatibility, fuzzing, and independent review.

See [docs/PRODUCT.md](docs/PRODUCT.md), [docs/QBX-SPEC-1.0.md](docs/QBX-SPEC-1.0.md), [docs/WINDOWS.md](docs/WINDOWS.md), and [SECURITY.md](SECURITY.md).

## License

MIT.

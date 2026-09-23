# QBX

[![CI](https://github.com/MukaSanches/QBX/actions/workflows/ci.yml/badge.svg)](https://github.com/MukaSanches/QBX/actions/workflows/ci.yml)

**QBX is an experimental goal-driven adaptive archive format.**

Instead of treating an archive as only a stream of compressed files, QBX experiments with content-defined blocks, global deduplication, adaptive representations, integrity verification, and optimization-based archive planning.

## QBX 1.0 Technology Preview

Current storage pipeline:

```text
Data
  → Content-defined chunking
  → SHA-256 content addressing
  → Global deduplication
  → Adaptive RAW / ZLIB / LZMA representation
  → QBX container
  → Verified lossless reconstruction
```

QBX also contains an experimental quantum-planning research pipeline:

```text
Archive planning problem
  → QUBO
  → Quantum circuit
  → Measurement
  → Candidate archive strategy
```

The quantum layer does **not** "quantum-compress bytes". Compression and reconstruction remain classical. The research question is whether combinatorial archive-planning decisions can benefit from quantum or hybrid optimization methods.

## Download

- [QBX v1.0.0 Technology Preview source package](releases/QBX-v1.0.0-tech-preview.tar.gz)
- [SHA-256 checksum](releases/QBX-v1.0.0-tech-preview.tar.gz.sha256)

Current package SHA-256:

```text
528aa07d6aa6375a82da041110be9056a10ec56369c2417bbe9807414c0513f6
```

## Install

Core + development tests:

```bash
python -m pip install -e '.[dev]'
```

Optional quantum experiment:

```bash
python -m pip install -e '.[quantum]'
```

## Usage

Pack:

```bash
qbx pack PATH archive.qbx
```

Unpack:

```bash
qbx unpack archive.qbx OUTPUT
```

Run tests:

```bash
python -m pytest -q
```

Run the quantum research experiment:

```bash
PYTHONPATH=. python -m experiments.quantum_planner_v1
```

## Verified research run

The first qBraid/Aer validation run used:

- 9 qubits
- 4096 shots
- Qiskit Aer simulator
- exact classical optimum: 155
- best sampled solution: 155

That run recovered the known optimum and validated the end-to-end QBX → QUBO → quantum-circuit → measurement pipeline.

**This is not evidence of quantum advantage.** The current experiment is a pipeline validation, not QAOA.

## Safety / maturity

QBX is a research technology preview. Do not use it as the only copy of important data. Archive extraction includes path-traversal protection and SHA-256 reconstruction checks, but the format and implementation are still experimental.

## Documentation

- [QBX Research Specification 1.0](docs/QBX-SPEC-1.0.md)
- [Quantum Optimizer Research Notes](docs/QUANTUM-OPTIMIZER.md)
- [Changelog](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE).

# QBX 1.0 Technology Preview

First public research release.

## Implemented

- Native experimental `.qbx` container
- Content-defined chunking
- Global block deduplication
- Adaptive RAW/ZLIB/LZMA representation
- SHA-256 block integrity
- SHA-256 reconstructed-file verification
- Lossless pack/unpack
- Classical archive-planning baseline
- QUBO compiler
- Quantum circuit planning experiment
- Qiskit Aer execution
- Public QBX format specification
- Path-traversal protection during extraction
- GitHub Actions test workflow

## Research result

The initial 9-qubit / 4096-shot qBraid/Aer experiment recovered the known optimum (cost 155).

This demonstrates the QBX → QUBO → quantum-circuit → measurement pipeline. It is not a claim of quantum advantage.

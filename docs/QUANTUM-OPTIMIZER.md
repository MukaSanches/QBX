# QBX Quantum Optimizer — Research Notes

QBX separates byte encoding from archive planning. Compression and reconstruction remain classical. The research layer models representation selection as a combinatorial optimization problem that can be compiled to QUBO.

## Current Technology Preview

The repository contains:

- a classical exact reference for a deliberately small planning instance;
- a QUBO compiler with one-hot representation constraints;
- a Qiskit/Aer quantum-circuit sampling experiment;
- comparison against the known classical optimum.

The included v1 experiment uses 9 qubits and 4096 shots. It is a pipeline validation, not QAOA and not evidence of quantum advantage.

## Intended progression

1. Measure candidate representation costs from real QBX chunks.
2. Build multi-objective costs (size, decode time, memory).
3. Compile the measured planning instance to QUBO.
4. Add QAOA and noise-aware simulation.
5. Compare against exact/classical heuristic baselines.
6. Run only validated, suitably small instances on physical QPUs.

Any claim of quantum benefit must be supported by reproducible benchmarks against strong classical baselines.

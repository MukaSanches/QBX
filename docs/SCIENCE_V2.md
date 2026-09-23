# QBX 2.0 scientific basis

QBX 2.0 introduces **AGRP — Adaptive Global Representation Planner** as an experimental archive-planning layer.

## What was validated

The research sequence used deterministic synthetic datasets spanning low entropy, structured text, repeated binary patterns, mixed data and pseudo-random data. Candidate representations were measured for stored size, encode latency and decode latency. Dominated candidates were removed with a Pareto filter.

A small optimization instance was solved exactly and then translated to a one-hot QUBO. Exhaustive enumeration of all 262,144 QUBO states for 18 binary variables produced the same objective score as the original exact formulation:

- exact objective: 0.25243298047920626
- QUBO objective: 0.25243298047920626
- equivalence: true

This validates the tested mathematical mapping. It does **not** establish quantum advantage.

## AGRP validation result

On the 12-block validation corpus:

| Metric | Local smallest | AGRP global |
| --- | ---: | ---: |
| Stored payload bytes | 526,921 | 537,088 |
| Measured decode sum | 1,143,671 ns | 426,689 ns |

AGRP used about 1.93% more stored payload bytes while reducing the measured decode-latency sum by about 62.69% in that run. The planner explored a bounded dynamic-programming frontier with a peak of 60 states.

The important result is demonstrated **trade-off planning**, not a claim that QBX universally compresses better than every other format.

## Product implementation

The production `adaptive` profile:

1. performs content-defined chunking;
2. deduplicates blocks by SHA-256;
3. measures multiple RAW/Zstandard/Deflate/LZMA representations;
4. Pareto-prunes dominated representations;
5. derives a local-smallest baseline;
6. uses a bounded global dynamic planner with size/decode budgets;
7. records planner metadata inside the QBX manifest;
8. writes the chosen representation for each unique block;
9. uses the existing verified QBX extraction and SHA-256 integrity path.

For scalability, the product planner uses bounded state retention; the research validation used exhaustive methods on small instances where exact ground truth was feasible.

## Quantum boundary

QBX archives never require a quantum computer for decoding. QUBO/QAOA remain research paths for the planning problem. Simulator agreement or QUBO equivalence must not be described as quantum advantage.

# QBX V3 — Technical invention disclosure candidate

## Status

This document records the technical mechanism implemented and experimentally motivated by QBX V3. It is **not a granted patent, patent application, novelty opinion, or freedom-to-operate opinion**. Patentability requires a professional prior-art search and legal analysis of the final claims.

## Technical problem

A conventional archive generally optimizes compression and integrity detection, but detection alone does not reconstruct a corrupted primary representation. Generic redundancy can add recovery capability but may ignore the archive's actual block relationships and storage budget.

## Candidate inventive concept

QBX V3 combines:

1. content-defined, content-addressed primary blocks;
2. per-block multiple compression candidates and global AGRP selection;
3. generation of reversible inter-block representations;
4. measurement of each repair representation's real stored-byte cost;
5. construction of a repair graph/lattice under a bounded byte budget;
6. optimization of the selected repair topology for survival under defined representation failures;
7. storage of repair representations as independently content-addressed records;
8. recursive decoder-side reconstruction using surviving primary and repair records;
9. cryptographic acceptance of a reconstructed block only when its SHA-256 equals the original block identity;
10. explicit reporting of healthy, degraded-recoverable and unrecoverable states.

The implemented V3 repair representation is compressed zero-padded XOR. The broader research concept is not limited to XOR; other reversible representations could be candidates if the decoder can prove the target identity.

## Research evidence

The ARK-2 final gate examined 1,020,680 candidate configurations and found 21,897 feasible configurations on the tested deterministic instance. Under the experiment's byte constraint, ARK used 2,920 bytes versus 2,929 bytes for the baseline while increasing the structural survivability metric from 64.2857143% to 89.1304348%. A separate physical validation covered 322 scenarios with zero false positives, zero false negatives and bit-perfect reconstruction in all 319 scenarios classified as recoverable.

These measurements support the engineering premise. They do not establish legal novelty.

## Claim-drafting directions for counsel

Potential claim themes to evaluate against prior art include:

- jointly selecting primary archive representations and a bounded set of reversible repair relationships based on measured storage cost and failure survivability;
- a content-addressed archive in which repair representations are independently hashed records and reconstruction is authenticated against the original primary-block identity;
- a bounded exact local optimizer that converts an archive's measured repair-candidate graph into a survivability-optimized lattice under a byte budget;
- decoder behavior that distinguishes structural unrecoverability from integrity failure and recursively reconstructs corrupted primary records through alternate representation paths.

## Prior-art boundaries that must be searched

Before any filing, search at minimum: delta compression graphs, dependency graphs, XOR parity, erasure coding, regenerating codes, locally repairable codes, deduplicated backup repair, content-addressed storage, recovery records, multi-representation archives, graph-resilient storage, adaptive compression, QUBO archive planning and combinations of these subjects.

Do not describe QBX V3 publicly as patented or patent-pending unless an actual filing has occurred and that wording is legally accurate.

# QBX 3.2 — Universal Archive Bridge

QBX 3.2 adds a bridge between the QBX format and common archive containers.

## The problem

Compressing a ZIP, 7z or RAR file as a single opaque byte stream usually provides little or no gain because the source is already compressed. QBX 3.2 can instead open the source container first and operate on the logical files inside it.

Example:

```text
already-compressed ZIP
        |
        v
Universal Archive Bridge
        |
        +--> logical files
               |
               +--> QBX: CDC -> SHA-256 -> dedup -> multi-codec -> Pareto -> AGRP -> ARK
               |
               +--> ZIP: standard Deflate
               +--> 7z : standard LZMA2
               +--> RAR: standard RAR5 through installed RAR/WinRAR
```

## Why this matters

If an existing ZIP contains duplicated or closely related files, feeding the ZIP bytes directly to another compressor hides those relationships. Decontainerization exposes the files again, allowing QBX content-defined chunking and global deduplication to operate across them.

This is a logical-content transformation. The newly created archive preserves the files stored inside the original container, not the byte-for-byte representation of the original ZIP/7z/RAR container itself.

## Output formats

### QBX

QBX remains the native format for the full technology stack:

- content-defined chunking;
- SHA-256 block identity;
- global deduplication;
- RAW/Zstandard/Deflate/LZMA representation candidates;
- Pareto pruning;
- AGRP global planning;
- ARK reversible repair relationships;
- authenticated recovery.

### ZIP

QBX can create a conventional ZIP/Deflate archive after optional decontainerization. The result is a normal ZIP intended for broad compatibility.

### 7z

QBX can create a conventional 7z archive using the py7zr implementation and LZMA2-compatible 7z semantics.

### RAR

QBX can create a standard RAR5 archive only when a compatible RAR/WinRAR executable is installed. QBX does not bundle or reimplement the proprietary RAR encoder.

The bridge can improve the *input preparation* before RAR compression by unpacking an already-compressed source container first. It does not inject AGRP or ARK metadata into a standard RAR file, because doing so would no longer be a conventional interoperable RAR archive.

## Safety

Before extracting ZIP and 7z sources, the bridge validates member paths and rejects traversal paths. RAR source listing is validated before extraction when an external RAR/WinRAR executable is used.

## CLI

```bash
qbx create output.qbx input.zip --format qbx
qbx create output.7z input.zip --format 7z
qbx create output.zip input.7z --format zip
qbx create output.rar input.zip --format rar
qbx formats
```

Use `--keep-source-container` if you intentionally want to store the compressed container itself rather than its logical contents.

## Claims boundary

QBX cannot guarantee that a standard RAR, ZIP or 7z output will always be smaller than the corresponding source. Compression depends on the data and the rules of the target format. The full QBX resilience model is available only in the QBX container.

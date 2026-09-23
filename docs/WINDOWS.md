# QBX 2.0 for Windows

QBX 2.0 is distributed in two Windows forms.

## Installer

`QBX-Setup-2.0.0.exe`

The installer places QBX under Program Files, creates a Start Menu shortcut, installs the command-line executable, and associates the `.qbx` extension with the graphical application.

The installer is currently **not code-signed**. Windows SmartScreen may therefore display an unknown-publisher warning.

## Portable

`QBX-Portable-2.0.0.zip`

Contains:

- `QBX.exe` — graphical application;
- `qbx-cli.exe` — command-line application.

No Python installation is required.

## QBX 2.0 adaptive mode

The default GUI profile is now `adaptive`, which runs AGRP:

1. content-defined chunking;
2. SHA-256 global deduplication;
3. multiple measured codec representations;
4. Pareto pruning;
5. bounded global goal-constrained planning;
6. verified QBX container creation.

The older `fast`, `balanced`, and `smallest` profiles remain available.

## Verification

The Windows build runs the Python tests, the QBX 2.0 reproducible benchmark, CLI smoke tests and a GUI self-test. It then produces `SHA256SUMS.txt` for the installer, portable archive and executables.

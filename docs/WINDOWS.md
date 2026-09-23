# QBX for Windows

QBX 1.0.0-rc1 is distributed in two Windows forms.

## Installer

`QBX-Setup-1.0.0-rc1.exe`

The installer places the application under Program Files, creates a Start Menu shortcut, installs the command-line executable, and associates the `.qbx` extension with the graphical QBX application.

The installer is currently **not code-signed**. Windows SmartScreen may therefore display an unknown-publisher warning.

## Portable

`QBX-Portable-1.0.0-rc1.zip`

Contains:

- `QBX.exe` — graphical application;
- `qbx-cli.exe` — command-line application.

No Python installation is required for either executable.

## Graphical application

The GUI can:

- select a file or folder;
- create a QBX archive;
- choose fast, balanced, or smallest profile;
- inspect an archive;
- verify every stored block and reconstructed file hash;
- extract an archive safely.

Double-clicking an associated `.qbx` file opens it in the GUI.

## Verification

The Windows build workflow produces `SHA256SUMS.txt` containing SHA-256 hashes of the installer, portable ZIP, and raw executables used during packaging.

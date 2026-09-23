# Security

QBX is still a release candidate. Do not use it as the only copy of important data.

The product engine validates extraction paths, rejects symlinks at pack time, refuses overwrites by default, bounds manifest/block sizes, uses atomic writes, and verifies SHA-256 at both block and reconstructed-file level.

Untrusted archives should still be treated as hostile input. Resource-exhaustion testing and fuzzing are required before the format should be considered hardened.

Please report security issues privately to the repository owner instead of publishing exploit details in a public issue.

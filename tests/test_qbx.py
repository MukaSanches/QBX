from qbx.core import pack, unpack, hexdigest

def test_roundtrip(tmp_path):
    src=tmp_path/"src"
    src.mkdir()
    data=(b"QBX"*100000)+(b"A"*200000)
    (src/"a.bin").write_bytes(data)
    (src/"b.bin").write_bytes(data)
    archive=tmp_path/"x.qbx"
    dst=tmp_path/"dst"

    stats=pack(str(src),str(archive))
    unpack(str(archive),str(dst))

    assert hexdigest((src/"a.bin").read_bytes()) == hexdigest((dst/"a.bin").read_bytes())
    assert hexdigest((src/"b.bin").read_bytes()) == hexdigest((dst/"b.bin").read_bytes())
    assert stats["deduplicated_chunks"] > 0


def test_unpack_rejects_path_traversal(tmp_path):
    import json
    import struct
    import pytest

    archive = tmp_path / "unsafe.qbx"
    manifest = {
        "format": "QBX",
        "version": 1,
        "files": [{
            "path": "../escape.txt",
            "size": 0,
            "sha256": hexdigest(b""),
            "blocks": [],
        }],
    }
    raw = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    with archive.open("wb") as f:
        f.write(b"QBX\x01")
        f.write(struct.pack(">Q", len(raw)))
        f.write(raw)
        f.write(struct.pack(">Q", 0))

    with pytest.raises(ValueError, match="Unsafe archive path"):
        unpack(str(archive), str(tmp_path / "out"))

from __future__ import annotations
import hashlib, json, lzma, os, struct, time, zlib
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

MAGIC = b"QBX\x01"
FORMAT_VERSION = 1

MIN_CHUNK = 32 * 1024
TARGET_CHUNK = 128 * 1024
MAX_CHUNK = 512 * 1024
MASK = TARGET_CHUNK - 1

def digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def hexdigest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def chunks(data: bytes):
    """Fast experimental content-defined chunking."""
    if not data:
        return
    start = 0
    fp = 0
    for i, b in enumerate(data):
        fp = ((fp << 1) ^ b ^ (fp >> 31)) & 0xffffffff
        n = i - start + 1
        if n >= MIN_CHUNK and ((fp & MASK) == 0 or n >= MAX_CHUNK):
            yield data[start:i+1]
            start = i + 1
            fp = 0
    if start < len(data):
        yield data[start:]

def entropy_sample(data: bytes) -> float:
    if not data: return 0.0
    sample = data if len(data) <= 16384 else data[::max(1,len(data)//16384)]
    counts = [0]*256
    for b in sample: counts[b] += 1
    import math
    n = len(sample)
    return -sum((c/n)*math.log2(c/n) for c in counts if c)

def candidates(data: bytes):
    e = entropy_sample(data)
    out = [("raw", data)]
    if e < 7.98:
        out.append(("zlib", zlib.compress(data, 9)))
        out.append(("lzma", lzma.compress(data, preset=6)))
    return out

def choose(data: bytes):
    opts = candidates(data)
    return min(opts, key=lambda x: len(x[1]))

def decode(codec: str, payload: bytes) -> bytes:
    if codec == "raw": return payload
    if codec == "zlib": return zlib.decompress(payload)
    if codec == "lzma": return lzma.decompress(payload)
    raise ValueError("Unsupported codec: " + codec)

@dataclass
class Block:
    codec: str
    usize: int
    payload: bytes

def pack(source: str, output: str):
    t0 = time.perf_counter()
    src = Path(source)
    root = src.parent if src.is_file() else src
    files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file())

    unique: dict[str, bytes] = {}
    entries = []
    original = 0
    logical_chunks = 0

    for p in files:
        data = p.read_bytes()
        original += len(data)
        ids = []
        for ch in chunks(data):
            logical_chunks += 1
            h = hexdigest(ch)
            ids.append(h)
            unique.setdefault(h, ch)
        entries.append({
            "path": str(p.relative_to(root)).replace("\\","/"),
            "size": len(data),
            "sha256": hexdigest(data),
            "blocks": ids
        })

    def work(item):
        h, data = item
        codec, payload = choose(data)
        return h, Block(codec, len(data), payload)

    workers = max(1, min(8, os.cpu_count() or 1))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        encoded = dict(ex.map(work, unique.items()))

    manifest = {
        "format":"QBX",
        "version":FORMAT_VERSION,
        "features":[
            "content-defined-chunking",
            "global-deduplication",
            "adaptive-codec-selection",
            "sha256-integrity",
            "random-block-addressing"
        ],
        "files":entries
    }
    m = json.dumps(manifest, separators=(",",":"), ensure_ascii=False).encode()

    with open(output, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack(">Q", len(m)))
        f.write(m)
        f.write(struct.pack(">Q", len(encoded)))
        for h, block in encoded.items():
            cb = block.codec.encode()
            f.write(bytes.fromhex(h))
            f.write(struct.pack("B", len(cb)))
            f.write(cb)
            f.write(struct.pack(">QQ", block.usize, len(block.payload)))
            f.write(block.payload)

    size = os.path.getsize(output)
    elapsed = time.perf_counter()-t0
    dedup_saved = logical_chunks-len(unique)
    return {
        "files":len(files),
        "original":original,
        "archive":size,
        "ratio":size/original if original else 0,
        "logical_chunks":logical_chunks,
        "unique_chunks":len(unique),
        "deduplicated_chunks":dedup_saved,
        "seconds":elapsed
    }

def unpack(archive: str, destination: str):
    t0 = time.perf_counter()
    with open(archive,"rb") as f:
        if f.read(4) != MAGIC: raise ValueError("Invalid QBX magic")
        mlen = struct.unpack(">Q",f.read(8))[0]
        manifest = json.loads(f.read(mlen))
        count = struct.unpack(">Q",f.read(8))[0]
        blocks={}
        for _ in range(count):
            h=f.read(32).hex()
            clen=struct.unpack("B",f.read(1))[0]
            codec=f.read(clen).decode()
            usize,csize=struct.unpack(">QQ",f.read(16))
            raw=decode(codec,f.read(csize))
            if len(raw)!=usize or hexdigest(raw)!=h:
                raise ValueError("QBX integrity failure")
            blocks[h]=raw

    dst=Path(destination).resolve()
    for e in manifest["files"]:
        target=(dst/e["path"]).resolve()
        if target != dst and dst not in target.parents:
            raise ValueError("Unsafe archive path: "+e["path"])
        target.parent.mkdir(parents=True,exist_ok=True)
        data=b"".join(blocks[h] for h in e["blocks"])
        if len(data)!=e["size"] or hexdigest(data)!=e["sha256"]:
            raise ValueError("File reconstruction failure: "+e["path"])
        target.write_bytes(data)

    return {"files":len(manifest["files"]), "seconds":time.perf_counter()-t0}

from __future__ import annotations

import os
import random
import zipfile
from pathlib import Path

import py7zr
import pytest

from qbx.api import pack as pack_qbx, unpack as unpack_qbx
from qbx.bridge import create_archive, output_capabilities
from qbx.core import QBXError


def test_optimized_zip_to_qbx_decontainerizes_and_deduplicates(tmp_path: Path) -> None:
    rng = random.Random(20260923)
    payload = rng.randbytes(256 * 1024)

    source_zip = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(
        source_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        zf.writestr("a.bin", payload)
        zf.writestr("b.bin", payload)

    direct = tmp_path / "direct.qbx"
    optimized = tmp_path / "optimized.qbx"

    direct_result = pack_qbx(source_zip, direct, profile="resilient", repair_budget_pct=0.0)
    optimized_result = create_archive(
        [source_zip],
        optimized,
        output_format="qbx",
        optimize_source_archives=True,
        qbx_profile="resilient",
        repair_budget_pct=0.0,
    )

    assert direct_result["ok"] is True
    assert optimized_result["ok"] is True
    assert optimized_result["optimized_source_archives"] == 1
    assert optimized_result["source_containers"] == ["zip"]
    assert optimized.stat().st_size < direct.stat().st_size

    restored = tmp_path / "restored"
    unpack_qbx(optimized, restored)
    assert (restored / "a.bin").read_bytes() == payload
    assert (restored / "b.bin").read_bytes() == payload


def test_create_standard_zip_from_folder(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("QBX bridge\n" * 1000, encoding="utf-8")

    output = tmp_path / "out.zip"
    result = create_archive([src], output, output_format="zip")

    assert result["ok"] is True
    assert result["output_format"] == "zip"
    assert result["qbx_resilience_embedded"] is False

    with zipfile.ZipFile(output) as zf:
        assert zf.read("hello.txt") == (src / "hello.txt").read_bytes()


def test_create_standard_7z_from_folder(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("QBX 7z bridge\n" * 1000, encoding="utf-8")

    output = tmp_path / "out.7z"
    result = create_archive([src], output, output_format="7z")

    assert result["ok"] is True
    assert result["output_format"] == "7z"

    extracted = tmp_path / "7z-out"
    extracted.mkdir()
    with py7zr.SevenZipFile(output, "r") as archive:
        archive.extractall(path=extracted)
    assert (extracted / "hello.txt").read_bytes() == (src / "hello.txt").read_bytes()


def test_zip_path_traversal_is_rejected(tmp_path: Path) -> None:
    source_zip = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(source_zip, "w") as zf:
        zf.writestr("../escape.txt", b"no")

    with pytest.raises(QBXError):
        create_archive(
            [source_zip],
            tmp_path / "unsafe.qbx",
            output_format="qbx",
            optimize_source_archives=True,
        )


def test_rar_capability_is_explicit() -> None:
    cap = output_capabilities()["rar"]
    assert isinstance(cap["available"], bool)
    assert "RAR" in cap["label"].upper()
    if cap["available"]:
        assert cap["executable"]
    else:
        assert cap["executable"] is None

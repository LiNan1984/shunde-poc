# -*- coding: utf-8 -*-
"""Ingest one native-text PDF from the bank-provided zip (evidence, not a unit-test gate)."""

from __future__ import annotations

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path

from pypdf import PdfReader

from .ingest import ingest_pdf
from .stores import store_root

SKIP_HINTS = ("年鉴", "CMF", "中国统计")


def decode_zip_name(info: zipfile.ZipInfo) -> str:
    """CP437 → UTF-8 (flag bit 11 already UTF-8)."""
    if info.flag_bits & 0x800:
        return info.filename
    raw = info.filename.encode("cp437")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", errors="replace")


def pick_native_pdf(zip_path: Path) -> tuple[zipfile.ZipInfo, str] | None:
    with zipfile.ZipFile(zip_path) as zf:
        candidates: list[tuple[int, zipfile.ZipInfo, str]] = []
        for info in zf.infolist():
            name = decode_zip_name(info)
            if info.is_dir() or not name.lower().endswith(".pdf"):
                continue
            if any(hint in name for hint in SKIP_HINTS):
                continue
            if "/." in name or name.startswith("__MACOSX"):
                continue
            candidates.append((info.file_size, info, name))
        candidates.sort()
        for _size, info, name in candidates:
            try:
                data = zf.read(info.filename)
            except KeyError:
                continue
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                    tmp.write(data)
                    tmp.flush()
                    text = PdfReader(tmp.name).pages[0].extract_text() or ""
            except Exception:
                text = ""
            if len(text.strip()) >= 20:
                return info, name
    return None


def ingest_native_sample(
    zip_path: str,
    *,
    max_pages: int = 2,
    dest_dir: Path | None = None,
) -> dict:
    path = Path(zip_path)
    if not path.is_file():
        return {
            "ok": False,
            "message": f"zip 不存在 / zip missing: {zip_path}",
            "n_chunks": 0,
        }
    picked = pick_native_pdf(path)
    if picked is None:
        return {
            "ok": False,
            "message": "zip 内没有可抽取原生文本的 PDF / no native-text PDF in zip",
            "n_chunks": 0,
        }
    info, name = picked
    root, err = store_root()
    if err or root is None:
        return {**(err or {"ok": False, "message": "workspace unavailable"}), "n_chunks": 0}
    out_dir = dest_dir or (root / "bank_samples")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / Path(name).name
    with zipfile.ZipFile(path) as zf:
        dest.write_bytes(zf.read(info.filename))
    result = ingest_pdf(str(dest), max_pages=max_pages)
    result["source_zip"] = str(path)
    result["source_member"] = name
    result["extracted_to"] = str(dest)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest one native-text PDF from the bank zip")
    parser.add_argument("zip_path")
    parser.add_argument("--max-pages", type=int, default=2)
    args = parser.parse_args(argv)
    result = ingest_native_sample(args.zip_path, max_pages=args.max_pages)
    print(result.get("message") or result)
    if result.get("ok"):
        print(
            f"doc_id={result.get('doc_id')} n_chunks={result.get('n_chunks')} "
            f"n_pages={result.get('n_pages')} source={result.get('source_member')}"
        )
        return 0
    print(result, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

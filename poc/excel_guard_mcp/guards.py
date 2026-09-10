# -*- coding: utf-8 -*-
"""Excel anomaly guards for POC demo: corrupt / encoding / large-sheet chunking."""

from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path
from typing import Any

import chardet
from openpyxl import load_workbook

# --- Limits (configurable via env vars) ---------------------------------------

# Max bytes fed to chardet (avoid OOM on huge CSV before chunking).
_ENCODING_SAMPLE_BYTES = 1 << 20  # 1 MiB
_ENCODING_HARD_LIMIT = 32 << 20  # 32 MiB — refuse full detect beyond this

# Max file size before we refuse to open as a workbook (DoS protection).
_MAX_FILE_BYTES = int(os.environ.get("POC_EXCEL_MAX_BYTES", 200 * 1024 * 1024))  # 200 MiB
_MAX_ZIP_ENTRIES = int(os.environ.get("POC_EXCEL_MAX_ZIP_ENTRIES", 10_000))

# Chunk limits
_MAX_ROWS_CEILING = 1_000_000
_MAX_CHUNKS = 10_000

# Suffix sets
_XLSX_SUFFIXES = {".xlsx", ".xlsm", ".xltx", ".xltm"}
_TEXT_SUFFIXES = {".csv", ".txt", ".tsv"}

logger = logging.getLogger("poc.excel_guard")


# --- Sandbox ------------------------------------------------------------------

def _workspace_root() -> Path:
    raw = os.environ.get("POC_WORKSPACE") or os.environ.get("QWENPAW_WORKING_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    # Default: repository root (parent of poc/)
    return Path(__file__).resolve().parents[2]


def _resolve_allowed_path(path: Any) -> tuple[Path | None, dict | None]:
    """Resolve path and enforce workspace sandbox.

    Returns (path, None) on success, or (None, error_dict) on denial/missing shape.
    error_dict uses ok/issue/message keys for corrupt-style callers; encoding/chunk
    callers remap as needed.
    """
    # Validate input type up front (M7)
    if not isinstance(path, str):
        return None, {
            "ok": False,
            "issue": "invalid_path",
            "message": "路径必须为字符串 / path must be a string",
        }
    if not path.strip():
        return None, {
            "ok": False,
            "issue": "invalid_path",
            "message": "路径不能为空 / path must not be empty",
        }

    root = _workspace_root()
    try:
        file_path = Path(path).expanduser().resolve(strict=False)
    except (OSError, ValueError) as exc:
        # ValueError catches embedded null bytes on some platforms
        logger.warning("path resolve failed: %s", exc)
        return None, {
            "ok": False,
            "issue": "path_denied",
            "message": f"路径无法解析 / Cannot resolve path: {exc}",
        }

    try:
        if not file_path.is_relative_to(root):
            logger.warning("path outside workspace: %s", path)
            return None, {
                "ok": False,
                "issue": "path_denied",
                "message": (
                    f"路径越界 / Path outside workspace root ({root}): {path}"
                ),
            }
    except AttributeError:
        # Python < 3.9 fallback — not expected on 3.13+
        if root not in file_path.parents and file_path != root:
            logger.warning("path outside workspace: %s", path)
            return None, {
                "ok": False,
                "issue": "path_denied",
                "message": (
                    f"路径越界 / Path outside workspace root ({root}): {path}"
                ),
            }

    try:
        is_symlink = file_path.is_symlink()
    except OSError as exc:
        logger.warning("symlink check failed: %s", exc)
        return None, {
            "ok": False,
            "issue": "path_denied",
            "message": f"路径无法访问 / Cannot access path: {exc}",
        }

    if is_symlink:
        try:
            real = file_path.resolve(strict=True)
            if not real.is_relative_to(root):
                logger.warning("symlink escapes workspace: %s", path)
                return None, {
                    "ok": False,
                    "issue": "path_denied",
                    "message": (
                        f"符号链接越界 / Symlink escapes workspace: {path}"
                    ),
                }
            file_path = real
        except OSError as exc:
            return None, {
                "ok": False,
                "issue": "path_denied",
                "message": f"符号链接无效 / Invalid symlink: {exc}",
            }

    return file_path, None


def _safe_name(file_path: Path) -> str:
    """Return a sanitized filename safe for interpolation into messages."""
    name = file_path.name
    # Strip control characters to prevent prompt-injection via crafted filenames
    return "".join(c for c in name if c.isprintable())


def _check_file_size(file_path: Path) -> dict | None:
    """Return error dict if file exceeds size limit, None otherwise."""
    try:
        size = file_path.stat().st_size
    except OSError as exc:
        return {
            "ok": False,
            "issue": "unreadable",
            "message": f"无法读取文件 / Cannot read file: {exc}",
        }
    if size > _MAX_FILE_BYTES:
        return {
            "ok": False,
            "issue": "too_large",
            "message": (
                f"文件过大 / File too large: {_safe_name(file_path)} "
                f"({size} bytes > {_MAX_FILE_BYTES})。请先拆分或压缩。"
            ),
        }
    return None


# --- detect_corrupt_workbook --------------------------------------------------

def detect_corrupt_workbook(path: str) -> dict:
    """Detect whether an Excel workbook is corrupt or unreadable.

    For CSV / text files, returns ok=True if the file is readable (not a
    corruption check, just a pass-through so the rest of the pipeline works).

    Returns:
        {"ok": bool, "issue": str, "message": str}
    """
    file_path, err = _resolve_allowed_path(path)
    if err is not None:
        return err

    if file_path is None:
        return err

    if not file_path.exists():
        return {
            "ok": False,
            "issue": "missing",
            "message": (
                f"文件不存在 / File not found: {path}。"
                "请确认路径是否正确。"
            ),
        }

    if file_path.is_dir():
        return {
            "ok": False,
            "issue": "invalid_path",
            "message": (
                f"路径是目录，不是文件 / Path is a directory, not a file: "
                f"{_safe_name(file_path)}"
            ),
        }

    size_err = _check_file_size(file_path)
    if size_err is not None:
        return size_err

    suffix = file_path.suffix.lower()

    # CSV / text: readable is fine; encoding check is a separate tool (H2 fix)
    if suffix in _TEXT_SUFFIXES:
        try:
            with file_path.open("rb") as fh:
                fh.read(1)  # confirm readable
        except OSError as exc:
            return {
                "ok": False,
                "issue": "unreadable",
                "message": f"文件无法读取 / Cannot read file: {exc}",
            }
        return {
            "ok": True,
            "issue": "",
            "message": (
                f"文本文件可读 / Text file readable: {_safe_name(file_path)}。"
                "建议调用 detect_encoding 确认编码。"
            ),
        }

    # Legacy .xls: explicitly unsupported (not "corrupt")
    if suffix in {".xls", ".xla", ".xlt"}:
        return {
            "ok": False,
            "issue": "unsupported",
            "message": (
                f"旧版 Excel 格式不支持 / Legacy .xls format not supported: "
                f"{_safe_name(file_path)}。请另存为 .xlsx 后再试。"
            ),
        }

    # OOXML formats: full check
    if suffix in _XLSX_SUFFIXES:
        try:
            if not zipfile.is_zipfile(file_path):
                return {
                    "ok": False,
                    "issue": "corrupt",
                    "message": (
                        "检测到损坏的 Excel 工作簿 / Corrupt workbook detected: "
                        f"{_safe_name(file_path)}。文件不是有效的 Office Open XML (ZIP) 包，"
                        "无法用 openpyxl 打开。请重新导出或修复后再试。"
                    ),
                }
            with zipfile.ZipFile(file_path, "r") as zf:
                entries = zf.infolist()
                if len(entries) > _MAX_ZIP_ENTRIES:
                    return {
                        "ok": False,
                        "issue": "unsafe_archive",
                        "message": (
                            f"ZIP 条目过多 / Too many ZIP entries: "
                            f"{len(entries)} > {_MAX_ZIP_ENTRIES}。"
                            "文件可能异常，请检查来源。"
                        ),
                    }
                names = zf.namelist()
                if "[Content_Types].xml" not in names:
                    return {
                        "ok": False,
                        "issue": "corrupt",
                        "message": (
                            "检测到损坏的 Excel 工作簿 / Corrupt workbook detected: "
                            f"{_safe_name(file_path)}。ZIP 包缺少 [Content_Types].xml，"
                            "结构不完整。请重新导出或修复后再试。"
                        ),
                    }
            load_workbook(file_path, read_only=True, data_only=True).close()
        except MemoryError:
            return {
                "ok": False,
                "issue": "too_large",
                "message": (
                    "文件解析内存不足 / Out of memory while parsing: "
                    f"{_safe_name(file_path)}。请减小文件大小后再试。"
                ),
            }
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            return {
                "ok": False,
                "issue": "corrupt",
                "message": (
                    "检测到损坏的 Excel 工作簿 / Corrupt workbook detected: "
                    f"{_safe_name(file_path)}。解析失败：{type(exc).__name__}。"
                    "请重新导出或修复后再试。"
                ),
            }
        except OSError as exc:
            return {
                "ok": False,
                "issue": "unreadable",
                "message": f"文件无法读取 / Cannot read file: {exc}",
            }
        except Exception as exc:  # noqa: BLE001 - last-resort catch for openpyxl
            logger.warning("unexpected workbook open failure: %s", exc)
            return {
                "ok": False,
                "issue": "corrupt",
                "message": (
                    "检测到损坏或不支持的 Excel 工作簿 / Corrupt or unsupported workbook: "
                    f"{_safe_name(file_path)}。打开失败：{type(exc).__name__}。"
                    "请重新导出或修复后再试。"
                ),
            }
        return {
            "ok": True,
            "issue": "",
            "message": f"工作簿正常 / Workbook OK: {_safe_name(file_path)}",
        }

    # Unknown extension
    return {
        "ok": False,
        "issue": "unsupported",
        "message": (
            f"不支持的文件格式 / Unsupported file format: {suffix}。"
            "请使用 .xlsx / .xlsm / .csv 等支持的格式。"
        ),
    }


# --- detect_encoding ----------------------------------------------------------

def detect_encoding(path: str) -> dict:
    """Detect text/CSV encoding with chardet; describe xlsx as zip/utf-8 internals.

    Returns:
        {"encoding": str, "confidence": float, "message": str}
    """
    file_path, err = _resolve_allowed_path(path)
    if err is not None:
        return {
            "encoding": "unknown",
            "confidence": 0.0,
            "message": err["message"],
        }

    if file_path is None:
        return {
            "encoding": "unknown",
            "confidence": 0.0,
            "message": "路径无效 / Invalid path",
        }

    if not file_path.exists():
        return {
            "encoding": "unknown",
            "confidence": 0.0,
            "message": f"文件不存在 / File not found: {path}",
        }

    suffix = file_path.suffix.lower()
    if suffix in _XLSX_SUFFIXES:
        is_zip = zipfile.is_zipfile(file_path)
        return {
            "encoding": "utf-8",
            "confidence": 1.0 if is_zip else 0.0,
            "message": (
                f"XLSX 为 ZIP 包，内部 XML 通常为 UTF-8 / "
                f"XLSX is a ZIP package with UTF-8 XML internals: "
                f"{_safe_name(file_path)}。"
                + (
                    "可直接用 openpyxl/pandas 读取。"
                    if is_zip
                    else "但当前文件不是有效 ZIP，请先做损坏检测。"
                )
            ),
        }

    size = file_path.stat().st_size
    if size == 0:
        return {
            "encoding": "utf-8",
            "confidence": 0.0,
            "message": f"空文件 / Empty file: {_safe_name(file_path)}",
        }

    # Always sample first MiB; remove the hard "refuse" behavior (M4 fix)
    sample_size = min(_ENCODING_SAMPLE_BYTES, size)
    sampled_only = size > _ENCODING_SAMPLE_BYTES

    try:
        with file_path.open("rb") as fh:
            raw = fh.read(sample_size)
    except OSError as exc:
        return {
            "encoding": "unknown",
            "confidence": 0.0,
            "message": f"文件无法读取 / Cannot read file: {exc}",
        }

    detected = chardet.detect(raw) or {}
    encoding = (detected.get("encoding") or "unknown").lower()
    confidence = float(detected.get("confidence") or 0.0)

    if encoding in {"ascii", "utf-8", "utf8"}:
        # Validate on the sample only; full-file validation is caller's choice
        try:
            raw.decode("utf-8")
            return {
                "encoding": "utf-8" if encoding != "ascii" else "ascii",
                "confidence": confidence,
                "message": (
                    f"文本编码正常 / Encoding OK ({encoding}, confidence={confidence:.2f}): "
                    f"{_safe_name(file_path)}"
                    + ("（仅采样前 1 MiB / sampled first 1 MiB）" if sampled_only else "")
                ),
            }
        except UnicodeDecodeError:
            pass

    if confidence < 0.5:
        tip = (
            f"编码置信度偏低 / Low-confidence encoding guess: {encoding} "
            f"(confidence={confidence:.2f})，文件：{_safe_name(file_path)}。"
            "建议按 latin-1/gbk 尝试转码为 UTF-8 后再读取，勿直接当 UTF-8 打开。"
        )
    else:
        tip = (
            f"检测到非 UTF-8 编码 / Non-UTF-8 encoding detected: {encoding} "
            f"(confidence={confidence:.2f})，文件：{_safe_name(file_path)}。"
            "读取 CSV/文本前请先转码为 UTF-8，否则中文或特殊字符可能乱码。"
        )
    if sampled_only:
        tip += "（仅采样前 1 MiB / sampled first 1 MiB）"

    return {
        "encoding": encoding,
        "confidence": confidence,
        "message": tip,
    }


# --- chunk_large_workbook -----------------------------------------------------

def chunk_large_workbook(path: str, max_rows: int = 5000) -> dict:
    """Plan row-range chunks when a workbook sheet exceeds max_rows.

    Returns:
        {
            "needs_chunking": bool,
            "total_rows": int,
            "chunks": list[{"start_row": int, "end_row": int, "sheet": str}],
            "message": str,
        }
    """
    file_path, err = _resolve_allowed_path(path)
    if err is not None:
        return {
            "needs_chunking": False,
            "total_rows": 0,
            "max_sheet_rows": 0,
            "chunks": [],
            "message": err["message"],
        }

    if file_path is None:
        return {
            "needs_chunking": False,
            "total_rows": 0,
            "max_sheet_rows": 0,
            "chunks": [],
            "message": "路径无效 / Invalid path",
        }

    if not file_path.exists():
        return {
            "needs_chunking": False,
            "total_rows": 0,
            "max_sheet_rows": 0,
            "chunks": [],
            "message": f"文件不存在 / File not found: {path}",
        }

    if max_rows < 1:
        return {
            "needs_chunking": False,
            "total_rows": 0,
            "max_sheet_rows": 0,
            "chunks": [],
            "message": "max_rows 必须 >= 1 / max_rows must be >= 1",
        }
    if max_rows > _MAX_ROWS_CEILING:
        return {
            "needs_chunking": False,
            "total_rows": 0,
            "max_sheet_rows": 0,
            "chunks": [],
            "message": (
                f"max_rows 过大 / max_rows too large: {max_rows} > {_MAX_ROWS_CEILING}。"
                "请减小 max_rows 或先筛选数据。"
            ),
        }

    size_err = _check_file_size(file_path)
    if size_err is not None:
        return {
            "needs_chunking": False,
            "total_rows": 0,
            "max_sheet_rows": 0,
            "chunks": [],
            "message": size_err["message"],
        }

    try:
        wb = load_workbook(file_path, read_only=True, data_only=True)
    except MemoryError:
        return {
            "needs_chunking": False,
            "total_rows": 0,
            "max_sheet_rows": 0,
            "chunks": [],
            "message": "文件解析内存不足 / Out of memory while parsing workbook",
        }
    except (OSError, ValueError) as exc:
        return {
            "needs_chunking": False,
            "total_rows": 0,
            "max_sheet_rows": 0,
            "chunks": [],
            "message": (
                "无法打开工作簿做分块 / Cannot open workbook for chunking: "
                f"{type(exc).__name__}"
            ),
        }
    except Exception as exc:  # noqa: BLE001 - last-resort
        logger.warning("unexpected chunk open failure: %s", exc)
        return {
            "needs_chunking": False,
            "total_rows": 0,
            "max_sheet_rows": 0,
            "chunks": [],
            "message": (
                "无法打开工作簿做分块 / Cannot open workbook for chunking: "
                f"{type(exc).__name__}"
            ),
        }

    chunks: list[dict] = []
    max_sheet_rows = 0
    try:
        for sheet in wb.worksheets:
            sheet_rows = int(sheet.max_row or 0)
            max_sheet_rows = max(max_sheet_rows, sheet_rows)
            if sheet_rows <= max_rows:
                continue
            start = 1
            while start <= sheet_rows:
                if len(chunks) >= _MAX_CHUNKS:
                    break
                end = min(start + max_rows - 1, sheet_rows)
                chunks.append(
                    {
                        "start_row": start,
                        "end_row": end,
                        "sheet": sheet.title,
                    }
                )
                start = end + 1
    finally:
        wb.close()

    needs_chunking = max_sheet_rows > max_rows
    if needs_chunking:
        if len(chunks) >= _MAX_CHUNKS:
            message = (
                f"分块数量达上限 / Chunk count capped at {_MAX_CHUNKS}: "
                f"max_sheet_rows={max_sheet_rows}, max_rows={max_rows}。"
                "请先筛选数据减小范围。"
            )
        else:
            message = (
                f"工作表行数过大，需要分块处理 / Large sheet needs chunking: "
                f"max_sheet_rows={max_sheet_rows} > max_rows={max_rows}，"
                f"已生成 {len(chunks)} 个分块范围。"
            )
    else:
        message = (
            f"行数未超限，无需分块 / No chunking needed: "
            f"max_sheet_rows={max_sheet_rows} <= max_rows={max_rows}"
        )
        chunks = []

    return {
        "needs_chunking": needs_chunking,
        "total_rows": max_sheet_rows,
        "max_sheet_rows": max_sheet_rows,
        "chunks": chunks,
        "message": message,
    }

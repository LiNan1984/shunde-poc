# -*- coding: utf-8 -*-
"""Excel anomaly guards for POC demo: corrupt / encoding / large-sheet chunking."""

from __future__ import annotations

import errno
import io
import logging
import os
import stat
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

# Race-free open flags (H1):
#   O_NOFOLLOW - the opened path component must never itself be a symlink at
#                the instant of the open(2) call (atomic in the kernel).
#   O_NONBLOCK - a FIFO/device placed in the workspace cannot block the open;
#                the fstat regular-file check below rejects it anyway.
#   O_CLOEXEC  - do not leak the descriptor into child processes.
# Intermediate directories are pinned via openat(dir_fd=...) so a symlink
# swapped into a path component *after* resolve() makes the next open fail
# with ELOOP instead of being followed outside the sandbox (TOCTOU).
_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW
if hasattr(os, "O_NONBLOCK"):
    _OPEN_FLAGS |= os.O_NONBLOCK
if hasattr(os, "O_CLOEXEC"):
    _OPEN_FLAGS |= os.O_CLOEXEC
_DIR_OPEN_FLAGS = _OPEN_FLAGS | os.O_DIRECTORY

# Roots for which the "sandbox active" audit line was already emitted (stderr).
_LOGGED_ROOTS: set[str] = set()


def _safe_name(file_path: Path) -> str:
    """Return a sanitized filename safe for interpolation into messages."""
    name = file_path.name
    # Strip control characters to prevent prompt-injection via crafted filenames
    return "".join(c for c in name if c.isprintable())


def _workspace_root() -> tuple[Path | None, dict | None]:
    """Return the validated sandbox root, or (None, error_dict).

    Fail-closed (M1): a configured root that is missing, not a directory, or
    the filesystem root '/' denies *every* operation instead of silently
    treating the whole filesystem as the workspace. With no env configured we
    fall back to the repository checkout root (always a real directory).
    """
    raw = os.environ.get("POC_WORKSPACE") or os.environ.get("QWENPAW_WORKING_DIR")
    if raw:
        try:
            root = Path(raw).expanduser().resolve()
        except (OSError, ValueError) as exc:
            logger.error("invalid POC_WORKSPACE value %r: %s", raw, exc)
            return None, {
                "ok": False,
                "issue": "workspace_invalid",
                "message": (
                    "沙箱根目录无效 / Invalid workspace root: "
                    f"路径无法解析 / Cannot resolve: {exc}（fail-closed 拒绝）。"
                ),
            }
        if str(root) == os.sep:
            logger.error(
                "workspace root rejected: filesystem root '/' is forbidden (fail-closed)"
            )
            return None, {
                "ok": False,
                "issue": "workspace_invalid",
                "message": (
                    "沙箱根目录无效 / Invalid workspace root: "
                    "不能使用文件系统根目录 '/'（等于关闭沙箱，fail-closed 拒绝）。"
                    "请把 POC_WORKSPACE 设置为专用工作目录。"
                ),
            }
        if not root.is_dir():
            logger.error(
                "workspace root rejected: not an existing directory: %s", raw
            )
            return None, {
                "ok": False,
                "issue": "workspace_invalid",
                "message": (
                    "沙箱根目录无效 / Invalid workspace root: "
                    f"目录不存在或不是目录 / not an existing directory: {raw}。"
                    "请检查 POC_WORKSPACE 配置（fail-closed 拒绝）。"
                ),
            }
    else:
        # Default: repository root (parent of poc/)
        root = Path(__file__).resolve().parents[2]
        if not root.is_dir():
            logger.error("default workspace root missing: %s", root)
            return None, {
                "ok": False,
                "issue": "workspace_invalid",
                "message": (
                    "沙箱根目录无效 / Invalid workspace root: "
                    f"默认根目录不存在 / default root missing: {root}。"
                ),
            }

    key = str(root)
    if key not in _LOGGED_ROOTS:
        # Audit marker. stderr ONLY — stdout is the MCP JSON-RPC channel (red line 4).
        logger.warning("sandbox workspace root active: %s", root)
        _LOGGED_ROOTS.add(key)
    return root, None


def _resolve_allowed_path(path: Any) -> tuple[Path | None, dict | None]:
    """Resolve path and enforce workspace sandbox containment.

    Returns (resolved_path, None) on success, or (None, error_dict) on
    denial/invalid input. The returned path has only been *lexically*
    validated; reading MUST go through ``_open_contained`` so that a symlink
    swapped in after this check cannot redirect the actual open (H1).
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

    root, root_err = _workspace_root()
    if root_err is not None:
        return None, root_err
    assert root is not None

    try:
        # strict=False: dangling links/loops keep an unresolved tail; the
        # openat+O_NOFOLLOW walk in _open_contained classifies them safely.
        file_path = Path(path).expanduser().resolve(strict=False)
    except (OSError, ValueError) as exc:
        # ValueError catches embedded null bytes on some platforms
        logger.warning("path resolve failed: %s", exc)
        return None, {
            "ok": False,
            "issue": "path_denied",
            "message": f"路径无法解析 / Cannot resolve path: {exc}",
        }

    if not file_path.is_relative_to(root):
        logger.warning("path outside workspace: %s", path)
        return None, {
            "ok": False,
            "issue": "path_denied",
            "message": (
                f"路径越界 / Path outside workspace root ({root}): {path}"
            ),
        }

    return file_path, None


def _classify_open_error(exc: OSError, file_path: Path) -> dict:
    """Map a safe-open OSError to the structured error shape."""
    name = _safe_name(file_path)
    if isinstance(exc, FileNotFoundError):
        return {
            "ok": False,
            "issue": "missing",
            "message": f"文件不存在 / File not found: {name}",
        }
    if isinstance(exc, IsADirectoryError) or exc.errno == errno.EISDIR:
        return {
            "ok": False,
            "issue": "invalid_path",
            "message": (
                "路径是目录，不是文件 / Path is a directory, not a file: "
                f"{name}"
            ),
        }
    if exc.errno == errno.ELOOP:
        return {
            "ok": False,
            "issue": "path_denied",
            "message": (
                "符号链接被拒绝 / Symlink rejected at open (O_NOFOLLOW): "
                f"{name}。路径可能在检查后被替换，已按 TOCTOU 防护拒绝。"
            ),
        }
    return {
        "ok": False,
        "issue": "unreadable",
        "message": f"文件无法读取 / Cannot read file: {exc}",
    }


class _NoClose:
    """Proxy over a binary file object whose ``close()`` is a no-op.

    ``zipfile.ZipFile.close()`` (and openpyxl through its archive) always
    closes the wrapped stream. The guard pipeline opens a SINGLE descriptor
    (is_zipfile -> ZipFile -> openpyxl, H1), so consumers must not close the
    underlying fd; the owning function closes it in a ``finally`` block.
    """

    def __init__(self, fh: io.BufferedReader) -> None:
        self._fh = fh

    def close(self) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fh, name)


def _open_contained(
    file_path: Path,
) -> tuple[io.BufferedReader | None, dict | None]:
    """Open a resolved, containment-checked path with one race-free fd.

    Walk from the sandbox-root directory fd with openat(2): every
    intermediate component is opened O_NOFOLLOW|O_DIRECTORY and pinned by fd
    (renaming/swapping an ancestor afterwards cannot affect the walk), and
    the final component is opened O_RDONLY|O_NOFOLLOW so a final-component
    symlink — including one swapped in between resolve() and this open —
    fails with ELOOP instead of being followed. The returned fd is then
    fstat-checked to be a regular file. Caller owns (and must close) the
    returned file object.
    """
    root, root_err = _workspace_root()
    if root_err is not None:
        return None, root_err
    assert root is not None

    try:
        rel = file_path.relative_to(root)
    except ValueError:
        logger.warning("open rejected: path outside workspace: %s", file_path)
        return None, {
            "ok": False,
            "issue": "path_denied",
            "message": (
                f"路径越界 / Path outside workspace root ({root}): {file_path}"
            ),
        }

    parts = rel.parts
    if not parts:
        return None, {
            "ok": False,
            "issue": "invalid_path",
            "message": "路径是目录，不是文件 / Path is a directory, not a file.",
        }

    dir_fds: list[int] = []
    file_fd = -1
    try:
        anchor = os.open(root, _DIR_OPEN_FLAGS)
        dir_fds.append(anchor)
        for name in parts[:-1]:
            dfd = os.open(name, _DIR_OPEN_FLAGS, dir_fd=dir_fds[-1])
            dir_fds.append(dfd)
        file_fd = os.open(parts[-1], _OPEN_FLAGS, dir_fd=dir_fds[-1])

        st = os.fstat(file_fd)
        if stat.S_ISDIR(st.st_mode):
            return None, {
                "ok": False,
                "issue": "invalid_path",
                "message": (
                    "路径是目录，不是文件 / Path is a directory, not a file: "
                    f"{_safe_name(file_path)}"
                ),
            }
        if not stat.S_ISREG(st.st_mode):
            # FIFO / socket / device — O_NONBLOCK kept the open from hanging.
            return None, {
                "ok": False,
                "issue": "invalid_path",
                "message": (
                    "非常规文件，拒绝读取 / Not a regular file, refused: "
                    f"{_safe_name(file_path)}"
                ),
            }

        fh = os.fdopen(file_fd, "rb")
        file_fd = -1  # fdopen took ownership
        return fh, None
    except OSError as exc:
        err = _classify_open_error(exc, file_path)
        logger.warning("safe open denied (%s): %s", err["issue"], exc)
        return None, err
    finally:
        if file_fd != -1:
            try:
                os.close(file_fd)
            except OSError:
                pass
        for dfd in reversed(dir_fds):
            try:
                os.close(dfd)
            except OSError:
                pass


def _oversize_error(size: int, file_path: Path) -> dict | None:
    """Return the too_large error dict if size exceeds the limit."""
    if size <= _MAX_FILE_BYTES:
        return None
    return {
        "ok": False,
        "issue": "too_large",
        "message": (
            f"文件过大 / File too large: {_safe_name(file_path)} "
            f"({size} bytes > {_MAX_FILE_BYTES})。请先拆分或压缩。"
        ),
    }


def _check_file_size(file_path: Path) -> dict | None:
    """Pre-open size estimate via lstat (no symlink follow — TOCTOU-safe)."""
    try:
        size = file_path.lstat().st_size
    except OSError as exc:
        return {
            "ok": False,
            "issue": "unreadable",
            "message": f"无法读取文件 / Cannot read file: {exc}",
        }
    return _oversize_error(size, file_path)


def _check_fh_size(fh: io.BufferedReader, file_path: Path) -> dict | None:
    """Authoritative limit check against the OPENED inode (fstat, swap-proof)."""
    try:
        size = os.fstat(fh.fileno()).st_size
    except OSError as exc:
        return {
            "ok": False,
            "issue": "unreadable",
            "message": f"无法读取文件 / Cannot read file: {exc}",
        }
    return _oversize_error(size, file_path)


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

    if file_path.is_dir():
        return {
            "ok": False,
            "issue": "invalid_path",
            "message": (
                f"路径是目录，不是文件 / Path is a directory, not a file: "
                f"{_safe_name(file_path)}"
            ),
        }

    # Use lstat so symlink-loops/dangling links are seen as present;
    # subsequent O_NOFOLLOW open classifies ELOOP/ENOENT correctly.
    try:
        file_path.lstat()
    except OSError as exc:
        return {
            "ok": False,
            "issue": "missing",
            "message": (
                f"文件不存在 / File not found: {path}。"
                "请确认路径是否正确。"
            ),
        } if isinstance(exc, FileNotFoundError) else {
            "ok": False,
            "issue": "unreadable",
            "message": f"无法读取文件 / Cannot read file: {exc}",
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

    # OOXML formats: full check (TOCTOU-safe: open via _open_contained)
    if suffix in _XLSX_SUFFIXES:
        fh, open_err = _open_contained(file_path)
        if open_err is not None:
            return open_err
        assert fh is not None
        try:
            try:
                head = fh.read(4)
            except OSError as exc:
                return _classify_open_error(exc, file_path)
            if head[:4] != b"PK\x03\x04":
                return {
                    "ok": False,
                    "issue": "corrupt",
                    "message": (
                        "检测到损坏的 Excel 工作簿 / Corrupt workbook detected: "
                        f"{_safe_name(file_path)}。文件不是有效的 Office Open XML (ZIP) 包，"
                        "无法用 openpyxl 打开。请重新导出或修复后再试。"
                    ),
                }
            try:
                fh.seek(0)
            except OSError:
                pass
            try:
                zf = zipfile.ZipFile(fh, "r")
            except (zipfile.BadZipFile, KeyError, ValueError) as exc:
                return {
                    "ok": False,
                    "issue": "corrupt",
                    "message": (
                        "检测到损坏的 Excel 工作簿 / Corrupt workbook detected: "
                        f"{_safe_name(file_path)}。ZIP 包结构不完整或已截断（{type(exc).__name__}），"
                        "无法用 openpyxl 打开。请重新导出或修复后再试。"
                    ),
                }
            except OSError as exc:
                return _classify_open_error(exc, file_path)
            try:
                entries = zf.infolist()
            except (zipfile.BadZipFile, KeyError, ValueError) as exc:
                return {
                    "ok": False,
                    "issue": "corrupt",
                    "message": (
                        "检测到损坏的 Excel 工作簿 / Corrupt workbook detected: "
                        f"{_safe_name(file_path)}。ZIP 包条目读取失败（{type(exc).__name__}），"
                        "结构不完整。请重新导出或修复后再试。"
                    ),
                }
            except OSError as exc:
                return _classify_open_error(exc, file_path)
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
            try:
                wb = load_workbook(fh, read_only=True, data_only=True)
                wb.close()
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
                return _classify_open_error(exc, file_path)
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
        finally:
            try:
                fh.close()
            except OSError:
                pass

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

    # CSV / plain text branch: count newlines with constant memory (binary
    # streaming, 1 MiB per read — never read() the whole file). Return shape
    # is identical to the xlsx branch (same keys / chunk semantics, header
    # row counted as row 1 just like openpyxl's max_row).
    if file_path.suffix.lower() in _TEXT_SUFFIXES:
        try:
            newline_count = 0
            last_byte = -1
            with open(file_path, "rb") as fh:
                while True:
                    buf = fh.read(1 << 20)
                    if not buf:
                        break
                    newline_count += buf.count(b"\n")
                    last_byte = buf[-1]
        except MemoryError:
            return {
                "needs_chunking": False,
                "total_rows": 0,
                "max_sheet_rows": 0,
                "chunks": [],
                "message": "文件读取内存不足 / Out of memory while reading text file",
            }
        except OSError as exc:
            return {
                "needs_chunking": False,
                "total_rows": 0,
                "max_sheet_rows": 0,
                "chunks": [],
                "message": (
                    "无法打开文本文件做分块 / Cannot open text file for chunking: "
                    f"{type(exc).__name__}"
                ),
            }

        # A final fragment without a trailing LF is still one (last) line;
        # CRLF is counted once because only \n is counted.
        total_lines = newline_count + (1 if last_byte not in (-1, 0x0A) else 0)

        text_chunks: list[dict] = []
        if total_lines > max_rows:
            start = 1
            while start <= total_lines:
                if len(text_chunks) >= _MAX_CHUNKS:
                    break
                end = min(start + max_rows - 1, total_lines)
                text_chunks.append(
                    {"start_row": start, "end_row": end, "sheet": file_path.stem}
                )
                start = end + 1

        needs_text_chunking = total_lines > max_rows
        if needs_text_chunking:
            if len(text_chunks) >= _MAX_CHUNKS:
                text_message = (
                    f"分块数量达上限 / Chunk count capped at {_MAX_CHUNKS}: "
                    f"max_sheet_rows={total_lines}, max_rows={max_rows}。"
                    "请先筛选数据减小范围。"
                )
            else:
                text_message = (
                    f"文本文件行数过大，需要分块处理 / Large text file needs chunking: "
                    f"max_sheet_rows={total_lines} > max_rows={max_rows}，"
                    f"已生成 {len(text_chunks)} 个分块范围。"
                )
        else:
            text_message = (
                f"行数未超限，无需分块 / No chunking needed: "
                f"max_sheet_rows={total_lines} <= max_rows={max_rows}"
            )
            text_chunks = []

        return {
            "needs_chunking": needs_text_chunking,
            "total_rows": total_lines,
            "max_sheet_rows": total_lines,
            "chunks": text_chunks,
            "message": text_message,
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

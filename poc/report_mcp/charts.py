# -*- coding: utf-8 -*-
"""Chart rendering helpers (matplotlib Agg backend) for the report MCP.

Each renderer takes a list[dict] (or DataFrame) + column mappings and writes
a PNG file under the workspace sandbox. Returns a JSON-friendly dict.

Supported chart types: bar / line / pie / scatter / heatmap.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Force non-interactive backend (POC env, no display).

import matplotlib.pyplot as plt  # noqa: E402  (after use("Agg"))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# Default DPI keeps PNGs sharp at 6-inch figure width without bloating docx.
_DEFAULT_DPI = 120
_DEFAULT_FIG_W = 6.4
_DEFAULT_FIG_H = 3.8

_VALID_TYPES = {"bar", "line", "pie", "scatter", "heatmap"}


def _workspace_root() -> Path:
    raw = os.environ.get("POC_WORKSPACE") or os.environ.get("QWENPAW_WORKING_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _resolve_allowed_path(path: str) -> tuple[Path | None, dict | None]:
    """Resolve a path and enforce the workspace sandbox.

    Mirrors the Phase 1 excel_guard_mcp.guards contract so the error shape
    stays consistent for Skill authors.
    """
    root = _workspace_root()
    try:
        file_path = Path(path).expanduser().resolve(strict=False)
    except OSError as exc:
        return None, {
            "ok": False,
            "issue": "path_denied",
            "message": f"路径无法解析 / Cannot resolve path: {exc}",
        }

    try:
        if not file_path.is_relative_to(root):
            return None, {
                "ok": False,
                "issue": "path_denied",
                "message": f"路径越界 / Path outside workspace root ({root}): {path}",
            }
    except AttributeError:  # pragma: no cover - py<3.9 fallback
        if root not in file_path.parents and file_path != root:
            return None, {
                "ok": False,
                "issue": "path_denied",
                "message": f"路径越界 / Path outside workspace root ({root}): {path}",
            }

    if file_path.is_symlink():
        try:
            real = file_path.resolve(strict=True)
            if not real.is_relative_to(root):
                return None, {
                    "ok": False,
                    "issue": "path_denied",
                    "message": f"符号链接越界 / Symlink escapes workspace: {path}",
                }
            file_path = real
        except OSError as exc:
            return None, {
                "ok": False,
                "issue": "path_denied",
                "message": f"符号链接无效 / Invalid symlink: {exc}",
            }

    return file_path, None


def _to_dataframe(data: Any) -> pd.DataFrame:
    """Coerce list[dict]/dict/None into a DataFrame with a friendly error."""
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        if not data:
            return pd.DataFrame()
        if not all(isinstance(r, dict) for r in data):
            raise ValueError("data 列表中必须是 dict / data list must contain dicts")
        return pd.DataFrame(data)
    if isinstance(data, dict):
        return pd.DataFrame(data)
    raise ValueError(f"不支持的 data 类型 / Unsupported data type: {type(data).__name__}")


def _default_output_path(chart_type: str, user_path: str = "") -> Path:
    """Pick an output path under workspace/output/charts/ when not given."""
    if user_path:
        return Path(user_path)
    root = _workspace_root()
    out_dir = root / "output" / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{chart_type}_{os.getpid()}_{abs(hash(chart_type)) % 10000}.png"


def _save_figure(fig: plt.Figure, path: Path, dpi: int) -> str | None:
    """Create parent dirs and save the figure. Returns an error message or None."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
    except OSError as exc:
        return f"图表保存失败 / Failed to save chart: {exc}"
    finally:
        plt.close(fig)
    return None


def _check_columns(df: pd.DataFrame, required: list[str]) -> str | None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        return f"列缺失 / Missing columns: {missing}"
    return None


def _err(message: str, **extra: Any) -> dict:
    return {"ok": False, "message": message, **extra}


def _ok(chart_type: str, output_path: Path, dpi: int) -> dict:
    width_px = int(_DEFAULT_FIG_W * dpi)
    height_px = int(_DEFAULT_FIG_H * dpi)
    return {
        "ok": True,
        "chart_type": chart_type,
        "output_path": str(output_path),
        "width_px": width_px,
        "height_px": height_px,
        "message": f"已生成 {chart_type} 图 / Rendered {chart_type} chart: {output_path.name}",
    }


def render_bar(
    data: Any,
    x: str,
    y: str,
    series: str | None = None,
    title: str = "",
    output_path: str = "",
    dpi: int = _DEFAULT_DPI,
) -> dict:
    """Render a bar (or grouped bar) chart to PNG."""
    if not x or not y:
        return _err("柱状图需要 x 和 y / bar chart needs x and y")
    try:
        df = _to_dataframe(data)
    except ValueError as exc:
        return _err(str(exc))

    if df.empty:
        return _err("数据为空 / data is empty")
    err = _check_columns(df, [x, y] + ([series] if series else []))
    if err:
        return _err(err)

    out, denied = _resolve_allowed_path(str(_default_output_path("bar", output_path)))
    if denied is not None:
        return _err(denied["message"], issue=denied["issue"])

    fig, ax = plt.subplots(figsize=(_DEFAULT_FIG_W, _DEFAULT_FIG_H), dpi=dpi)
    try:
        if series:
            pivot = df.pivot_table(index=x, columns=series, values=y, aggfunc="sum", fill_value=0)
            pivot.plot(kind="bar", ax=ax)
        else:
            agg = df.groupby(x, dropna=False)[y].sum().reset_index()
            ax.bar(agg[x].astype(str), agg[y])
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        if title:
            ax.set_title(title)
    except Exception as exc:  # noqa: BLE001
        plt.close(fig)
        return _err(f"柱状图渲染失败 / Failed to render bar chart: {exc}")

    save_err = _save_figure(fig, out, dpi)
    if save_err:
        return _err(save_err)
    return _ok("bar", out, dpi)


def render_line(
    data: Any,
    x: str,
    y: str,
    series: str | None = None,
    title: str = "",
    output_path: str = "",
    dpi: int = _DEFAULT_DPI,
) -> dict:
    """Render a line chart to PNG (single or multi-series)."""
    if not x or not y:
        return _err("折线图需要 x 和 y / line chart needs x and y")
    try:
        df = _to_dataframe(data)
    except ValueError as exc:
        return _err(str(exc))

    if df.empty:
        return _err("数据为空 / data is empty")
    err = _check_columns(df, [x, y] + ([series] if series else []))
    if err:
        return _err(err)

    out, denied = _resolve_allowed_path(str(_default_output_path("line", output_path)))
    if denied is not None:
        return _err(denied["message"], issue=denied["issue"])

    fig, ax = plt.subplots(figsize=(_DEFAULT_FIG_W, _DEFAULT_FIG_H), dpi=dpi)
    try:
        if series:
            for key, sub in df.groupby(series):
                sub_sorted = sub.sort_values(x)
                ax.plot(sub_sorted[x], sub_sorted[y], label=str(key), marker="o", linewidth=1.5)
            ax.legend(title=series, fontsize=8)
        else:
            sub_sorted = df.sort_values(x)
            ax.plot(sub_sorted[x], sub_sorted[y], marker="o", linewidth=1.5)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        if title:
            ax.set_title(title)
    except Exception as exc:  # noqa: BLE001
        plt.close(fig)
        return _err(f"折线图渲染失败 / Failed to render line chart: {exc}")

    save_err = _save_figure(fig, out, dpi)
    if save_err:
        return _err(save_err)
    return _ok("line", out, dpi)


def render_pie(
    data: Any,
    label: str,
    value: str,
    title: str = "",
    output_path: str = "",
    dpi: int = _DEFAULT_DPI,
) -> dict:
    """Render a pie chart to PNG (values are summed by label)."""
    if not label or not value:
        return _err("饼图需要 label 和 value / pie chart needs label and value")
    try:
        df = _to_dataframe(data)
    except ValueError as exc:
        return _err(str(exc))

    if df.empty:
        return _err("数据为空 / data is empty")
    err = _check_columns(df, [label, value])
    if err:
        return _err(err)

    out, denied = _resolve_allowed_path(str(_default_output_path("pie", output_path)))
    if denied is not None:
        return _err(denied["message"], issue=denied["issue"])

    fig, ax = plt.subplots(figsize=(_DEFAULT_FIG_W, _DEFAULT_FIG_H), dpi=dpi)
    try:
        agg = df.groupby(label, dropna=False)[value].sum().reset_index()
        ax.pie(agg[value], labels=agg[label].astype(str), autopct="%1.1f%%", startangle=90)
        ax.set_aspect("equal")
        if title:
            ax.set_title(title)
    except Exception as exc:  # noqa: BLE001
        plt.close(fig)
        return _err(f"饼图渲染失败 / Failed to render pie chart: {exc}")

    save_err = _save_figure(fig, out, dpi)
    if save_err:
        return _err(save_err)
    return _ok("pie", out, dpi)


def render_scatter(
    data: Any,
    x: str,
    y: str,
    color: str | None = None,
    title: str = "",
    output_path: str = "",
    dpi: int = _DEFAULT_DPI,
) -> dict:
    """Render a scatter plot to PNG (optionally colored by a column)."""
    if not x or not y:
        return _err("散点图需要 x 和 y / scatter needs x and y")
    try:
        df = _to_dataframe(data)
    except ValueError as exc:
        return _err(str(exc))

    if df.empty:
        return _err("数据为空 / data is empty")
    err = _check_columns(df, [x, y] + ([color] if color else []))
    if err:
        return _err(err)

    out, denied = _resolve_allowed_path(str(_default_output_path("scatter", output_path)))
    if denied is not None:
        return _err(denied["message"], issue=denied["issue"])

    fig, ax = plt.subplots(figsize=(_DEFAULT_FIG_W, _DEFAULT_FIG_H), dpi=dpi)
    try:
        if color:
            for key, sub in df.groupby(color):
                ax.scatter(sub[x], sub[y], label=str(key), alpha=0.75, s=24)
            ax.legend(title=color, fontsize=8)
        else:
            ax.scatter(df[x], df[y], alpha=0.75, s=24)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        if title:
            ax.set_title(title)
    except Exception as exc:  # noqa: BLE001
        plt.close(fig)
        return _err(f"散点图渲染失败 / Failed to render scatter: {exc}")

    save_err = _save_figure(fig, out, dpi)
    if save_err:
        return _err(save_err)
    return _ok("scatter", out, dpi)


def render_heatmap(
    data: Any = None,
    row: str | None = None,
    col: str | None = None,
    value: str | None = None,
    x_labels: list[str] | None = None,
    y_labels: list[str] | None = None,
    matrix: list[list[float]] | None = None,
    title: str = "",
    output_path: str = "",
    dpi: int = _DEFAULT_DPI,
) -> dict:
    """Render a heatmap to PNG.

    Two input modes:
    1. Long form: ``data`` is a list[dict] with row/col/value columns.
    2. Wide form: pass ``matrix`` + ``x_labels`` + ``y_labels`` directly.
    """
    out, denied = _resolve_allowed_path(str(_default_output_path("heatmap", output_path)))
    if denied is not None:
        return _err(denied["message"], issue=denied["issue"])

    try:
        if matrix is not None:
            arr = np.asarray(matrix, dtype=float)
            if arr.ndim != 2:
                return _err("matrix 必须是二维 / matrix must be 2D")
            xl = x_labels or [str(i) for i in range(arr.shape[1])]
            yl = y_labels or [str(i) for i in range(arr.shape[0])]
        else:
            if not (row and col and value):
                return _err(
                    "热力图需要 (row, col, value) 或 (matrix, x_labels, y_labels) / "
                    "heatmap needs either (row, col, value) or (matrix, x_labels, y_labels)"
                )
            df = _to_dataframe(data)
            if df.empty:
                return _err("数据为空 / data is empty")
            err = _check_columns(df, [row, col, value])
            if err:
                return _err(err)
            pivot = df.pivot_table(index=row, columns=col, values=value, aggfunc="sum", fill_value=0)
            arr = pivot.to_numpy(dtype=float)
            xl = [str(c) for c in pivot.columns]
            yl = [str(i) for i in pivot.index]
    except Exception as exc:  # noqa: BLE001
        return _err(f"热力图数据准备失败 / Failed to prepare heatmap data: {exc}")

    fig, ax = plt.subplots(figsize=(_DEFAULT_FIG_W, _DEFAULT_FIG_H), dpi=dpi)
    try:
        im = ax.imshow(arr, aspect="auto", cmap="YlGnBu")
        ax.set_xticks(range(len(xl)))
        ax.set_xticklabels(xl, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(yl)))
        ax.set_yticklabels(yl, fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        if title:
            ax.set_title(title)
    except Exception as exc:  # noqa: BLE001
        plt.close(fig)
        return _err(f"热力图渲染失败 / Failed to render heatmap: {exc}")

    save_err = _save_figure(fig, out, dpi)
    if save_err:
        return _err(save_err)
    return _ok("heatmap", out, dpi)


def render_chart(  # convenience dispatcher; not a public MCP tool
    chart_type: str,
    **kwargs: Any,
) -> dict:
    """Dispatch to the matching chart renderer (used by tests / convenience)."""
    ct = (chart_type or "").lower()
    if ct not in _VALID_TYPES:
        return _err(
            f"不支持的 chart_type / Unsupported chart_type: {chart_type!r}. "
            f"Expected one of {sorted(_VALID_TYPES)}"
        )
    fn = {
        "bar": render_bar,
        "line": render_line,
        "pie": render_pie,
        "scatter": render_scatter,
        "heatmap": render_heatmap,
    }[ct]
    return fn(**kwargs)

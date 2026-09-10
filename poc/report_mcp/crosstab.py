# -*- coding: utf-8 -*-
"""Cross-tabulation helpers (pandas pivot_table) for the report MCP."""

from __future__ import annotations

from typing import Any

import pandas as pd

_AGG_FUNCS = {"sum", "mean", "count", "min", "max", "median", "std"}


def pivot_table(
    data: Any,
    rows: list[str],
    cols: list[str],
    value: str,
    aggfunc: str = "sum",
    max_categories: int = 50,
) -> dict:
    """Build a cross-tab from long-form data.

    Args:
        data: list[dict] / dict / DataFrame.
        rows: row index columns.
        cols: column index columns.
        value: value column to aggregate.
        aggfunc: one of ``sum / mean / count / min / max / median / std``.
        max_categories: refuse to build a table with more distinct cells than this.

    Returns:
        dict with keys ``ok, table (list[dict]), rows, cols, value, aggfunc,
        row_count, col_count, message``.
    """
    if not rows:
        return _err("rows 不能为空 / rows must not be empty")
    if not value:
        return _err("value 不能为空 / value must not be empty")
    if aggfunc not in _AGG_FUNCS:
        return _err(
            f"不支持的 aggfunc / Unsupported aggfunc: {aggfunc!r}. "
            f"Expected one of {sorted(_AGG_FUNCS)}"
        )
    if max_categories < 1:
        return _err("max_categories 必须 >= 1 / max_categories must be >= 1")

    try:
        df = _to_df(data)
    except ValueError as exc:
        return _err(str(exc))

    if df.empty:
        return _err("数据为空 / data is empty")

    missing = [c for c in (list(rows) + list(cols) + [value]) if c not in df.columns]
    if missing:
        return _err(f"列缺失 / Missing columns: {missing}")

    n_rows = df[rows].drop_duplicates().shape[0]
    n_cols = df[cols].drop_duplicates().shape[0] if cols else 1
    if n_rows * n_cols > max_categories:
        return _err(
            f"交叉表维度超限 / crosstab too large: {n_rows}x{n_cols} > {max_categories}。"
            "请先筛选 top-N 或减少维度。"
        )

    try:
        table = pd.pivot_table(
            df, index=rows, columns=cols or None, values=value, aggfunc=aggfunc, fill_value=0
        )
    except Exception as exc:  # noqa: BLE001
        return _err(f"pivot_table 失败 / pivot failed: {exc}")

    # Flatten MultiIndex columns so the dict output is JSON-friendly.
    table_records = table.reset_index().to_dict(orient="records")
    row_count = int(table.shape[0])
    col_count = int(table.shape[1]) if cols else 1

    return {
        "ok": True,
        "table": table_records,
        "rows": list(rows),
        "cols": list(cols),
        "value": value,
        "aggfunc": aggfunc,
        "row_count": row_count,
        "col_count": col_count,
        "message": (
            f"交叉表已生成 / Crosstab built: {row_count}行 x {col_count}列 "
            f"(agg={aggfunc}, value={value})"
        ),
    }


def _to_df(data: Any) -> pd.DataFrame:
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


def _err(message: str) -> dict:
    return {"ok": False, "table": [], "message": message}

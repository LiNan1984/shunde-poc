# -*- coding: utf-8 -*-
"""Error-path and branch-coverage tests for poc.report_mcp.

Targets (handoff task A): charts.py 60% -> >=85%, crosstab.py 66% -> >=90%.
Covers: empty data, missing columns, illegal types, sandbox path escape,
unwritable output directory, symlink handling, render-time failures, and
both heatmap input modes plus the render_chart dispatcher.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from poc.report_mcp import charts
from poc.report_mcp.charts import render_chart
from poc.report_mcp.crosstab import pivot_table

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _sandbox_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POC_WORKSPACE", str(tmp_path))


ROWS = [
    {"region": "北区", "quarter": "Q1", "product": "储蓄", "sales": 100, "customers": 30},
    {"region": "北区", "quarter": "Q2", "product": "信贷", "sales": 140, "customers": 34},
    {"region": "南区", "quarter": "Q1", "product": "储蓄", "sales": 80, "customers": 20},
    {"region": "南区", "quarter": "Q2", "product": "理财", "sales": 120, "customers": 28},
    {"region": "东区", "quarter": "Q1", "product": "信贷", "sales": 60, "customers": 18},
    {"region": "东区", "quarter": "Q2", "product": "储蓄", "sales": 90, "customers": 22},
]


# ---------------------------------------------------------------------------
# charts._workspace_root / _resolve_allowed_path branches
# ---------------------------------------------------------------------------


def test_workspace_root_defaults_to_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POC_WORKSPACE", raising=False)
    monkeypatch.delenv("QWENPAW_WORKING_DIR", raising=False)

    assert charts._workspace_root() == REPO_ROOT


def test_workspace_root_prefers_qwenpaw_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("POC_WORKSPACE", raising=False)
    monkeypatch.setenv("QWENPAW_WORKING_DIR", str(tmp_path))

    assert charts._workspace_root() == tmp_path.resolve()


def test_resolve_allowed_path_reports_oserror(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    orig_realpath = os.path.realpath

    def _maybe_boom(path: object, *_args: object, **_kwargs: object) -> str:
        if str(path).endswith("boom.png"):
            raise OSError("synthetic resolve failure")
        return orig_realpath(path)

    monkeypatch.setattr(os.path, "realpath", _maybe_boom)

    resolved, err = charts._resolve_allowed_path(str(tmp_path / "boom.png"))
    assert resolved is None
    assert err is not None
    assert err["issue"] == "path_denied"
    assert "Cannot resolve" in err["message"]


def test_resolve_symlink_inside_workspace_followed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "real.png"
    target.write_bytes(b"x")
    link = tmp_path / "link.png"
    link.symlink_to(target)

    # Make strict=False resolution a passthrough so the link itself reaches
    # the symlink branch (real resolve() would pre-follow the link).
    orig_resolve = Path.resolve

    def _fake_resolve(self: Path, strict: bool = False) -> Path:
        return self if not strict else orig_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", _fake_resolve)

    resolved, err = charts._resolve_allowed_path(str(link))
    assert err is None
    assert resolved == target.resolve()


def test_resolve_symlink_escaping_workspace_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fd, outside = tempfile.mkstemp(prefix="report-symlink-target-", suffix=".png")
    os.close(fd)
    link = tmp_path / "escape.png"
    link.symlink_to(outside)

    orig_resolve = Path.resolve

    def _fake_resolve(self: Path, strict: bool = False) -> Path:
        return self if not strict else orig_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", _fake_resolve)

    try:
        resolved, err = charts._resolve_allowed_path(str(link))
        assert resolved is None
        assert err is not None
        assert err["issue"] == "path_denied"
        assert "符号链接越界" in err["message"]
    finally:
        Path(outside).unlink(missing_ok=True)


def test_resolve_dangling_symlink_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    link = tmp_path / "dangling.png"
    link.symlink_to(tmp_path / "gone.png")

    orig_resolve = Path.resolve

    def _fake_resolve(self: Path, strict: bool = False) -> Path:
        return self if not strict else orig_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", _fake_resolve)

    resolved, err = charts._resolve_allowed_path(str(link))
    assert resolved is None
    assert err is not None
    assert err["issue"] == "path_denied"
    assert "符号链接无效" in err["message"]


# ---------------------------------------------------------------------------
# charts._to_dataframe / _check_columns / default output path
# ---------------------------------------------------------------------------


def test_to_dataframe_accepts_all_supported_shapes() -> None:
    assert charts._to_dataframe(None).empty
    assert charts._to_dataframe([]).empty
    df = pd.DataFrame([{"a": 1}])
    result = charts._to_dataframe(df)
    assert result is not df  # copied, not the same object

    from_dict = charts._to_dataframe({"a": [1, 2], "b": [3, 4]})
    assert list(from_dict.columns) == ["a", "b"] and len(from_dict) == 2

    from_list = charts._to_dataframe([{"a": 1}, {"a": 2}])
    assert len(from_list) == 2


def test_to_dataframe_rejects_bad_shapes() -> None:
    with pytest.raises(ValueError, match="dict"):
        charts._to_dataframe([1, 2])
    with pytest.raises(ValueError, match="Unsupported"):
        charts._to_dataframe(42)


def test_default_output_path_uses_workspace_output_dir(tmp_path: Path) -> None:
    p = charts._default_output_path("bar")
    assert p.parent == tmp_path / "output" / "charts"
    assert p.suffix == ".png"


def test_default_output_path_respects_explicit_relative_path() -> None:
    p = charts._default_output_path("bar", "sub/custom.png")
    assert p == Path("sub/custom.png")


# ---------------------------------------------------------------------------
# bar
# ---------------------------------------------------------------------------


def test_bar_requires_x_and_y(tmp_path: Path) -> None:
    res = charts.render_bar(ROWS, x="", y="sales", output_path=str(tmp_path / "b.png"))
    assert res["ok"] is False and "x 和 y" in res["message"]


def test_bar_rejects_illegal_data_type(tmp_path: Path) -> None:
    res = charts.render_bar(42, x="region", y="sales", output_path=str(tmp_path / "b.png"))
    assert res["ok"] is False and "Unsupported" in res["message"]


def test_bar_rejects_non_dict_rows(tmp_path: Path) -> None:
    res = charts.render_bar([1, 2], x="region", y="sales", output_path=str(tmp_path / "b.png"))
    assert res["ok"] is False and "dict" in res["message"]


def test_bar_rejects_empty_data(tmp_path: Path) -> None:
    res = charts.render_bar([], x="region", y="sales", output_path=str(tmp_path / "b.png"))
    assert res["ok"] is False and "empty" in res["message"].lower()


def test_bar_rejects_missing_column(tmp_path: Path) -> None:
    res = charts.render_bar(ROWS, x="nope", y="sales", output_path=str(tmp_path / "b.png"))
    assert res["ok"] is False and "Missing columns" in res["message"]


def test_bar_denies_path_outside_workspace() -> None:
    res = charts.render_bar(ROWS, x="region", y="sales", output_path="/etc/evil_bar.png")
    assert res["ok"] is False
    assert res.get("issue") == "path_denied"
    assert "越界" in res["message"] or "outside" in res["message"].lower()


def test_bar_grouped_series_renders(tmp_path: Path) -> None:
    res = charts.render_bar(
        ROWS, x="quarter", y="sales", series="region",
        title="分组柱图", output_path=str(tmp_path / "bar_group.png"),
    )
    assert res["ok"] is True, res
    assert Path(res["output_path"]).is_file()


def test_bar_render_failure_returns_friendly_error(tmp_path: Path) -> None:
    # Non-numeric values cannot be summed/plotted as bar heights.
    bad = [{"x": "a", "s": "g", "v": "z"}, {"x": "b", "s": "g", "v": "q"}]
    res = charts.render_bar(
        bad, x="x", y="v", series="s", output_path=str(tmp_path / "bad.png")
    )
    assert res["ok"] is False
    assert "柱状图渲染失败" in res["message"]


def test_bar_unwritable_output_dir_returns_error(
    tmp_path: Path,
) -> None:
    ro = tmp_path / "readonly"
    ro.mkdir()
    os.chmod(ro, 0o555)  # no write bit
    try:
        res = charts.render_bar(
            ROWS, x="region", y="sales", output_path=str(ro / "sub" / "b.png")
        )
        assert res["ok"] is False
        assert "保存失败" in res["message"] or "Failed to save" in res["message"]
    finally:
        os.chmod(ro, 0o755)


def test_bar_default_output_path_when_omitted() -> None:
    res = charts.render_bar(ROWS, x="region", y="sales")
    try:
        assert res["ok"] is True, res
        assert Path(res["output_path"]).name.endswith(".png")
    finally:
        Path(res["output_path"]).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# line
# ---------------------------------------------------------------------------


def test_line_error_paths(tmp_path: Path) -> None:
    assert charts.render_line(ROWS, x="", y="sales", output_path=str(tmp_path / "l.png"))["ok"] is False
    assert "Unsupported" in charts.render_line(42, x="x", y="y", output_path=str(tmp_path / "l2.png"))["message"]
    assert charts.render_line(None, x="x", y="y", output_path=str(tmp_path / "l3.png"))["ok"] is False
    assert "Missing columns" in charts.render_line(
        ROWS, x="x", y="nope", output_path=str(tmp_path / "l4.png")
    )["message"]
    denied = charts.render_line(ROWS, x="customers", y="sales", output_path="/etc/evil_line.png")
    assert denied["ok"] is False and denied.get("issue") == "path_denied"


def test_line_multi_series_renders(tmp_path: Path) -> None:
    res = charts.render_line(
        ROWS, x="quarter", y="sales", series="region",
        title="多系列折线", output_path=str(tmp_path / "line_group.png"),
    )
    assert res["ok"] is True, res


def test_line_render_failure_on_unorderable_x(tmp_path: Path) -> None:
    bad = [{"x": 1, "y": 1}, {"x": "a", "y": 2}]
    res = charts.render_line(bad, x="x", y="y", output_path=str(tmp_path / "bad.png"))
    assert res["ok"] is False and "折线图渲染失败" in res["message"]


# ---------------------------------------------------------------------------
# pie
# ---------------------------------------------------------------------------


def test_pie_error_paths(tmp_path: Path) -> None:
    assert charts.render_pie(ROWS, label="", value="sales", output_path=str(tmp_path / "p.png"))["ok"] is False
    assert "Unsupported" in charts.render_pie(42, label="region", value="sales", output_path=str(tmp_path / "p2.png"))["message"]
    assert charts.render_pie([], label="region", value="sales", output_path=str(tmp_path / "p3.png"))["ok"] is False
    assert "Missing columns" in charts.render_pie(
        ROWS, label="region", value="nope", output_path=str(tmp_path / "p4.png")
    )["message"]
    denied = charts.render_pie(ROWS, label="region", value="sales", output_path="/etc/evil_pie.png")
    assert denied["ok"] is False and denied.get("issue") == "path_denied"


def test_pie_happy_renders_with_title(tmp_path: Path) -> None:
    res = charts.render_pie(
        ROWS, label="product", value="sales", title="产品占比",
        output_path=str(tmp_path / "pie.png"),
    )
    assert res["ok"] is True, res
    assert Path(res["output_path"]).is_file()


def test_pie_render_failure_on_non_numeric_values(tmp_path: Path) -> None:
    bad = [{"k": "a", "v": "x"}, {"k": "b", "v": "y"}]
    res = charts.render_pie(bad, label="k", value="v", output_path=str(tmp_path / "bad.png"))
    assert res["ok"] is False and "饼图渲染失败" in res["message"]


# ---------------------------------------------------------------------------
# scatter
# ---------------------------------------------------------------------------


def test_scatter_error_paths(tmp_path: Path) -> None:
    assert charts.render_scatter(ROWS, x="", y="sales", output_path=str(tmp_path / "s.png"))["ok"] is False
    assert "Unsupported" in charts.render_scatter(42, x="x", y="y", output_path=str(tmp_path / "s2.png"))["message"]
    assert charts.render_scatter(None, x="x", y="y", output_path=str(tmp_path / "s3.png"))["ok"] is False
    assert "Missing columns" in charts.render_scatter(
        ROWS, x="customers", y="nope", output_path=str(tmp_path / "s4.png")
    )["message"]
    denied = charts.render_scatter(ROWS, x="customers", y="sales", output_path="/etc/evil_scatter.png")
    assert denied["ok"] is False and denied.get("issue") == "path_denied"


def test_scatter_colored_by_column_renders(tmp_path: Path) -> None:
    res = charts.render_scatter(
        ROWS, x="customers", y="sales", color="region",
        title="客户数-销售额", output_path=str(tmp_path / "sc_color.png"),
    )
    assert res["ok"] is True, res


def test_scatter_render_failure_on_unhashable_x(tmp_path: Path) -> None:
    bad = [{"x": {"a": 1}, "y": 1}, {"x": {"b": 2}, "y": 2}]
    res = charts.render_scatter(bad, x="x", y="y", output_path=str(tmp_path / "bad.png"))
    assert res["ok"] is False and "散点图渲染失败" in res["message"]


# ---------------------------------------------------------------------------
# heatmap (both input modes)
# ---------------------------------------------------------------------------


def test_heatmap_denies_path_outside_workspace() -> None:
    res = charts.render_heatmap(
        matrix=[[1, 2]], output_path="/etc/evil_heat.png"
    )
    assert res["ok"] is False
    assert res.get("issue") == "path_denied"


def test_heatmap_matrix_must_be_2d(tmp_path: Path) -> None:
    res = charts.render_heatmap(matrix=[1, 2, 3], output_path=str(tmp_path / "h.png"))
    assert res["ok"] is False and "二维" in res["message"]


def test_heatmap_requires_long_form_args(tmp_path: Path) -> None:
    res = charts.render_heatmap(output_path=str(tmp_path / "h.png"))
    assert res["ok"] is False and "heatmap needs" in res["message"]


def test_heatmap_long_form_empty_and_missing_column(tmp_path: Path) -> None:
    empty = charts.render_heatmap(
        data=[], row="r", col="c", value="v", output_path=str(tmp_path / "h.png")
    )
    assert empty["ok"] is False and "empty" in empty["message"].lower()

    missing = charts.render_heatmap(
        data=ROWS, row="region", col="quarter", value="nope",
        output_path=str(tmp_path / "h2.png"),
    )
    assert missing["ok"] is False and "Missing columns" in missing["message"]


def test_heatmap_long_form_renders(tmp_path: Path) -> None:
    res = charts.render_heatmap(
        data=ROWS, row="region", col="quarter", value="sales",
        title="区域 x 季度", output_path=str(tmp_path / "h_long.png"),
    )
    assert res["ok"] is True, res
    assert Path(res["output_path"]).is_file()


def test_heatmap_non_numeric_matrix_fails_prepare(tmp_path: Path) -> None:
    res = charts.render_heatmap(
        matrix=[["a", "b"], ["c", "d"]], output_path=str(tmp_path / "h.png")
    )
    assert res["ok"] is False and "数据准备失败" in res["message"]


def test_heatmap_render_failure_returns_friendly_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic imshow failure")

    monkeypatch.setattr("matplotlib.axes.Axes.imshow", _boom)

    res = charts.render_heatmap(
        matrix=[[1, 2], [3, 4]], output_path=str(tmp_path / "h.png")
    )
    assert res["ok"] is False and "热力图渲染失败" in res["message"]


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------


def test_render_chart_dispatch_reaches_renderers(tmp_path: Path) -> None:
    res = render_chart(
        "bar", data=ROWS, x="region", y="sales", output_path=str(tmp_path / "d.png")
    )
    assert res["ok"] is True, res


@pytest.mark.parametrize(
    ("chart_type", "kwargs"),
    [
        ("bar", {"data": ROWS, "x": "region", "y": "sales"}),
        ("line", {"data": ROWS, "x": "customers", "y": "sales"}),
        ("pie", {"data": ROWS, "label": "region", "value": "sales"}),
        ("scatter", {"data": ROWS, "x": "customers", "y": "sales"}),
        ("heatmap", {"matrix": [[1, 2], [3, 4]]}),
    ],
)
def test_render_chart_dispatches_every_type(
    tmp_path: Path, chart_type: str, kwargs: dict
) -> None:
    kwargs["output_path"] = str(tmp_path / f"{chart_type}.png")
    res = render_chart(chart_type, **kwargs)
    assert res["ok"] is True, res
    assert Path(res["output_path"]).is_file()


def test_render_chart_rejects_unknown_type(tmp_path: Path) -> None:
    res = render_chart("radar", data=ROWS, x="region", y="sales")
    assert res["ok"] is False and "Unsupported chart_type" in res["message"]
    # Empty / None type must not blow up either.
    assert render_chart("", data=ROWS)["ok"] is False


# ---------------------------------------------------------------------------
# crosstab
# ---------------------------------------------------------------------------


def test_crosstab_validates_required_arguments() -> None:
    assert "rows" in pivot_table(ROWS, rows=[], cols=["quarter"], value="sales")["message"]
    assert "value" in pivot_table(ROWS, rows=["region"], cols=[], value="")["message"]
    bad_agg = pivot_table(ROWS, rows=["region"], cols=[], value="sales", aggfunc="bogus")
    assert "Unsupported aggfunc" in bad_agg["message"]
    bad_max = pivot_table(ROWS, rows=["region"], cols=[], value="sales", max_categories=0)
    assert "max_categories" in bad_max["message"]


def test_crosstab_rejects_bad_data_shapes(tmp_path: Path) -> None:
    assert "Unsupported" in pivot_table(42, rows=["region"], cols=[], value="sales")["message"]
    assert "dict" in pivot_table([1, 2], rows=["region"], cols=[], value="sales")["message"]
    assert pivot_table(None, rows=["region"], cols=[], value="sales")["ok"] is False
    assert pivot_table([], rows=["region"], cols=[], value="sales")["ok"] is False


def test_crosstab_accepts_dataframe_and_dict() -> None:
    df = pd.DataFrame(ROWS)
    res_df = pivot_table(df, rows=["region"], cols=["quarter"], value="sales")
    assert res_df["ok"] is True

    res_dict = pivot_table(
        {"region": ["N", "S"], "sales": [1, 2]}, rows=["region"], cols=[], value="sales"
    )
    assert res_dict["ok"] is True and res_dict["col_count"] == 1


def test_crosstab_missing_column() -> None:
    res = pivot_table(ROWS, rows=["region"], cols=["quarter"], value="nope")
    assert res["ok"] is False and "Missing columns" in res["message"]


def test_crosstab_rows_only_has_single_column_bucket() -> None:
    res = pivot_table(ROWS, rows=["region"], cols=[], value="sales", aggfunc="mean")
    assert res["ok"] is True
    assert res["col_count"] == 1
    assert res["row_count"] == 3


@pytest.mark.parametrize("aggfunc", ["sum", "count", "mean", "min", "max", "median"])
def test_crosstab_supported_aggfuncs(aggfunc: str) -> None:
    res = pivot_table(ROWS, rows=["quarter"], cols=["region"], value="sales", aggfunc=aggfunc)
    assert res["ok"] is True, res["message"]


def test_crosstab_pivot_failure_on_mean_of_strings() -> None:
    bad = [
        {"r": "a", "c": "x", "v": "z"},
        {"r": "b", "c": "y", "v": "q"},
    ]
    res = pivot_table(bad, rows=["r"], cols=["c"], value="v", aggfunc="mean")
    assert res["ok"] is False and "pivot failed" in res["message"]

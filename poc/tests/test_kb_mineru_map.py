# -*- coding: utf-8 -*-
"""MinerU official content_list mapping — no live MinerU process."""

from __future__ import annotations

from poc.kb_mcp.mineru import map_content_list, table_formats_from_html


def test_map_content_list_pages_tables_images() -> None:
    content = [
        {"type": "text", "text": "第一章 信贷政策", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "逾期90天认定标准 ALPHAKEY", "page_idx": 0},
        {
            "type": "table",
            "table_caption": ["产品定价"],
            "table_body": (
                "<table><tr><th>产品</th><th>利率</th></tr>"
                "<tr><td>经营贷款</td><td>4.20</td></tr></table>"
            ),
            "page_idx": 0,
        },
        {
            "type": "image",
            "img_path": "images/chart.jpg",
            "image_caption": ["RATECHART 利率走势"],
            "page_idx": 1,
        },
    ]
    pages, chunks = map_content_list(content)
    assert [p["page"] for p in pages] == [1, 2]
    assert "ALPHAKEY" in pages[0]["native_text"]
    assert "第一" in (pages[0].get("chapter") or "")
    tables = [c for c in chunks if c["kind"] == "table"]
    assert tables
    assert "4.20" in (tables[0]["table"]["csv"] or "")
    assert "<table" in tables[0]["table"]["html"]
    images = [c for c in chunks if c["kind"] == "image"]
    assert images
    assert images[0]["page"] == 2
    assert "RATECHART" in (images[0]["image_description"] or "")


def test_table_formats_from_html_three_formats() -> None:
    html = "<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>"
    table = table_formats_from_html(html)
    assert "1" in table["csv"] and "2" in table["csv"]
    assert table["html"].startswith("<table")
    assert table["json"][0]["a"] == "1"

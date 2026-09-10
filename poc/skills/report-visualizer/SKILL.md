---
name: report-visualizer
description: "当用户要求把数据或纯文字生成可视化报告（docx），或要求交叉表、柱状图、折线图、饼图、散点图、热力图时使用。触发词：报告生成、可视化报告、生成 docx、生成报告、交叉表、柱状图、折线图、饼图、散点图、热力图。先调用 report-visualizer MCP 渲染图表与交叉表，再调用 docx 工具组装报告。"
metadata:
  poc_version: "0.1"
---

# report-visualizer

顺德农商行 POC：报告可视化助手 Skill。优先调用 `report-visualizer` MCP 完成交叉表与五类图表渲染，再基于 `python-docx` 组装 docx 报告。

## 名称

`report-visualizer`

## 描述

面向银行 POC 演示场景的报告可视化技能：用户提供纯文字、数据表（CSV/JSON/list[dict]）或分析结论，并要求生成包含**交叉表**与**柱/折/饼/散点/热力图**等五类图表的 **docx** 报告时，启用本技能。处理流程：解析用户输入的结构 → 调用 `pivot_table_tool` 构建交叉表 → 调用对应 `render_*_tool` 工具产出 PNG → 调用 `render_docx_report_tool` 拼装 docx → 报告路径与图表清单返回给用户。

## 触发词

以下意图应触发本技能（示例，不限于此）：

- 报告生成 / 生成报告
- 可视化报告 / 报告可视化
- 生成 docx / 写一份报告
- 交叉表 / 透视表 / 多维分析
- 柱状图 / 折线图 / 饼图 / 散点图 / 热力图
- 给我一个图表 / 出图
- "把这组数据做成报告"

## 参数

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| 数据 | list[dict] / CSV / JSON | 报告中需要分析的数据 |
| 报告标题 | string | 报告主标题 |
| 章节大纲 | list[dict] | 每章 `{heading, level, paragraphs, table, charts}` |
| 输出路径 | string | 工作区内 `.docx` 输出绝对路径 |
| 页眉 / 页脚 | string (可选) | 报告页眉页脚文本 |
| 图表类型 | string | `bar` / `line` / `pie` / `scatter` / `heatmap` |

### 输出

| 产出 | 说明 |
|------|------|
| docx 报告路径 | 工作区内 `.docx` 绝对路径 |
| 章节摘要 | 报告中实际写入的章节数 |
| 插入图表数 | 成功嵌入的 PNG 数量 |
| 交叉表数据 | `pivot_table_tool` 返回的扁平表（前若干行摘要） |

## 返回值

成功时返回：

1. **报告路径**：docx 文件绝对路径（位于 `POC_WORKSPACE/output/` 或用户指定路径）。
2. **章节与图表摘要**：章节数、成功插入的图表数，便于用户复述。
3. **图表文件清单**：每张 PNG 的绝对路径，便于评委复查。
4. **护栏提示**：若 MCP 工具返回 `ok=false`，先返回 `message` 字段并停止后续组装。

失败时返回可读错误（路径越界、列缺失、维度超限、字体/库缺失等），不编造数据。

## 边界条件

- **非 docx 输出不触发**：用户要的是 PDF / HTML / PPTX 时不直接使用本技能；可先与 `docx-zh` 内置 Skill 协作或说明「当前 POC 仅 docx」。
- **路径越界拒绝**：所有输出必须落在 `POC_WORKSPACE` 内，符号链接越界也拒绝（与 Phase 1 一致）。
- **维度超限防御**：交叉表 `rows × cols` 超过 `max_categories`（默认 50）时直接返回提示，不强行生成。
- **列缺失早退**：图表所需的 `x` / `y` / `label` / `value` / `color` 不在数据中时返回提示，不静默使用空数据。
- **matplotlib 后端**：`Agg` 强制非交互，避免无显示器环境报错。
- **范围收窄**：本技能只做「文字 + 数据 → docx + 五类图」，不替代通用 `docx` Skill 处理复杂模板（可协作）。

## 与 MCP `report-visualizer` 的协作流程

每次按顺序调用（stdio FastMCP，配置见 `poc/config/mcp-report-visualizer.json`）：

1. **`pivot_table_tool`**（可选）
   - 入参：`data`, `rows`, `cols`, `value`, `aggfunc`（默认 `sum`），`max_categories`（默认 50）
   - 拿到 `table`（list[dict]）后可作为 docx 的 `table` 段落，也可用作图表数据源。

2. **`render_bar_tool` / `render_line_tool` / `render_pie_tool` / `render_scatter_tool` / `render_heatmap_tool`**（按需）
   - 每次返回 `output_path`（PNG），记录到章节的 `charts` 列表里。

3. **`render_docx_report_tool`**
   - 入参：`title`, `sections`, `output_path`, `header?`, `footer?`
   - `sections` 每项结构示例：
     ```json
     {
       "heading": "分季度销售",
       "level": 2,
       "paragraphs": ["本季度销售数据见下表与图。"],
       "table": {"headers": ["季度", "北区", "南区"], "rows": [["Q1", 100, 80]]},
       "charts": ["<REPO_ROOT>/poc/output/charts/bar_xxx.png"]
     }
     ```

推荐流程：

```
用户提供数据 + 报告大纲
        │
        ▼
pivot_table_tool ──超限──▶ 返回提示并结束（或减少维度）
        │ 正常
        ▼
render_*_tool × N ──列缺失──▶ 提示并跳到下一节
        │
        ▼
render_docx_report_tool ──路径越界──▶ 拒绝并提示
        │ 正常
        ▼
返回报告路径 + 章节/图表摘要给用户
```

## 可参考的 python-docx + matplotlib 用法简述

```python
# 交叉表 / Cross-tab
from poc.report_mcp import pivot_table
ct = pivot_table(data, rows=["q"], cols=["region"], value="sales", aggfunc="sum")
table = ct["table"]  # list[dict], JSON-friendly

# 柱状图 / Bar chart
from poc.report_mcp import render_bar
p = render_bar(data, x="region", y="sales", title="Sales by Region",
               output_path="<REPO_ROOT>/poc/output/charts/sales.png")

# 组装 docx / Assemble report
from poc.report_mcp import render_docx_report
sections = [
    {"heading": "分季度销售", "level": 2,
     "paragraphs": ["见下表与图。"],
     "table": {"headers": list(table[0].keys()),
               "rows": [list(r.values()) for r in table]},
     "charts": [p["output_path"]]},
]
r = render_docx_report(
    title="分行销售报告",
    sections=sections,
    output_path="<REPO_ROOT>/poc/output/report.docx",
    header="顺德农商行 POC",
    footer="页码 1",
)
print(r["output_path"], r["charts_inserted"])
```

约定：图表数据列用 `pandas`/原生 list[dict] 传入；中文文本通过 `python-docx` 显式指定 `eastAsia` 字体（默认宋体/黑体），避免 Mac/Linux 上中文显示为方块。

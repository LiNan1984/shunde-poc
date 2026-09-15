---
name: excel-qa-bank
description: "L1 skill列表摘要：Excel/CSV 读查析写。触发词：excel问答、表格分析、xlsx、csv查询。先 excel_guard__ mcp列表，文件摘要后再文件详情，pandas 精算。"
metadata:
  poc_version: "0.1"
---

# excel-qa-bank

## 渐进加载合同

上下文按 **L1 / L2 / L3** 渐进式工具加载。顺序（字面）：

skill列表摘要 → skill → mcp列表namespace前缀 → 详细mcp → 文件摘要 → 文件详情

稳定前缀（L1 目录始终不变）提高缓存命中率，前缀一致性更省 token，提高 token 经济型 ROI。

- **L1 skill列表摘要**：仅 YAML `description`。禁止把完整 MCP schema 预埋进摘要。
- **L2 skill**：先读本正文，再读 **mcp列表**（**namespace前缀** `excel_guard__`）：`excel_guard__detect_corrupt_workbook`、`excel_guard__detect_encoding`、`excel_guard__chunk_large_workbook`、`excel_guard__describe_workbook`、`excel_guard__sheet_to_markdown`、`excel_guard__edit_workbook`、`excel_guard__inspect_workbook`、`excel_guard__validate_workbook`、`excel_guard__render_workbook`。
- **L3 详细mcp**：调用时再展开入参。**文件摘要** 用 `excel_guard__describe_workbook`；**文件详情** 再用 `excel_guard__sheet_to_markdown`、`excel_guard__inspect_workbook`。

顺德农商行 POC：Excel/CSV 问答助手 Skill。优先调用 `excel-guard` MCP 做异常检测，再基于 pandas / openpyxl 完成读、查、析、写。

## 名称

`excel-qa-bank`

## 描述

面向银行 POC 演示场景的表格问答技能：用户提供 Excel（`.xlsx` / `.xlsm`）或 CSV，并提出读取、筛选、聚合、写回等问题时启用本技能。处理前必须先走 `excel-guard` MCP：损坏检测、编码识别、超大分块，再用 `describe_workbook`（必要时 `sheet_to_markdown` 小区间）看清结构，最后用 pandas / openpyxl 计算。筛选、合计、写回必须以代码执行结果为准，不得把整表转成 markdown 后靠模型猜，也不得用知识库切片当数值答案。

## 触发词

以下意图应触发本技能（示例，不限于此）：

- excel问答
- 表格分析
- xlsx
- csv查询
- 读取/查询/分析/写入 Excel 或 CSV
- 用户上传或指定表格文件路径并提问

## 参数

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| 文件路径 | string | 工作区内的 `.xlsx` / `.xlsm` / `.csv` 路径，或用户上传后的本地路径 |
| 问题 | string | 自然语言问题，覆盖读取、筛选、聚合、统计、写回等 |

### 输出

| 产出 | 说明 |
|------|------|
| 答案 | 针对问题的文字结论、汇总表或关键单元格说明 |
| 写回文件路径 | 若问题要求写入/另存，返回生成或修改后的表格文件路径 |

## 返回值

成功时返回：

1. **文字答案**：直接回答用户问题（可含表格摘要）。
2. **可选文件路径**：写回场景下给出输出文件绝对/工作区相对路径。
3. **护栏提示**：若 MCP 检出异常，先返回确定性提示，再决定是否继续（损坏则停止；编码给出建议后按识别结果读取；超大则按分块结果继续）。

失败时返回可读错误说明（文件不存在、格式不支持、MCP 报损坏等），不编造单元格数据。

## 边界条件

- **非表格交付物不触发**：主要交付物是 Word、HTML 报告、独立脚本、PPT、PDF 时，即使涉及表格数据也不使用本技能。
- **损坏文件先报 MCP 提示**：`detect_corrupt_workbook` 判定损坏时，向用户展示 MCP 返回的提示文案并停止读写，不得强行解析。
- **超大文件必须分块**：行数超过阈值阈值时必须调用 `chunk_large_workbook`，按分块结果逐步分析，禁止一次性整表载入导致超时/OOM。
- **编码异常**：CSV / 文本表先 `detect_encoding`，按识别编码读取；勿默认 UTF-8 硬读。
- **范围收窄**：只处理读/查/析/写类表格问答；不替代通用 `xlsx` 技能去做复杂财务模型排版（可协作）。

## 与 MCP `excel-guard` 的协作流程

每次处理用户表格前，**优先一次调用 `preflight_workbook`（python 内 `from poc.excel_guard_mcp.readers import preflight_workbook`）**——它串行执行下面 1-3 步并在损坏时短路（`proceed=false` 即终止）。仅在需要单项重查时才分别调用以下 MCP 工具（stdio FastMCP，配置见 `poc/config/mcp-excel-guard.json`）：

1. **`detect_corrupt_workbook`**  
   - 入参：文件路径  
   - 若 `ok=false`：原样转述 `message`，终止后续问答。

2. **`detect_encoding`**  
   - 入参：文件路径（尤其 CSV / 可疑文本表）  
   - 使用返回的 `encoding` / `confidence` 决定 `pandas.read_csv(..., encoding=...)` 等读取参数。

3. **`chunk_large_workbook`**  
   - 入参：文件路径，可选 `max_rows`（默认 5000）  
   - 若 `needs_chunking=true`：按返回的 `chunks` 分块读取与分析，再汇总答案。

4. **`describe_workbook`**（护栏通过后、写 pandas 之前必做）  
   - 入参：文件路径，可选 `preview_rows`（默认 5）  
   - 返回 sheet 清单、行列数、表头、短预览。用它决定读哪张表、哪些列，禁止盲跑 pandas。

5. **`sheet_to_markdown`**（可选，仅小区间）  
   - 入参：文件路径、可选 `sheet`、闭区间 `start_row` / `end_row`（`end_row=0` 时默认读 `max_rows`（默认 500）行）  
   - 返回表头 + 该行区间的 markdown（区间不含表头行时会自动附上投票表头）。小表或用户要「先看几行」时用；大表只导出当前分块，不要整表灌进上下文。

6. **写后自检：`audit_workbook`**（python 代码内调用，非 MCP 工具）  
   - `from poc.excel_guard_mcp.readers import audit_workbook; audit_workbook(path)`  
   - 任何写回操作完成后必须执行：缓存错误值（`#REF!`、`#DIV/0!` 等）归入 `must_fix`，公式中疑似硬编码的 3 位以上数字归入 `review`。有 `must_fix` 时必须修复后重新自检，不得直接向用户交付。

## 多文件场景：先路由再计算

用户上传多个 Excel/CSV 或询问「哪个文件里有 XX 数据」时，不要逐个打开：

1. 用 kb-qa MCP 的 `ingest_spreadsheet`（`poc/kb_mcp`）把每个文件的元数据（文件名 / sheet 名 / 表头 / 样例行）索引进知识库——只索引元数据，不索引数据行。
2. `search_knowledge` 语义检索定位目标文件与 sheet。
3. 命中后再用 pandas / openpyxl 打开原文件做精确计算。检索只负责「找文件」，代码负责「算数字」。

推荐流程：

```
用户上传/指定文件 + 问题
        │
        ▼
detect_corrupt_workbook ──损坏──▶ 返回 MCP 提示，结束
        │ 正常
        ▼
detect_encoding（CSV/文本表必做；xlsx 可跳过）
        │
        ▼
chunk_large_workbook ──需分块──▶ 记住 chunks，后面按区间读
        │
        ▼
describe_workbook（看 sheet / 表头 / 预览 / 合并区域 / 公式别名）
        │ 小区间预览可选 sheet_to_markdown
        ▼
pandas / openpyxl 读查析写 → 返回答案 / 写回路径
        │ 写回后必做
        ▼
audit_workbook（must_fix 修复后重检；review 复核硬编码）
```

多文件场景：`ingest_spreadsheet` 索引元数据 → `search_knowledge` 路由 → pandas 打开命中文件精算。
```

多文件「哪张表里有 XX」时，可先让 `kb-qa-bank` 的 `ingest_spreadsheet` / `search_knowledge` **定位文件**，再回到本技能用 pandas 计算。知识库命中只用于选文件，不用于加总或筛选。

## 可参考内置 xlsx skill 的 pandas / openpyxl 用法简述

可复用 QwenPaw 内置 `xlsx`（`xlsx-zh`）的常见做法：

**pandas（读、分析、简单写回）：**

```python
import pandas as pd

df = pd.read_excel("file.xlsx")
all_sheets = pd.read_excel("file.xlsx", sheet_name=None)
df.head()
df.describe()
df.to_excel("output.xlsx", index=False)

# CSV 配合 detect_encoding 结果
df = pd.read_csv("file.csv", encoding=encoding)
```

**openpyxl（保留公式/格式、定点修改）：**

```python
from openpyxl import load_workbook, Workbook

wb = load_workbook("existing.xlsx")
sheet = wb.active
sheet["A1"] = "New Value"
wb.save("modified.xlsx")
```

约定：数据分析优先 pandas；需要公式与单元格格式时用 openpyxl。写回后向用户给出输出路径。大文件结合 `chunk_large_workbook` 的分块信息使用 `usecols` / 行范围读取，避免整表进内存。

---
name: excel-qa-bank
description: "当用户上传或指定 Excel/CSV 并提出读取、查询、分析、写入类问题时使用。触发词：excel问答、表格分析、xlsx、csv查询。先调用 excel-guard MCP 检查损坏/编码/超大分块，再进行问答。"
metadata:
  poc_version: "0.1"
---

# excel-qa-bank

顺德农商行 POC：Excel/CSV 问答助手 Skill。优先调用 `excel-guard` MCP 做异常检测，再基于 pandas / openpyxl 完成读、查、析、写。

## 名称

`excel-qa-bank`

## 描述

面向银行 POC 演示场景的表格问答技能：用户提供 Excel（`.xlsx` / `.xlsm`）或 CSV，并提出读取、筛选、聚合、写回等问题时启用本技能。处理前必须先走 `excel-guard` MCP，覆盖损坏检测、编码识别与超大文件分块。

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

每次处理用户表格前，按顺序调用以下三个 MCP 工具（stdio FastMCP，配置见 `poc/config/mcp-excel-guard.json`）：

1. **`detect_corrupt_workbook`**  
   - 入参：文件路径  
   - 若 `ok=false`：原样转述 `message`，终止后续问答。

2. **`detect_encoding`**  
   - 入参：文件路径（尤其 CSV / 可疑文本表）  
   - 使用返回的 `encoding` / `confidence` 决定 `pandas.read_csv(..., encoding=...)` 等读取参数。

3. **`chunk_large_workbook`**  
   - 入参：文件路径，可选 `max_rows`（默认 5000）  
   - 若 `needs_chunking=true`：按返回的 `chunks` 分块读取与分析，再汇总答案。

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
chunk_large_workbook ──需分块──▶ 按 chunks 迭代分析
        │ 无需分块
        ▼
pandas / openpyxl 读查析写 → 返回答案 / 写回路径
```

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

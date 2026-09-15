---
name: mineru-document-parser
description: "文档解析：PDF/DOCX/PPTX/图片/网页 → Markdown/JSON/DOCX/LaTeX，OCR 109 语种，表格转 HTML、公式转 LaTeX。触发词：PDF转Markdown、文档解析、OCR、扫描件识别、提取表格、批量解析。用 mineru-open-api CLI 或 mineru-mcp 的 parse_documents。"
metadata:
  poc_version: "0.1"
---

# mineru-document-parser

## 渐进加载合同

L1 摘要（YAML description）→ L2 本正文 → L3 调用时展开参数。

## 名称

`mineru-document-parser`

## 描述

MinerU 官方在线 API 文档解析技能（opendatalab/MinerU-Ecosystem）。把 PDF、Word、PPT、图片、网页解析成高保真 Markdown/JSON，可选导出 DOCX/HTML/LaTeX；表格保留 HTML 结构、公式转 LaTeX；支持 109 语种 OCR、扫描件、手写、多栏、跨页表格合并，输出按人类阅读顺序并自动去页眉页脚。

## 触发词

- PDF 转 Markdown / 文档解析 / 结构化提取
- OCR / 扫描件识别 / 手写识别
- 提取表格（HTML）/ 提取公式（LaTeX）
- 批量解析 / 网页正文抽取（crawl）
- 导出 docx / latex / html

## 两条调用通道

| 通道 | 适用 | 位置 |
|------|------|------|
| CLI `mineru-open-api` | 脚本/批处理/落盘资产（图片、多格式） | 本机 `~/.local/bin/mineru-open-api`；VPS 暂无（用 MCP 通道） |
| MCP `parse_documents` | Agent 会话内解析、返回正文摘要 | VPS `http://127.0.0.1:8201/mcp`（pm2 `mineru-mcp`）；本机 stdio `uvx mineru-open-mcp` |

认证：环境变量 `MINERU_API_TOKEN`（CLI 同认 `MINERU_TOKEN`）。本机在 `~/.config/mineru/env`（source 后用）；VPS 在 `/root/.qwenpaw.secret/mineru.env`（仅 root 可读，勿写入任何文档/代码）。**不设 token 也能用 Flash 模式**（免费，仅 Markdown，≤10MB/≤20 页）。

## Flash vs 精准（Precision）

| | Flash | 精准 |
|---|---|---|
| 认证 | 不需要 | 需要 token |
| 限制 | ≤10MB、≤20 页 | ≤200MB、≤600 页 |
| 输出 | 仅 Markdown | Markdown/JSON/HTML/LaTeX/DOCX |
| 批量 | 单文件 | ≤200 文件/批 |

默认用精准模式；小文件快速预览才用 flash。

## CLI 用法

```bash
source ~/.config/mineru/env   # 本机；VPS 用 source /root/.qwenpaw.secret/mineru.env

# 精准解析，Markdown 到 stdout
mineru-open-api extract report.pdf

# 落盘全部资产（images/tables）+ 多格式导出
mineru-open-api extract report.pdf -o ./out/ -f md,docx,html

# 批量
mineru-open-api extract *.pdf -o ./results/
mineru-open-api extract --list filelist.txt -o ./results/

# 网页 → Markdown
mineru-open-api crawl https://example.com

# 免认证快速预览
mineru-open-api flash-extract report.pdf
```

## MCP 用法（parse_documents）

入参 `file_sources`：数组，元素为字符串路径/URL，或 `{"source": "...", "pages": "1-5"}`（页码范围仅 PDF；同一文件可带多个不同范围）。可选 `enable_ocr`、`model`（`vlm` 默认/`pipeline`/`MinerU-HTML`）、`output_dir`。

返回：单文件默认内联 Markdown 正文（`content`、`content_chars`、`truncated`）；批量或超长内容落盘并返回 `extract_path`。配套工具 `get_ocr_languages`（109 语种清单）。

HTTP 传输（Streamable HTTP）握手要点：initialize → `mcp-session-id` 响应头 → notifications/initialized → tools/call；每次 POST 都要带 session 头和 `Accept: application/json, text/event-stream`，结果在 SSE `data:` 行里。

## 参数（关键）

| 参数 | 取值 | 说明 |
|------|------|------|
| file_sources | string \| {source, pages} 数组 | 本地路径或 URL |
| pages | "3" / "1-10" | 仅 PDF |
| model | vlm（默认，推荐）/ pipeline / MinerU-HTML | 韩文等用 pipeline + 指定 OCR 语种 |
| format(CLI) | md,json,html,latex,docx 逗号分隔 | 默认 md |

## 返回值 / 边界

- 返回 Markdown 正文 + 资产路径；`truncated: true` 时去落盘路径拿全量。
- 表格是 HTML 片段、公式是 LaTeX，直接喂给 LLM 前不用再转。
- 解析在 MinerU 云端完成：**文件内容会上传到 mineru.net**（结果仅临时缓存、不用于训练）。涉密文件禁止走本通道。
- 超限（>200MB/>600 页）会报错；批量并发 `--concurrency` 尚未生效。
- 输出目录默认 `~/mineru-downloads`（VPS 为 `/root/mineru-downloads`）。

## 相关

检索/深读解析产物用 [mineru-document-explorer]；MCP 服务运维用 [mineru-mcp]。

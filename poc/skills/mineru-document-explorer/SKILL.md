---
name: mineru-document-explorer
description: "Agent 原生知识引擎：跨库混合检索（BM25+向量+重排）、单文档深度阅读（目录/分页/文内检索/元素提取）、LLM Wiki 知识组织。触发词：文档检索、深度阅读、doc_toc、文内搜索、建 wiki、知识库问答（已解析文档）。用 qmd CLI 或 qmd-mcp 15 工具。"
metadata:
  poc_version: "0.1"
---

# mineru-document-explorer

## 渐进加载合同

L1 摘要（YAML description）→ L2 本正文 + 需要时读 `references/official-skill.md`（官方 15 工具完整决策树）→ L3 调用时展开参数。

## 名称

`mineru-document-explorer`

## 描述

MinerU 官方 Agent 原生知识引擎（opendatalab/MinerU-Document-Explorer，npm 包 `mineru-document-explorer`，CLI 名 `qmd`）。三组能力：

1. **Retrieval**：`query`（混合检索：BM25+向量+LLM 重排+查询扩展）、`get`、`multi_get`、`status`
2. **Deep Reading**：`doc_toc`、`doc_read`、`doc_grep`、`doc_query`、`doc_elements`、`doc_links` —— 不整本加载，按目录/页码/命中地址读
3. **Knowledge Ingestion**：`wiki_ingest`、`doc_write`、`wiki_lint`、`wiki_log`、`wiki_index` —— LLM 维护的 wiki 知识库

支持 Markdown/PDF/DOCX/PPTX。PDF 深读自动走 MinerU Cloud（设了 `MINERU_API_KEY` 时）解析，PyMuPDF 兜底。

## 触发词

- 文档检索 / 全库搜索 / 跨文档找
- 深度阅读 / 文档目录 / 读第 N 页 / 文内搜索
- 提取文档中的表格 / 图片 / 公式元素
- 建 wiki / 知识整理 / 知识库健康检查
- 已入库文档的问答（先检索再精读）

## 调用通道

| 通道 | 位置 |
|------|------|
| MCP HTTP（推荐，模型常驻免冷启动） | VPS `http://localhost:8181/mcp`（pm2 `qmd-mcp`，监听 `[::1]`，本机访问用 localhost）；本机 `qmd mcp --http --daemon` 同端口 |
| MCP stdio | `qmd mcp`（客户端拉起子进程） |
| CLI（注意：每次调用重新加载模型，慢 5-15s） | 本机 `qmd`（需 `export PATH=~/.local/qmd-py/bin:$PATH`，pymupdf 依赖在该 venv）；VPS `export PATH=/root/qmd-py/bin:$PATH` |

Agent 工作流一律优先 MCP HTTP。

## 决策树（速查）

```text
要找什么？
├─ 跨文档找 → query（简单串）/ 检索文档结构用 status
├─ 拿整份小文档 → get / multi_get
└─ 大文档内定位 → doc_toc 起步 → doc_read 按地址读
     ├─ 知道关键词 → doc_grep 得地址 → doc_read
     ├─ 语义模糊 → doc_query 得地址 → doc_read
     └─ 要表格/图/公式 → doc_elements
建 wiki → wiki_ingest → doc_read 关键节 → doc_write(带 source) → wiki_lint → wiki_index
```

## 本部署已建集合

| 集合 | 路径 | mask |
|------|------|------|
| VPS `kb-agent-docs` | `/root/.qwenpaw/workspaces/kb-agent` | `**/*.pdf` |
| 本机 `bank-samples` | `~/Desktop/aicode/shunde/kb_store/bank_samples` | `**/*.{md,pdf,docx,pptx}` |

新集合：`qmd collection add <dir> --name <n> --mask '**/*.{md,pdf,docx,pptx}'` 然后 `qmd update`。**给 PDF 建集合必须装过 python 依赖（pymupdf 等）和 `mineru-open-sdk`，否则静默索引 0 个文件**。

## query 语法

- 单行：`query "历史上技术革命与金融泡沫的规律"`（自动扩展）
- 结构化（多行）：`intent:` / `lex:`（关键词+词组+-排除）/ `vec:`（语义）/ `hyde:`（假设答案）
- 结果带 `qmd://collection/file` 路径、`#docid`、score；`minScore: 0.5` 过滤低置信。

## 地址体系（doc_read 的入参）

`line:45-120`（Markdown）、`page:3` / `pages:0`（PDF，0 起）、`slide:5`（PPTX）。地址一律来自 `doc_toc`/`doc_grep`/`doc_query` 的返回，不要凭空造。

## 边界 / 注意

- `qmd search` 是纯 BM25（秒回，模型未下载时可用）；`query` 首次要下 ~2GB 模型（embeddinggemma + reranker + query-expansion，已在本机与 VPS 缓存）。
- doc-* 命令只对**已索引集合内**的文件生效；未索引报 "File exists but is not indexed"。
- 索引对文件名做归一化（如 `东吴证券_AI经济学…pdf` → `东吴证券-ai经济学…pdf`），以 `qmd ls` 结果为准。
- 集合目录是 raw 只读源；写操作只有 wiki 的 `doc_write`。
- 本地索引 DB：`~/.cache/qmd/index.sqlite`（CLI 与 MCP daemon 共享，需同一用户）。

## 相关

解析新文档进库用 [mineru-document-parser]；MCP 服务运维用 [mineru-mcp]；完整官方工具文档见 `references/official-skill.md`。

---
name: kb-qa-bank
description: "当用户要对 PDF/扫描件/带表或带图的文档做知识库入库、检索、缺块召回或多模态问答时使用。触发词：知识库、PDF问答、多模态文档、缺块召回。先调用 kb-qa MCP 入库再检索。"
metadata:
  poc_version: "0.1"
---

# kb-qa-bank

顺德农商行 POC：多模态文件问答助手 Skill。通过 `kb-qa` MCP 完成文档解析、三库入库与混合检索，覆盖缺块漏块、表/图+页码章节、极简短句、概括性总体四类问答。

## 名称

`kb-qa-bank`

## 描述

面向银行 POC 演示场景的多模态知识库技能：用户提供工作区内的 PDF（原生文本、扫描页、含表格或图片），要求建库、检索或问答时启用本技能。处理前必须走 `kb-qa` MCP，路径限制在 `POC_WORKSPACE` 沙箱内。

## 触发词

以下意图应触发本技能（示例，不限于此）：

- 知识库
- PDF问答
- 多模态文档
- 缺块召回
- 扫描件 OCR 入库
- 按文档 ID / 章节 / 页码检索
- 问表格或图片并要求来源页码
- 信贷政策 / 逾期认定 / 经营贷款利率 / 概括信贷文档

## 演示语料（已放进工作区，不要再满盘搜索）

用户说「信贷」「信贷文件」「信贷政策」时，**不要 glob 全盘、不要编造找不到**。直接用已入库文档：

| 用户说法 | 工作区文件 | `doc_id` |
|----------|------------|----------|
| 信贷 / 信贷政策 / 逾期90天 | `信贷政策.pdf` | `credit-policy` |
| 表格 / 经营贷款利率 / RATECHART | `产品定价.pdf` | `pricing` |
| 东吴证券 / AI 金融风险 | `东吴证券_AI经济学.pdf` | 已入库则按 search 命中 |

问答顺序：

1. 先 `answer_knowledge(query=用户原话, doc_id=上表)`（语料已入库则足够）
2. 若返回无命中，再 `ingest_document(path=工作区里的绝对路径, doc_id=上表)` 后重问
3. 路径必须在 `POC_WORKSPACE` 内；本 POC 的工作区就是 Default Agent 目录，文件名就是 `信贷政策.pdf`

## 参数

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| 文件路径 | string | 工作区内的 `.pdf` 路径 |
| 问题 | string | 自然语言问题，覆盖缺块、表/图、短句、概括 |
| doc_id | string | 可选文档 ID；缺省用文件名 |
| chapter | string | 可选章节过滤 |
| page_from / page_to | int | 可选页码范围，0 表示不限制 |
| mode | string | `hybrid` / `bm25` / `text` / `image` |

### 输出

| 产出 | 说明 |
|------|------|
| 答案 | 带页码（及章节，若有）的文字结论 |
| 命中块 | chunk_id / page / chapter / text / kind |

## 返回值

成功时返回：

1. **文字答案**：直接回答用户问题，表/图问必须带来源页码。
2. **来源列表**：`page`、`chapter`（能解析到则有）、`chunk_id`。
3. **入库摘要**：`ingest_document` 返回块数与实际后端名（`elasticsearch`/`mysql`/`local` 等，未接通则如实为 local fallback）。

失败时返回可读错误（路径越界、MinerU/Embedding 端点超时、文件无法打开），不编造切块或命中。

## 边界条件

- **只处理工作区 PDF**：路径必须落在 `POC_WORKSPACE`；越界立即拒绝。
- **不冒充活路中间件**：ElasticSearch / MySQL / GALASYBASE / MinerU 未接通时走本地 fallback，答案里不得写成「已写入行方集群」。
- **扫描页必须 OCR**：原生 extract 为空的页走 OCR；本机无 tesseract 时说明原因，不填假字。
- **缺块补召回**：索引段落被截断或缺失时，用邻块/重叠块补召回，禁止只靠单条被删块。
- **概括题不能只回 top-1**：总体/综述类问题必须覆盖多页或多块要点。
- **不修改 QwenPaw 内核**：本技能只通过 MCP 旁路接入。

## 与 MCP `kb-qa` 的协作流程

配置见 `poc/config/mcp-kb-qa.json`。每次处理按顺序调用：

1. **`parse_document`**（可选预览）
   - 入参：文件路径、可选 `doc_id` / `max_pages`
   - 查看切块是否带 `page` / `chapter`，表格是否同时有 csv/html/json，页图是否落地。

2. **`ingest_document`**
   - 入参：文件路径、可选 `doc_id` / `max_pages`
   - 页图进对象存储，元数据进关系库，块向量进向量库，文档–章节–页进图库。

3. **`search_knowledge`**
   - 入参：`query`，可选 `doc_id` / `chapter` / `page_from` / `page_to` / `mode`
   - 同时走关键词/BM25、文本向量、图像向量；命中必须带页码。

4. **`answer_knowledge`**
   - 入参：`query` 与同样的过滤项
   - 用于四类问答：缺块漏块、多模态（表/图+页码章节）、极简短句（3–5 字）、概括性总体。

推荐流程：

```
用户指定 PDF + 问题
        │
        ▼
parse_document（可选，确认切块/页图）
        │
        ▼
ingest_document ──失败──▶ 返回 MCP 错误，结束
        │ 成功
        ▼
search_knowledge 或 answer_knowledge
        │
        ▼
返回答案 + 页码/章节来源
```

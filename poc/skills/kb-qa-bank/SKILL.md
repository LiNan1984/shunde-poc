---
name: kb-qa-bank
description: "L1 skill列表摘要：PDF/扫描件多模态入库检索。触发词：知识库、PDF问答、缺块召回、哪张表。先 kb_qa__ mcp列表，文件摘要后再看图详情。"
metadata:
  poc_version: "0.1"
---

# kb-qa-bank

## 渐进加载合同

上下文按 **L1 / L2 / L3** 渐进式工具加载。顺序（字面）：

skill列表摘要 → skill → mcp列表namespace前缀 → 详细mcp → 文件摘要 → 文件详情

稳定前缀（L1 目录始终不变）提高缓存命中率，前缀一致性更省 token，提高 token 经济型 ROI。

- **L1 skill列表摘要**：仅 YAML `description`。禁止把完整 MCP schema 预埋进摘要。
- **L2 skill**：先读本正文，再读 **mcp列表**（**namespace前缀** `kb_qa__`）：`kb_qa__parse_document`、`kb_qa__ingest_document`、`kb_qa__ingest_spreadsheet`、`kb_qa__search_knowledge`、`kb_qa__answer_knowledge`、`kb_qa__analyze_page`。
- **L3 详细mcp**：调用时再展开入参。**文件摘要** 用 `kb_qa__parse_document`、`kb_qa__search_knowledge`；**文件详情** 再用 `kb_qa__analyze_page` 看页图。

顺德农商行 POC：多模态文件问答助手 Skill。通过 `kb-qa` MCP 完成文档解析、三库入库与混合检索，覆盖缺块漏块、表/图+页码章节、极简短句、概括性总体四类问答。

## 名称

`kb-qa-bank`

## 描述

面向银行 POC 演示场景的多模态知识库技能：用户提供工作区内的 PDF（原生文本、扫描页、含表格或图片），要求建库、检索或问答时启用本技能。工作区内的 Excel/CSV 可用 `ingest_spreadsheet` 只索引文件名、sheet 名、表头和少量样例行，供「哪份文件/哪张表」定位；**筛选、合计、写回仍交给 `excel-qa-bank` 用 pandas 算**，禁止用 RAG 切片当数值答案。路径限制在 `POC_WORKSPACE` 沙箱内。

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
- 哪份 Excel / 哪张 sheet 里有某列或某网点（先定位文件，再交给 excel-qa-bank）

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
3. 命中块 `kind=table/image` 时，用 `analyze_page(doc_id=上表, page=命中页, query=用户追问)` 看页面图作答精确数字
4. 路径必须在 `POC_WORKSPACE` 内；本 POC 的工作区就是 Default Agent 目录，文件名就是 `信贷政策.pdf`

## 参数

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| 文件路径 | string | 工作区内的 `.pdf` 路径；表格定位时为 `.xlsx` / `.csv` |
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

- **只处理工作区文件**：路径必须落在 `POC_WORKSPACE`；越界立即拒绝。PDF 走 `ingest_document`；Excel/CSV 走 `ingest_spreadsheet`（元数据 only）。
- **表格数值题不走 RAG**：命中块只用来 locate 文件/sheet；聚合、筛选、写回交给 `excel-qa-bank` + pandas / openpyxl。
- **不冒充活路中间件**：ElasticSearch / MySQL / GALASYBASE / MinerU 未接通时走本地 fallback，答案里不得写成「已写入行方集群」。
- **扫描页必须 OCR**：原生 extract 为空的页走 OCR；本机无 tesseract 时说明原因，不填假字。
- **缺块补召回**：索引段落被截断或缺失时，用邻块/重叠块补召回，禁止只靠单条被删块。
- **概括题不能只回 top-1**：总体/综述类问题必须覆盖多页或多块要点。
- **看图作答不编造**：未配置视觉模型（缺 `POC_CHAT_URL` / `POC_ALIYUN_API_KEY` / `POC_VISION_MODEL`，见 `~/.qwenpaw.secret/middleware.env`）时，`analyze_page` 返回 `error_type=config`，如实降级为切块文字答案并说明「图中数字未能核对」，不得编造图中数字；视觉端点调用失败同理（`error_type=network`），禁止拿文字块冒充看图结论。
- **不修改 QwenPaw 内核**：本技能只通过 MCP 旁路接入。

## 与 MCP `kb-qa` 的协作流程

配置见 `poc/config/mcp-kb-qa.json`。每次处理按顺序调用：

1. **`parse_document`**（可选预览）
   - 入参：文件路径、可选 `doc_id` / `max_pages`
   - 查看切块是否带 `page` / `chapter`，表格是否同时有 csv/html/json，页图是否落地。

2. **`ingest_document`**
   - 入参：文件路径、可选 `doc_id` / `max_pages`
   - 页图进对象存储，元数据进关系库，块向量进向量库，文档–章节–页进图库。仅用于 PDF。

3. **`ingest_spreadsheet`**
   - 入参：工作区 `.xlsx` / `.csv` 路径、可选 `doc_id` / `sample_rows`（默认 5）
   - 只索引文件名、sheet 名、表头、样例行，**不把每一行数据灌进向量库**。

4. **`search_knowledge`**
   - 入参：`query`，可选 `doc_id` / `chapter` / `page_from` / `page_to` / `mode`
   - 同时走关键词/BM25、文本向量、图像向量；命中必须带页码。对表格：用命中的 `doc_id` / 路径 / sheet（`chapter`）**定位文件**，不要直接当合计结果。

5. **`answer_knowledge`**
   - 入参：`query` 与同样的过滤项
   - 用于四类问答：缺块漏块、多模态（表/图+页码章节）、极简短句（3–5 字）、概括性总体。不用于 Excel 加减乘除。

6. **`analyze_page`**（看图作答）
   - 入参：`query` 必填；`doc_id` + `page`（推荐，来自 search/answer 命中的页码）或 `path`（工作区内页面 PNG 绝对路径）二选一定位页面图
   - 把该页 PNG 喂给视觉模型（`POC_VISION_MODEL`），只依据图片内容作答：图中数字原样引用，图里没有的如实说没有。当 `search_knowledge` / `answer_knowledge` 命中 `kind=table` / `kind=image` 的块、而用户追问精确数字或图上细节时，用本工具看页面图作答，不再只依赖切块文字。

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

用户问「哪份 Excel 里有 XX」/ 多文件定位
        │
        ▼
ingest_spreadsheet（元数据）
        │
        ▼
search_knowledge 定位文件 / sheet
        │
        ▼
交给 excel-qa-bank：describe_workbook → pandas 计算
```

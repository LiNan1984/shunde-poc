# Excel 问答能力链交接文档

| 项 | 内容 |
|----|------|
| 范围 | 场景① Excel/CSV 问答的**能力层与测量层**：excel-guard MCP、excel-qa-bank skill、kb 表格元数据路由、黄金回归集 |
| 日期 | 2026-09-15 |
| 测试健康度 | `pytest poc/tests tests` → **454 passed, 1 skipped**（本文档提交时） |
| 相关文档 | [`HANDOFF.md`](HANDOFF.md)（开发总览）· [`Excel问答能力交接与演示query.md`](Excel问答能力交接与演示query.md)（现场演示 query，含真实列名）· [`poc/README.md`](../poc/README.md)（部署步骤）· [`HANDOFF_FOR_AI.md`](HANDOFF_FOR_AI.md)（AI 接手任务卡） |

---

## 1. 一段话讲清设计

Excel 问答**不走**「转 markdown 塞上下文」或「数据行进知识库 RAG」——筛选/合计/写回是确定性数据操作，代码执行的准确率远高于检索。真正有效的结构是：

```
护栏（损坏/编码/超大，单次调用 preflight）
  → L1 读压缩（describe_workbook：投票表头/合并区域/公式别名/markdown 预览）
  → 有界读取（sheet_to_markdown 行区间，自动附表头；大表按 chunk 计划分段）
  → pandas / openpyxl 对原文件精算（答案来自计算，不来自检索片段）
  → 写后自检（audit_workbook：#REF! 等 must_fix、公式硬编码 review）
多文件场景：kb ingest_spreadsheet 只索引「文件名/sheet/表头/样例」→ 检索定位文件 → 回到 pandas 精算
```

方法论出处：Shortcut 电子表格 Agent 的「上下文分层缓存 / 单一执行入口 / 读是压缩、写要反馈」原则，结合本 POC 已有的护栏三件套。

## 2. 代码地图

| 文件 | 内容 |
|------|------|
| `poc/excel_guard_mcp/guards.py` | 护栏三件套 + 沙箱（`_resolve_allowed_path`/`_open_contained`，O_NOFOLLOW 防 TOCTOU） |
| `poc/excel_guard_mcp/readers.py` | **L1 能力核心**：`describe_workbook` / `sheet_to_markdown` / `audit_workbook` / `preflight_workbook`（库函数与 MCP 双通道） |
| `poc/excel_guard_mcp/officecli_bridge.py` | officecli 桥接（透视表/图表/公式求值/schema 校验/截图渲染），同套沙箱护栏 + 动词白名单 |
| `poc/excel_guard_mcp/server.py` | MCP 工具注册（当前 **9 个**，见下表） |
| `poc/kb_mcp/spreadsheet.py` | `parse_spreadsheet_metadata`：每 sheet 产一条 `sheet_meta` chunk |
| `poc/kb_mcp/ingest.py` | `ingest_spreadsheet`：元数据入库（复用 `_commit_chunks`） |
| `poc/evals/qa_set.py` | 黄金问答集：确定性数据源、期望值同源计算、写回 verifier |
| `poc/evals/score.py` | 评分器（无 LLM，数字容差 / 文本精确 / write 开文件校验） |
| `scripts/excel_qa_eval.py` | 评测 CLI（build / answers / self-test） |
| `poc/fixtures/qa_fixtures/` | 评测工作簿 + `qa_golden.json` + `baseline_answers.json` + `golden_outputs/` |
| `poc/skills/excel-qa-bank/SKILL.md` | L2 技能文档（渐进加载合同 + 流程 + 边界） |

## 3. MCP 工具清单（excel-guard，9 个）

| 工具 | 作用 | 备注 |
|------|------|------|
| `detect_corrupt_workbook` | 损坏/旧 .xls 检测 | 损坏即终止 |
| `detect_encoding` | CSV 编码识别 | 勿默认 UTF-8 硬读 |
| `chunk_large_workbook` | >5000 行分块计划 | 行号与 slice 对齐 |
| `describe_workbook` | 结构视图（投票表头/合并区域/公式别名/预览） | **读前必调，禁止盲跑 pandas** |
| `sheet_to_markdown` | 行区间导出（区间外自动附投票表头） | 上限 2000 行 |
| `edit_workbook` | officecli 批量编辑（动词白名单） | 需 `officecli` 在 PATH 或 `OFFICECLI_BIN` |
| `inspect_workbook` | officecli 结构 inspect | 同上 |
| `validate_workbook` | OpenXML schema 校验 | 同上 |
| `render_workbook` | 渲染截图（视觉复核回路） | 同上 |

**代码内 helper（非 MCP 工具，import 使用）**：`preflight_workbook`（三护栏单次调用、损坏短路）、`audit_workbook`（写后必做）。新增 MCP 工具时**必须同步** `scripts/mcp_stdio_smoke.py` 与 `tests/test_mcp_stdio_smoke.py` 的工具数（教训：5→9 演进时曾出现 3 处过期断言致测试红）。

## 4. 黄金回归集（测量层）

**14 条问答对，覆盖全部已上线能力，无裸奔能力：**

| 组 | 题号 | 考什么 |
|----|------|--------|
| 干净明细 | q01-q05 | 筛选/合计/极值/分组/日期切片（销售明细.xlsx，40 行） |
| 多级合并表头 | q06-q07 | 表头投票跳过标题行与合并年份带（分区域汇总.xlsx） |
| 未缓存公式列 | q08-q09 | 公式补位预览 + agent 自算 B×C（公式列.xlsx） |
| GBK 编码 | q10, q13 | 编码识别与转存（网点名单.csv） |
| 多文件路由 | q14 | ingest_spreadsheet → 检索定位文件名 |
| 写回 | q11-q13 | verifier 打开 agent 输出文件逐行校验内容 |

**设计不变量（测试强制）：**
1. 期望值与工作簿出自**同一份内存数据**（`qa_set.py` 顶部列表），永不漂移；
2. 每题期望值由测试用**独立读取路径**（pandas/openpyxl 直读落盘文件）重算验证；
3. q14 答案唯一性：其他文件不得含「部门」列（有不变量测试）。

**用法：**

```bash
.venv/bin/python scripts/excel_qa_eval.py --build          # 生成 fixtures + 打印题目
.venv/bin/python scripts/excel_qa_eval.py --answers a.json # 评分（读类填值，写类填输出文件路径）
.venv/bin/python scripts/excel_qa_eval.py --self-test      # 黄金答案必须 100%
```

**基线：14/14 = 100%**（读类走 skill 规定流程 preflight→describe→pandas→audit；写回 3 题由 `build_write_golden` 黄金输出代表）。**改动 excel-qa / excel-guard 任何能力后必须重跑评分**，准确率变化是唯一的验收语言。

## 5. 环境依赖与红线

- `POC_WORKSPACE` 沙箱：所有路径必须落在工作区内，越界拒绝且**不回显路径**（防提示注入）。
- officecli：桥接四件套需要 `officecli` 二进制（PATH 或 `OFFICECLI_BIN`）；缺失时该四件套返回 `ok=false, issue=officecli_unavailable`，**读/护栏/audit 不受影响**。
- 禁止把 API Key 写进仓库/配置（密钥走 `QWENPAW_SECRET_DIR` / env）。
- 大文件红线：>5000 行必须走分块；`sheet_to_markdown` 单次 ≤2000 行；audit 上限 10 万行。
- 写回后不跑 `audit_workbook` 就交付 = 违规；`must_fix` 未清零不得交付。

## 6. 已知未决与下一步

1. **QwenPaw agent 实跑对比**：基线 14/14 是确定性流程的成绩；真实 LLM agent 的得分尚未测——这是黄金集存在的意义，接入 QwenPaw Console 后跑 `--answers` 即得第一份真实准确率。
2. **模型漂移监测**：QwenPaw submodule 已随上游到 v2.2.1-beta（测试已放宽为钉 major 版本线 v2.x）；模型升级后重跑回归集对比。
3. **评测扩展方向**：大文件分块题（>5000 行）、officecli 桥接四件套的写回题、跨文件聚合题。
4. **并行线**：kb-qa 侧（中间件 ES/MySQL、reranker、图像向量、`analyze_page` 视觉问答、kb 黄金评测 `scripts/kb_eval.py`）由对应文档与 `poc/tests/test_kb_*.py` 覆盖，见 [`poc/README.md`](../poc/README.md) Phase 5。
5. **未入库文件**：仓库根目录的个人材料（PDF/批注 docx/zip 等）有意不提交，接手者勿 `git add -A`。

# 顺德农商行 POC 开发计划（分阶段）+ Phase 1 Excel 实施计划

> **For agentic workers:** Use subagent-driven development for Phase 1 tasks. Checkbox steps track progress.  
> **依据：** `docs/qwenpaw-poc-modification-evaluation.md`、`docs/poc-completion-gap-qa.md`、POC 选型方案。

**Goal:** 在 `poc/` 落地可接入 QwenPaw v2.0.0 的第一批能力：Excel 异常 MCP + Excel 问答 Skill + 接线配置；后续阶段按优先级推进报告/运营/部署/知识库/HARNESS。

**Architecture:** POC 扩展放在仓库根目录 `poc/`，**不 fork 改 QwenPaw 核心**。MCP 以 stdio FastMCP 进程对外；Skill 以 `SKILL.md` 目录供技能池/外部 `skill_paths` 挂载；`poc/config/` 提供可粘贴进 Console 的 `mcpServers` JSON。

**Tech Stack:** Python 3.10+、`mcp` (FastMCP)、openpyxl、pandas、chardet、pytest；运行时宿主为 QwenPaw v2.0.0。

## Global Constraints

- QwenPaw 版本锁定 **v2.0.0**（本地 `QwenPaw/` 检出）。
- **禁止**把 API Key / Bearer 写入跟踪文件；模型密钥仅环境变量 / `QWENPAW_SECRET_DIR`。
- Phase 1 **不做** ES/MySQL/GALASYBASE、运营 HOOK、报告图表、镜像裁剪（列入后续阶段）。
- 验收对齐 POC：三种异常 Excel 正确提示；Skill 文档含名称/描述/触发词/参数/返回值/边界。

---

## 总览：分阶段路线图

| 阶段 | 内容 | 人·日（估） | 状态 |
|------|------|-------------|------|
| **P0** | 模型/MaaS 接入说明（已有评估+探针） | 0.5～1 | 文档已备 |
| **P1（本次）** | Excel Skill + 异常 MCP + 接线 | 4～6 | **代码已落地（待 Console 挂载演示）** |
| **P2** | 报告可视化 Skill（docx+表+图） | 4～6 | 未开始 |
| **P3** | 运营助手 MCP + Skill + HOOK 埋点 | 5～7 | 未开始 |
| **P4** | 后端 `/health` + 镜像精简截图 | 3～5 | 未开始 |
| **P5** | 多模态知识库旁路（最大块） | 12～18 | 未开始 |
| **P6** | HARNESS 三方案讲义与调参 | 2～3 | 未开始 |

**日历（2 人）：** P1 约 1 周内可演示；全量 demo-ready 仍约 3.5～5.5 周（见 gap-qa）。

---

## Phase 1 文件地图

```
poc/
├── README.md                          # 如何挂到 QwenPaw
├── requirements.txt
├── excel_guard_mcp/
│   ├── __init__.py
│   ├── server.py                      # FastMCP 入口
│   ├── guards.py                      # corrupt / encoding / chunk 逻辑
│   └── pyproject 或由根 requirements 安装
├── skills/excel-qa-bank/
│   └── SKILL.md                       # POC Skill 文档
├── config/
│   └── mcp-excel-guard.json           # Console 可导入 mcpServers
├── fixtures/                          # 三种异常样例生成脚本产出
│   ├── corrupt.xlsx
│   ├── encoding_latin1.csv            # 或 xls 变体说明
│   └── large_chunk_demo.xlsx
└── tests/
    ├── test_excel_guards.py
    └── test_skill_doc.py
```

---

### Task 1: excel-guard 核心逻辑（TDD）

**Files:**
- Create: `poc/excel_guard_mcp/guards.py`
- Test: `poc/tests/test_excel_guards.py`

**Interfaces:**
- Produces:
  - `detect_corrupt_workbook(path: str) -> dict` — `{"ok": bool, "issue": str, "message": str}`
  - `detect_encoding(path: str) -> dict` — `{"encoding": str, "confidence": float, "message": str}`
  - `chunk_large_workbook(path: str, max_rows: int = 5000) -> dict` — `{"needs_chunking": bool, "total_rows": int, "chunks": list[dict], "message": str}`

- [x] **Step 1:** 写失败测试（损坏文件、非 UTF 文本表、超大行数）
- [x] **Step 2:** 实现 `guards.py` 使测试通过
- [x] **Step 3:** 用脚本生成 `poc/fixtures/` 样例

### Task 2: FastMCP server 暴露三工具

**Files:**
- Create: `poc/excel_guard_mcp/server.py`
- Create: `poc/excel_guard_mcp/__init__.py`
- Create: `poc/config/mcp-excel-guard.json`
- Create: `poc/requirements.txt`

**Interfaces:**
- Consumes: Task 1 guards
- Produces: MCP tools `detect_corrupt_workbook`, `detect_encoding`, `chunk_large_workbook`

- [x] **Step 1:** FastMCP 注册三工具，返回 JSON 友好 dict
- [x] **Step 2:** `mcp-excel-guard.json` 指向 `python -m poc.excel_guard_mcp.server` 或绝对脚本路径
- [x] **Step 3:** 冒烟：`python -c` 导入 server 模块成功

### Task 3: excel-qa-bank Skill

**Files:**
- Create: `poc/skills/excel-qa-bank/SKILL.md`
- Test: `poc/tests/test_skill_doc.py`

**Interfaces:**
- Produces: 符合 QwenPaw Skill frontmatter（name/description）+ 正文含触发词、参数、返回值、边界；说明优先调用 excel-guard MCP 再做问答

- [x] **Step 1:** 写 SKILL.md（中文，POC 验收字段齐全）
- [x] **Step 2:** 测试断言 frontmatter 与必填章节存在

### Task 4: 接线 README + 仓库测试入口

**Files:**
- Create: `poc/README.md`
- Modify: 根 `tests/` 可增加薄包装或文档说明 `pytest poc/tests`

- [x] **Step 1:** README 写清 Console 导入 MCP、skill_paths / 技能池广播步骤
- [x] **Step 2:** `pytest poc/tests -v` 全绿
- [x] **Step 3:** Commit

---

## Phase 1 完成定义（DoD）

1. `pytest poc/tests -v` 通过。  
2. 三种异常路径均有**确定性**提示文案（损坏 / 编码 / 分块）。  
3. `SKILL.md` 含名称、描述、触发词、参数、返回值、边界。  
4. `mcp-excel-guard.json` 可被人工粘贴进 QwenPaw MCP 导入。  
5. 不提交任何 API Key。

---

## 后续阶段（仅提纲，本轮不实施）

- **P2 报告：** `poc/skills/report-viz/` + matplotlib 插图脚本。  
- **P3 运营：** `poc/plugins/ops-telemetry/` Runtime Hook + 四类埋点。  
- **P4 部署：** 精简 Dockerfile patch + `/health` 路由插件。  
- **P5 知识库：** 旁路服务 + `kb-rag` MCP。  
- **P6 HARNESS：** 讲义 Markdown + 调参 checklist。

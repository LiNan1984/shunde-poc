# 交接文档（面向接手开发的 AI Agent）

| 项 | 内容 |
|----|------|
| 项目 | 顺德农商行 POC — QwenPaw v2.0.0 旁路扩展 |
| 文档日期 | 2026-03-22（Agent Team 并行开发第二轮之后） |
| 上一版总交接 | [`HANDOFF.md`](HANDOFF.md)（业务背景/验收口径以它为准） |
| 本文用途 | **给下一个写代码的 AI 直接开工用**：环境、基线、任务卡、红线 |
| 基线测试 | **101 passed**（`pytest poc/tests tests/`） |

---

## 0. 一句话现状

Phase 1（Excel 异常 MCP + 问答 Skill）已完成并经多 agent 测试深化与安全加固；Phase 2（报告可视化 MCP + Skill）**脚手架已落地、测试全绿**，但未挂 Console 彩排；P3～P6 未开始。

---

## 1. 30 秒开工（先跑绿基线，再做任何事）

```bash
cd <REPO_ROOT>            # 本机当前为 /Users/linan/Desktop/aicode/shunde
source .venv/bin/activate # 必须用 venv！系统 python3 是 3.14 且没装依赖
pytest poc/tests tests/ -q
# 期望：101 passed
```

若 venv 缺失或依赖不全：

```bash
uv venv && source .venv/bin/activate
uv pip install -r poc/requirements.txt
git -C QwenPaw describe --tags --exact-match   # 期望：v2.0.0
```

**任何任务完成前，`pytest poc/tests tests/ -q` 必须保持全绿。新增功能先写测试（RED）再实现（GREY/GREEN）。**

---

## 2. 仓库结构（当前事实）

```
shunde/
├── QwenPaw/                         # v2.0.0 宿主框架（被 .gitignore，勿改内核）
├── poc/
│   ├── excel_guard_mcp/             # Phase 1 MCP：损坏/编码/分块（已加固）
│   │   ├── guards.py                #   核心逻辑 + POC_WORKSPACE 沙箱
│   │   └── server.py                #   FastMCP("excel-guard")，3 工具
│   ├── report_mcp/                  # Phase 2 MCP：报告可视化（脚手架，7 工具）
│   │   ├── charts.py                #   matplotlib Agg：柱/折/饼/散点/热力
│   │   ├── crosstab.py              #   pandas pivot_table 交叉表
│   │   ├── docx_gen.py              #   python-docx 组装（含中文字体处理）
│   │   └── server.py                #   FastMCP("report-visualizer")
│   ├── skills/
│   │   ├── excel-qa-bank/SKILL.md   # Phase 1 Skill
│   │   └── report-visualizer/SKILL.md  # Phase 2 Skill
│   ├── config/
│   │   ├── mcp-excel-guard.json     # 挂载模板（<REPO_ROOT> 占位符）
│   │   └── mcp-report-visualizer.json
│   ├── fixtures/                    # 异常样例（corrupt.xlsx / GBK CSV / 大表）
│   └── tests/                       # 89 个测试（见下）
├── docs/
│   ├── HANDOFF.md                   # 总交接（业务/验收/密钥约定）
│   ├── poc-completion-gap-qa.md     # 24 条验收标准 + 工期
│   ├── qwenpaw-poc-modification-evaluation.md  # 扩展点地图
│   └── superpowers/
│       ├── phase1-security-review.md          # 安全审计详情（必读）
│       ├── p4-deployment-research.md          # /health 与镜像预研
│       ├── 2026-03-22-agent-team-parallel-dev.md
│       └── plans/
│           ├── 2026-03-22-poc-phase1-excel-plan.md
│           └── 2026-03-22-poc-phase2-report-visualizer-plan.md
└── tests/                           # 12 个文档结构性测试
```

测试构成（101 个）：`test_excel_guards.py` 41 + `test_mcp_server.py` 32 + `test_report_mcp.py` 8 + `test_skill_doc.py` 8 + `tests/` 文档测试 12。

---

## 3. 必须遵守的架构约定（改代码前读）

1. **不 fork QwenPaw 内核**。所有扩展放 `poc/`，通过 MCP / Skill 旁路接入。
2. **沙箱契约**：每个读/写文件的 MCP 工具必须经 `_resolve_allowed_path()`，只允许 `POC_WORKSPACE`（或 `QWENPAW_WORKING_DIR`）内路径。`report_mcp/charts.py` 已有同款实现，新 MCP 照抄。
3. **返回结构契约**（下游 Skill/测试依赖，勿随意改 key 名）：
   - 损坏类：`{"ok": bool, "issue": str, "message": str}`
   - issue 取值：`path_denied / invalid_path / missing / corrupt / unsupported / unreadable / too_large / unsafe_archive`
   - 编码类：`{"encoding", "confidence", "message"}`
   - 分块类：`{"needs_chunking", "total_rows", "max_sheet_rows", "chunks", "message"}`（`total_rows` 是兼容别名，保留）
   - 报告类：`{"ok", "message", ...}` + 各自字段（`output_path` / `table` 等）
   - 所有 `message` **中英双语**，面向银行演示观众。
4. **MCP = 确定性计算层；Skill = LLM 编排层**。Skill 文档（SKILL.md）必须含 frontmatter（`name`/`description`）和四段：**触发词 / 参数 / 返回值 / 边界条件**（有测试强制）。
5. **配置模板用 `<REPO_ROOT>` 占位符**，禁止把本机绝对路径或任何 Bearer/Key 提交进 git。
6. **代码风格**：`from __future__ import annotations`、类型标注、中英双语 docstring、无密钥。

---

## 4. 任务卡（可并行领取）

> 颗粒度按「一个 AI 会话能独立完成并验收」设计。**任务 A/B/C/D 互相独立，可并行**；每个任务都要求测试先行、基线不破。

### 任务 A — Phase 2 收尾到 demo-ready（推荐最先做，2～3 人·日）

**目标：** 让报告可视化助手能现场端到端演示。

1. 补齐 `report_mcp` 错误路径测试，把 `charts.py` 覆盖率从 60% 拉到 ≥85%、`crosstab.py` 从 66% 到 ≥90%：
   - 空数据 / 列缺失 / 非法 data 类型 / 不支持的 aggfunc / 路径越界 / 输出目录不可写
   - 参照 `poc/tests/test_mcp_server.py` 的 `_call_tool` 模式（见 §6.1）给 `report_mcp/server.py` 补一个 `test_report_mcp_server.py`，断言 7 个工具全部注册且可调用。
2. **CSV chunking 缺口（安全审计 M5）**：SKILL.md 声称大 CSV 走 `chunk_large_workbook`，实际只支持 xlsx。给 `chunk_large_workbook` 加 `.csv/.txt` 分支：二进制流式数 `\n`（常量内存），返回同样的 chunk 结构。
3. 端到端彩排脚本：写 `poc/fixtures/report_demo/`（一份销售样例 xlsx/csv + 一个 `scripts/report_demo.py`），命令行一键产出含交叉表 + 五类图的 docx，供无 Console 时演示。
4. 按 `poc/README.md` 步骤把两个 MCP + 两个 Skill 实际挂到 QwenPaw Console（替换 `<REPO_ROOT>`），用 fixtures 手测，把实际截图/遇到的问题回写 `poc/README.md`。

**DoD：** `pytest poc/tests tests/ -q` 全绿；覆盖率达标；`python scripts/report_demo.py` 产出能打开的 docx（含 5 图 1 表）；README 有实测挂载记录。

### 任务 B — 安全技术债（1～2 人·日，独立）

详情读 [`docs/superpowers/phase1-security-review.md`](superpowers/phase1-security-review.md)。按顺序：

1. **H1 TOCTOU**：改为单次 `os.open(path, os.O_RDONLY | os.O_NOFOLLOW)` 拿 fd，把文件对象传给 `zipfile.ZipFile(fh)` / `load_workbook(fh)`（二者都接受 file-like）；删除 `guards.py` 中 `resolve()` 之后不可达的 symlink 复查块（约第 100～130 行，审计确认为死代码）。
2. **M1 fail-open**：`POC_WORKSPACE=/` 或不存在时当前全部放行。首次使用时校验 root 存在且是目录、拒绝 `/`，向 **stderr** 打一条有效 root 日志（stdout 是 MCP JSON-RPC 通道，绝不能污染）。
3. **M6 收尾**：复核 `guards.py` 新增的 `except` 分支，确保 `MemoryError` 不被宽 `except Exception` 吞掉。
4. 每个修复配攻击向量回归测试（参照审计报告末尾「Security tests that should be added」7 条）。

**DoD：** 新增测试覆盖 fd-based 读取（symlink 在检查后被换走时仍读到原 inode）；`POC_WORKSPACE=/` 被拒；全部测试绿。

### 任务 C — P3 运营助手 + HOOK/埋点（5～7 人·日，独立，评委权重高）

**目标：** POC 第三类场景「运营助手（MCP + SKILL + HOOK 四类埋点）」。

1. 先调研 QwenPaw 的 hook/中间件真实扩展点（**不要凭文档想象**）：
   ```bash
   ls QwenPaw/plugins/middleware-demo/      # 官方中间件样例
   grep -rn "hook\|middleware" QwenPaw/src/qwenpaw/ --include="*.py" -l
   ```
2. 四类埋点最低要求（验收口径见 gap-qa）：**调用量/Token 用量、工具调用成败、会话/用户标识、耗时**。实现为旁路日志/JSONL 落盘（`POC_WORKSPACE/telemetry/`），不改内核。
3. 新建 `poc/ops_mcp/`（运营数据问答 MCP，复用沙箱契约）+ `poc/skills/ops-assistant/SKILL.md`（四段齐全）。
4. 测试 + 一个 demo 数据问答剧本。

**DoD：** 四个埋点维度各有测试断言 JSONL 落盘内容；Skill 四段齐全（`test_skill_doc.py` 的 SKILLS 列表要加新条目）；基线全绿。

**注意：** gap-qa 的结论是「缺口主因不是埋点」——埋点是运营助手的子集（约 10～15%），别把整个 P3 做成只有埋点。

### 任务 D — P4 部署：`/health` + 镜像瘦身（3～5 人·日，独立）

预研已完成（[`p4-deployment-research.md`](superpowers/p4-deployment-research.md)）：确认 v2.0.0 只有 `/api/version`，无 `/health`；官方镜像含 XFCE4+Chromium，远超 500MB。

1. **先验证插件机制能否注入 FastAPI 路由**（读 `QwenPaw/plugins/bundle/*/plugin.py`）；可行则写 `poc/plugins/health/`，不可行则做 `poc/deploy/` 下的 entrypoint 旁路（nginx/sidecar），**不要 sed 改内核文件**。
2. `GET /health` 返回 `{"status":"ok"}` + 200，配套启动截图。
3. 写 `poc/deploy/Dockerfile.poc`：multi-stage，runtime 换 `python:slim`，评估去 Chromium/XFCE（先确认演示不需要 Coding Mode 浏览器），装中文字体 `fonts-wqy-zenhei`（P2 docx/图表需要），目标镜像 <500MB。
4. `docker build` 实测体积并记录在文档中。

**DoD：** 容器启动后 `curl /health` = 200；`docker images` 记录 <500MB；步骤文档可复现。

### 任务 E — P1 收尾：12 道 Excel 测题答卷（2～3 人·日）

需求原文在未入 git 的 `.docx`（仓库根目录）里。任务：整理 12 题标准答卷 + Agent 装配剧本（每题：输入文件、预期 MCP 调用顺序、期望答案要点、异常题的护栏文案）。产出 `docs/` 下 markdown，不阻塞代码任务。

### 暂不启动（依赖外部环境）

- **P5 知识库**（12～18 人·日）：等行方给 ES/MySQL/GALASYBASE/MinerU/Embedding 端点。
- **P6 HARNESS**（2～3 人·日）：上下文压缩/长期记忆/沙箱三方案讲义，纯阐述类，随时可做。

---

## 5. 红线（违反会被打回）

- ❌ 提交 Bearer / API Key / `.env` / `providers.json`；密钥只走环境变量或 `QWENPAW_SECRET_DIR`。
- ❌ 把 `<REPO_ROOT>` 替换成的本机绝对路径提交进共享分支（本地另存可以）。
- ❌ 修改 `QwenPaw/` 内核代码。
- ❌ MCP 工具绕过沙箱读 `POC_WORKSPACE` 外文件；stdout 输出任何非 JSON-RPC 内容（logging 一律 stderr，`guards.py` 已有范例 logger）。
- ❌ 提交前基线不是 101+ 全绿；删测试来"修"失败。
- ❌ chardet 给出的结果写成确定结论——它对短样本极不可靠（见 §6.2）。

---

## 6. 这一轮踩过的坑（省你的时间）

### 6.1 FastMCP 工具的程序化测试方法

不要真启动 stdio server。FastMCP 的 API 是协程，用 `asyncio.run` 包在普通同步 pytest 里（无需 pytest-asyncio 插件）：

```python
import asyncio, json
from poc.excel_guard_mcp.server import mcp

def _call_tool(name, arguments):
    result = asyncio.run(mcp.call_tool(name, arguments))
    if isinstance(result, dict):          # 前向兼容结构化返回
        return result
    text = getattr(result[0], "text", None)
    return json.loads(text)

# 注册信息：tools = asyncio.run(mcp.list_tools())，每个有 .name/.description/.inputSchema
```

完整范例：`poc/tests/test_mcp_server.py`（32 个测试，含注册校验、沙箱拒绝、生命周期）。

### 6.2 chardet 置信度陷阱（实测，本机 chardet 7.6.0）

- 纯 ASCII + 少量 latin-1 重音字符的短样本：置信度可低至 **0.08**，且编码被误判成 Windows-1250。
- 中文 GBK（含大量中文）：置信度也只有 **0.16**（报 GB18030），加大样本量无改善。
- **UTF-16：置信度稳定 1.0** —— 需要"高置信度非 UTF-8"断言时用 UTF-16 造样本。
- 演示用 `poc/fixtures/encoding_gbk.csv`；不要写 `confidence >= 0.5` 针对 latin-1/GBK 的断言。

### 6.3 测试环境

- venv Python 3.13.5；系统 python3 是 3.14 且**没装项目依赖**，直接 `python3 -m pytest` 会 import 失败——先 `source .venv/bin/activate`。
- 装包用 `uv pip install ...`（Homebrew Python 受 PEP 668 保护，裸 pip 会报错）。
- 权限位 `chmod 0o000` 目录在 macOS/Python 3.13 上：`Path.resolve(strict=False)` 词法解析不报错，失败发生在后续 `is_symlink()`/`stat()`——写权限类测试时注意错误发生点。
- 稀疏文件（`seek(32MiB)` 写 1 字节）可用于造大文件测试，不实际占盘。

### 6.4 中文字体

`docx_gen.py` 已显式设 `w:eastAsia`（宋体正文/黑体标题）。Linux 容器里仍需装 `fonts-wqy-zenhei`，否则 matplotlib 图表中文出方块、docx 在无中文字体机器上回退。matplotlib 已强制 `Agg` 后端（无显示器安全）。

### 6.5 行为已变更的地方（老测试/老文档可能还按旧行为写）

- CSV 传给 `detect_corrupt_workbook` 现在返回 `ok=true`（旧行为：误报 corrupt）——这是 H2 修复。
- `.xls` 现在返回 `issue="unsupported"`（旧："corrupt"）。
- `detect_encoding` 对 >32MiB 文件改为采样前 1MiB + message 标注「仅采样」（旧：直接拒）。
- 新 issue 码：`too_large`（>200MiB，`POC_EXCEL_MAX_BYTES` 可调）、`unsafe_archive`（ZIP 条目 >10000）。

---

## 7. 验收命令速查

```bash
source .venv/bin/activate
pytest poc/tests tests/ -q                          # 必须全绿（当前 101）
pytest poc/tests --cov=poc/excel_guard_mcp --cov=poc/report_mcp --cov-report=term-missing
python -m poc.excel_guard_mcp < /dev/null          # MCP stdio 起得来且 EOF 即退
python -m poc.report_mcp < /dev/null
git -C QwenPaw describe --tags --exact-match       # v2.0.0
```

24 条业务验收标准见 [`poc-completion-gap-qa.md`](poc-completion-gap-qa.md) §Q5；挂载操作以 [`../poc/README.md`](../poc/README.md) 为准。

---

## 8. 完成一个任务后的收尾要求

1. 跑全量测试 + 覆盖率，贴结果在提交信息里。
2. 更新 `docs/HANDOFF.md` §4/§5 对照表 和本文 §1 的测试计数。
3. 新 MCP/Skill：在 `poc/README.md`、`poc/skills/README.md`、`poc/tests/test_skill_doc.py` 的 SKILLS 列表三处登记。
4. Commit 格式：`feat:/fix:/docs:/test:/refactor:` 前缀，一个任务一个 commit。
5. 发现本文与代码事实冲突时，**以代码为准并修订本文**。

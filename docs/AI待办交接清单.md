# 顺德 POC — 待办交接清单（发接手 AI / 接手人）

> 发送时请把本文件与整个代码仓库一起给出。本文自包含：只读这一份就能开工。
> 日期：2026-03-22 ｜ 基线 commit：`6110e7d` ｜ **当前 225 个测试全绿（101 基线 + 124 新增；详见 §三 任务 A～F 的 commit 列表）**

---

## 一、先跑通基线（5 分钟）

```bash
cd <REPO_ROOT>
source .venv/bin/activate          # 必须用 venv；系统 python3 没装依赖
uv pip install -r poc/requirements.txt
git -C QwenPaw describe --tags --exact-match   # 期望 v2.0.0
pytest poc/tests tests/ -q          # 期望 225 passed（基线 101 + 任务 A/B/C/D 新增 124）
```

若 `QwenPaw/` 目录缺失（它被 gitignore）：

```bash
gh repo clone agentscope-ai/QwenPaw -- --branch v2.0.0
```

**铁律：任何任务完成后这条命令必须仍然全绿，且测试数量只许增加。禁止改测试去适配错误实现。**

---

## 二、项目是什么

给银行演示用的 AI Agent POC，宿主是 QwenPaw v2.0.0，扩展全部放在 `poc/` 目录**旁路接入，不改内核**。六大考察场景：

| 场景 | 当前状态 |
|------|---------|
| ① Excel 文件问答（MCP+Skill） | ✅ 代码完成 + 测试深化（41 单元 + 32 集成），**未挂 Console 实测** |
| ② 多模态知识库（ES/MySQL/GALASYBASE） | ❌ 未开始，**等行方环境**（最大块，12～18 人·日） |
| ③ 运营助手（MCP+Skill+HOOK 埋点） | ✅ 已完成（commit 见 git log）：ops-data MCP（3 工具）+ ops-assistant Skill + 6 HookBase 覆盖 4 类埋点 |
| ④ 报告可视化（docx+交叉表+五类图） | ✅ 已完成（commit `e033887`）：7 个 MCP 工具 + Skill + 35 测试 + CSV 分块 + 一键 demo + stdio 彩排 |
| ⑤ 后端部署（镜像<500MB / `/health`） | ✅ 已完成（commit 见 git log）：Dockerfile.poc + `GET /api/poc/health` 插件（红线 2：不动内核） |
| ⑥ HARNESS（压缩/记忆/沙箱方案阐述） | ✅ 已完成（commit `0fc7838`）：`docs/harness/` 三份讲义 + 索引 |

现有三个 MCP：`excel-guard`（损坏/编码/分块检测，3 工具）、`report-visualizer`（柱/折/饼/散点/热力图 + 交叉表 + docx 组装，7 工具）、`ops-data`（调用量/Token/工具成败/耗时数据问答，3 工具）。两个 QwenPaw 插件：`poc-health`、`poc-ops-telemetry`。

---

## 三、待办清单

### 🔴 第一优先：不依赖外部环境，马上能做

#### ☑ 任务 A：报告可视化（场景④）收尾到能演示 — ✅ commit `e033887`
- [x] 补错误路径测试：`report_mcp/charts.py` 覆盖率 60%→≥85%（空数据/列缺失/非法类型/路径越界/输出目录不可写）；`crosstab.py` 66%→≥90%
- [x] 新增 `poc/tests/test_report_mcp_server.py`，断言 7 个工具全部注册且能调用（测试写法见下方第五节）
- [x] **CSV 分块缺口**：`chunk_large_workbook` 目前只支持 xlsx，但 Skill 文档承诺了大 CSV。加 `.csv/.txt` 分支，二进制流式数 `\n`（常量内存），返回结构与 xlsx 一致
- [x] 一键演示：`poc/fixtures/report_demo/` 放样例数据，`scripts/report_demo.py` 命令行产出含 1 交叉表 + 5 图的 docx
- [x] 按 `poc/README.md` 把两个 MCP + 两个 Skill 实际挂到 QwenPaw Console（替换 `<REPO_ROOT>` 占位符），用 fixtures 走一遍，把实测过程和问题回写 README
- **DoD**：测试全绿、覆盖率达标、脚本能一键产出 docx、README 有实测记录

#### ☑ 任务 B：安全技术债 — ✅ commit `685e79a`
- [x] **TOCTOU**（审计 H1）：改用 `os.open(path, os.O_RDONLY | os.O_NOFOLLOW)` 单次打开拿 fd，文件对象传给 `zipfile.ZipFile(fh)` / `load_workbook(fh)`；删掉 `guards.py` 中 `resolve()` 之后不可达的 symlink 复查死代码
- [x] **沙箱 fail-open**（M1）：`POC_WORKSPACE=/` 或目录不存在时当前全放行——校验 root 合法、拒绝 `/`，有效 root 向 **stderr** 打日志（stdout 是 MCP 协议通道，严禁污染）
- [x] 每个修复配攻击向量回归测试（symlink 检查后换走仍读到原 inode、`POC_WORKSPACE=/` 被拒）
- [x] 核对 `except` 分支，确认 `MemoryError` 不被宽 `except Exception` 吞掉
- **DoD**：新测试通过、基线全绿
- **审计详情**：`docs/superpowers/phase1-security-review.md`（已修复 H2/H3/H4/M7，本文只列未修项）

#### ☑ 任务 E：Excel 12 题答卷（纯文档，可与 A/B 并行） — ✅ commit `44d0fa0`
- [x] 从仓库根目录的 POC 选型方案 `.docx` 提取 12 道 Excel 测题（该文件未入 git，向发送方索取）
- [x] 每题写标准答卷：输入文件、MCP 调用顺序、期望答案要点、异常题护栏文案
- [x] 产出 Agent 装配剧本（Console 里如何配出能答题的智能体），存 `docs/`

### 🟡 第二优先：按评委权重排期

#### ☑ 任务 C：运营助手 + HOOK 埋点（场景③） — ✅ commit `6c48103`
- [x] 先读真实扩展点（勿凭想象）：`QwenPaw/plugins/middleware-demo/` 和 `grep -rn "hook\|middleware" QwenPaw/src/qwenpaw/`
- [x] 四类埋点（24 条验收要求）：调用量/Token 用量、工具成败、用户/会话标识、耗时；旁路 JSONL 落盘 `POC_WORKSPACE/telemetry/`，不改内核
- [x] 新建 `poc/ops_mcp/`（运营数据问答）+ `poc/skills/ops-assistant/SKILL.md`（必须含 触发词/参数/返回值/边界 四段）
- [x] 在 `poc/tests/test_skill_doc.py` 的 SKILLS 列表、两个 README 三处登记
- **注意**：埋点只是这个场景的 10～15%，主体是数据问答 + 业务理解，别做偏

#### ☑ 任务 D：部署（场景⑤） — ✅ commit `f05fd65`
- [x] 调研插件能否注入 FastAPI 路由（读 `QwenPaw/plugins/bundle/*/plugin.py`）；可行走 `poc/plugins/health/`，不可行走 entrypoint 旁路，**不要 sed 改内核**
- [x] `GET /health` → `{"status":"ok"}` 200；v2.0.0 现状只有 `/api/version`
- [x] `poc/deploy/Dockerfile.poc`：multi-stage + `python:slim`，评估去掉 XFCE4/Chromium（先确认演示不用 Coding Mode 浏览器），装 `fonts-wqy-zenhei`
- [x] `docker build` 实测镜像 **<500MB** 并记录；预研见 `docs/superpowers/p4-deployment-research.md`

#### ☑ 任务 F：HARNESS 三方案讲义（场景⑥） — ✅ commit `0fc7838`
- [x] 上下文压缩 / 长期记忆 / 沙箱 三个方案各一份可讲清的讲义 + QwenPaw 内调参演示

### ⚪ 被外部阻塞（先催，不要空等）

- [ ] **任务 G：知识库（场景②，12～18 人·日）**——等行方提供：ES / MySQL / GALASYBASE 端点与接口文档、MinerU / Embedding / Reranker 服务
- [ ] 向行方确认模型口径：要求 **Qwen3.6-35B/27B**；现有探针曾用 `qwen3.5-35b-a3b`，不合规
- [ ] 确认演示环境是否需要浏览器/Coding Mode（决定任务 D 能否删 Chromium）
- [ ] 密钥轮换：若 Bearer 曾出现在聊天记录中，去云控制台轮换

---

## 四、红线（违反直接打回）

1. 禁止提交任何 Bearer / API Key / `.env` / `providers.json` / 本机绝对路径（配置只用 `<REPO_ROOT>` 占位符）
2. 禁止修改 `QwenPaw/` 内核代码；所有扩展在 `poc/`
3. 任何文件读写必须过沙箱（`POC_WORKSPACE`），参考 `guards.py` / `report_mcp/charts.py` 的 `_resolve_allowed_path`
4. stdout 只能输出 MCP JSON-RPC；日志一律 stderr
5. 返回结构的 key 名不许破坏兼容（`ok/issue/message`、`total_rows` 等下游有测试依赖）
6. SKILL.md 必须有 frontmatter + 触发词/参数/返回值/边界四段（有测试强制）
7. 提交前 `pytest poc/tests tests/ -q` 全绿，并更新本文件和 `docs/HANDOFF.md` 的测试计数

---

## 五、给接手 AI 的关键经验（本轮实测）

**FastMCP 怎么测**（不启动 stdio）：
```python
import asyncio, json
from poc.excel_guard_mcp.server import mcp

def _call_tool(name, arguments):
    result = asyncio.run(mcp.call_tool(name, arguments))
    if isinstance(result, dict):
        return result
    return json.loads(result[0].text)
# 注册信息：asyncio.run(mcp.list_tools()) → 每个有 .name/.description/.inputSchema
```
完整范例：`poc/tests/test_mcp_server.py`（32 个测试）。

**chardet 不可靠（实测 7.6.0）**：短 latin-1 样本置信度 0.08、GBK 中文 0.16；只有 **UTF-16 稳定 1.0**。写"高置信度非 UTF-8"测试用 UTF-16；演示用 `poc/fixtures/encoding_gbk.csv`。

**环境**：venv 是 Python 3.13.5；装包用 `uv pip install`（Homebrew Python 有 PEP 668 保护）；macOS 没有 `timeout` 命令。

**已变更行为（老文档若冲突以此为准）**：CSV 进 `detect_corrupt_workbook` 现在返回 ok（不再误报损坏）；`.xls` 返回 `issue="unsupported"`；>32MiB 文本改为采样前 1MiB 而非拒绝；新增 issue 码 `too_large` / `unsafe_archive`（阈值经 `POC_EXCEL_MAX_BYTES` 等环境变量可调）。

**中文字体**：docx 已显式指定宋体/黑体；Linux 容器必须装 `fonts-wqy-zenhei`，否则图表中文是方块。matplotlib 已锁 `Agg` 后端。

---

## 六、验收速查

```bash
source .venv/bin/activate
pytest poc/tests tests/ -q           # 全绿（基线 101 + 任务 A/B/C/D 新增 124 = 225 passed）
pytest poc/tests --cov=poc/excel_guard_mcp --cov=poc/report_mcp --cov-report=term-missing
python -m poc.excel_guard_mcp </dev/null   # exit 0
python -m poc.report_mcp       </dev/null   # exit 0
python -m poc.ops_mcp          </dev/null   # exit 0
```

业务验收 24 条：`docs/poc-completion-gap-qa.md` §Q5。挂载操作：`poc/README.md`。

| 任务 | 人·日 | 可否并行 | 阻塞条件 |
|------|-------|---------|---------|
| A 报告收尾 | 2～3 | ✅ | 无 |
| B 安全债 | 1～2 | ✅ | 无 |
| E 12 题答卷 | 2～3 | ✅（需 docx） | 索取需求 docx |
| C 运营助手 | 5～7 | ✅ | 无 |
| D 部署 | 3～5 | ✅ | 最好先确认浏览器需求 |
| F HARNESS 讲义 | 2～3 | ✅ | 无 |
| G 知识库 | 12～18 | — | **等行方环境** |

**建议起手：A + B 并行**（最快出演示成果、且趁代码熟悉还安全债），E 穿插做文档。

---

## 七、完成后的收尾（每个任务都要做）

- [x] 全量测试 + 覆盖率贴进 commit message
- [x] 更新 `docs/HANDOFF.md` §4/§5 和本文件第一节测试计数
- [x] 新 MCP/Skill 登记三处：`poc/README.md`、`poc/skills/README.md`、`test_skill_doc.py`
- [x] commit 前缀 `feat:/fix:/docs:/test:/refactor:`，一任务一 commit
- [ ] 发现文档与代码冲突时，以代码为准并修文档（持续执行项，非一次性）

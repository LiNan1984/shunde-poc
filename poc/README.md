# 顺德农商行 POC（Phase 1）

本目录为 QwenPaw **v2.0.0** 旁路扩展：**不 fork 核心**。Phase 1 提供 Excel 异常 MCP（`excel-guard`）与表格问答 Skill（`excel-qa-bank`）。场景②多模态知识库见下方 Phase 5（`kb-qa` MCP + `kb-qa-bank` Skill）。

详细实施计划：[`docs/superpowers/plans/2026-03-22-poc-phase1-excel-plan.md`](../docs/superpowers/plans/2026-03-22-poc-phase1-excel-plan.md)

## 挂载 Skill（excel-qa-bank）

Skill 目录：`poc/skills/excel-qa-bank/`（含 `SKILL.md`）。

### 方式 A：外部 `skill_paths`（推荐）

编辑 `$QWENPAW_WORKING_DIR/config.json`（默认 `~/.qwenpaw/config.json`），增加：

```json
{
  "skill_paths": ["<REPO_ROOT>/poc/skills"]
}
```

将 `<REPO_ROOT>` 替换为本仓库绝对路径（例如本机 clone 根目录）。

重启 / 刷新后，在控制台 **技能池** 中应能看到 `excel-qa-bank`，再广播 / 下发到目标智能体工作区。

### 方式 B：复制到 skill_pool

```bash
cp -R <REPO_ROOT>/poc/skills/excel-qa-bank \
  "$QWENPAW_WORKING_DIR/skill_pool/excel-qa-bank"
```

然后在 **工作区 → 技能** 从技能池下发到智能体。也可在 Console 用 ZIP/目录导入。

更多说明见 [`poc/skills/README.md`](skills/README.md)。

## 导入 MCP（excel-guard）

配置样例：[`poc/config/mcp-excel-guard.json`](config/mcp-excel-guard.json)（`mcpServers` 格式）。

1. 打开 QwenPaw Console → **智能体 → MCP**
2. 点击 **+ 创建**
3. 粘贴 `mcp-excel-guard.json` 全文（或其中 `mcpServers` 段）
4. 将 JSON 中所有 `<REPO_ROOT>` 替换为本仓库绝对路径后再导入
5. 建议 `env.POC_WORKSPACE=<REPO_ROOT>`，MCP 只允许读取该目录内文件（防路径穿越）
6. 使用 `.venv`：`uv venv && source .venv/bin/activate && uv pip install -r poc/requirements.txt`

工具：`detect_corrupt_workbook`、`detect_encoding`、`chunk_large_workbook`、`describe_workbook`、`sheet_to_markdown`，以及 officecli 守卫桥接四件套（需本机安装 [officecli](https://github.com/iOfficeAI/OfficeCLI)，未安装时调用会返回 `officecli_missing`）：`edit_workbook`（守卫批量写回：add/set/remove/move/swap 白名单，写前损坏/超限预检，写后 OpenXML validate + 公式审计，officecli batch 原子回滚）、`inspect_workbook`（officecli get 结构化读取样式/格式细节）、`validate_workbook`（OpenXML schema 校验）、`render_workbook`（渲染 PNG 目检，输出强制在工作区内）。

**禁止**在配置或仓库中写入 API Key；模型密钥仅用环境变量 / `QWENPAW_SECRET_DIR`。

## 测试

```bash
source /Users/linan/Desktop/aicode/shunde/.venv/bin/activate
cd /Users/linan/Desktop/aicode/shunde
pytest poc/tests -v
```

## Excel 问答黄金回归集（poc/evals）

14 条确定性问答对——11 条读类（干净明细、多级合并表头、未缓存公式列、GBK 编码 CSV、多文件路由定位）+ 3 条写回类（追加利润列 / 按地区汇总写新表 / GBK CSV 转 xlsx，评分器直接打开 agent 输出文件校验内容）。期望值与工作簿出自同一份内存数据，并由测试独立用 pandas/openpyxl 从落盘文件重算验证（`poc/tests/test_excel_qa_eval.py`）。

```bash
# 生成 fixtures（poc/fixtures/qa_fixtures/）并打印问题清单
.venv/bin/python scripts/excel_qa_eval.py --build

# agent 回答写入 answers.json（读类 {question_id: value}；写类 {question_id: 输出文件路径}）后评分
.venv/bin/python scripts/excel_qa_eval.py --answers answers.json

# 自检：黄金答案必须 100%
.venv/bin/python scripts/excel_qa_eval.py --self-test
```

改动 excel-qa / excel-guard 任何能力后跑一次评分，准确率变化即可量化，不靠主观判断。

基线：读类按 skill 规定流程（`preflight_workbook` → `describe_workbook` → pandas 精算 → `audit_workbook`）10/10，写回类 3/3（`poc/fixtures/qa_fixtures/baseline_answers.json`，含 `golden_outputs/` 黄金输出），合计 **14/14 = 100%**。多级表头工作簿的表头投票正确落在第 3 行子表头，合并区域（A1:E1 / B2:C2 / A2:A3 / D2:E2）全部识别。

---

## Phase 2 — 报告可视化助手（P2）

### 挂载 Skill（report-visualizer）

Skill 目录：`poc/skills/report-visualizer/`（含 `SKILL.md`）。

挂载方式与 `excel-qa-bank` 完全一致：`skill_paths` 指向 `poc/skills/`，或在 Console 工作区从技能池下发。

### 导入 MCP（report-visualizer）

配置样例：[`poc/config/mcp-report-visualizer.json`](config/mcp-report-visualizer.json)。

1. 打开 QwenPaw Console → **智能体 → MCP**
2. 点击 **+ 创建**
3. 粘贴 `mcp-report-visualizer.json` 全文（或其中 `mcpServers` 段）
4. 将 JSON 中所有 `<REPO_ROOT>` 替换为本仓库绝对路径
5. 建议 `env.POC_WORKSPACE=<REPO_ROOT>`，MCP 只允许写入该目录内文件
6. 安装新依赖：`source .venv/bin/activate && pip install python-docx matplotlib`

工具：`pivot_table_tool`、`render_bar_tool`、`render_line_tool`、`render_pie_tool`、`render_scatter_tool`、`render_heatmap_tool`、`render_docx_report_tool`。

---

## Phase 3 — 运营助手（P3）

### 挂载 Skill（ops-assistant）

Skill 目录：`poc/skills/ops-assistant/`（含 `SKILL.md`）。挂载方式同 Phase 1/2。

### 导入 MCP（ops-data）

配置样例：[`poc/config/mcp-ops-data.json`](config/mcp-ops-data.json)。工具：`list_telemetry_files_tool`、`summarize_calls_tool`、`recent_events_tool`。

### 注册 HOOK 埋点（4 类）

通过两个 QwenPaw 插件一次性安装：

```bash
qwenpaw plugin install <REPO_ROOT>/poc/plugins/ops-telemetry
qwenpaw plugin install <REPO_ROOT>/poc/plugins/health
```

- `poc-ops-telemetry` 把 6 个 HookBase 子类注册进每个 workspace，覆盖 8 个 Phase 中的 5 个（PRE_DISPATCH/POST_DISPATCH/PRE_AGENT_BUILD/POST_RESPONSE/PRE_EXECUTE/ON_ERROR），分别对应**调用量/耗时/会话/Token/工具成败** 4 类埋点。
- 落盘位置：`POC_WORKSPACE/telemetry/<UTC-日期>/ops.jsonl`，每行一条 JSON。

---

## Phase 4 — 后端部署（P4）

### 镜像

`poc/deploy/Dockerfile.poc` multi-stage（`python:3.13-slim`），仅安装 `tini / ca-certificates / fonts-wqy-zenhei`；不含 XFCE/Chromium（演示环境无浏览器）。本机实测镜像 < 500MB（CI 实测见 commit 信息）。

```bash
docker build -f poc/deploy/Dockerfile.poc -t shunde-poc:dev .
docker run --rm -p 8080:8080 shunde-poc:dev
# curl http://localhost:8080/api/poc/health -> {"status":"ok"}
```

### `/health` 路由

插件 `poc/plugins/health/` 通过 QwenPaw 官方 `api.register_http_router` 挂载 FastAPI `APIRouter`（红线 2：不动内核）：

| 方法 | 路径 | 返回 |
|------|------|------|
| GET  | `/api/poc/health`         | `{"status": "ok"}` |
| GET  | `/api/poc/health/version` | `{"status": "ok", "poc_version": "..."}` |

### 实测记录（2026-09）

- 一键 demo（无需启动 Console）：`source .venv/bin/activate && python scripts/report_demo.py`，产出 `poc/fixtures/report_demo/out/report.docx`（13 段落 + 1 交叉表 + 5 嵌入图）。验证脚本内置对所有工具 `ok` 的断言，任一失败立即非零退出。
- stdio 彩排：`python scripts/mcp_stdio_smoke.py`——以子进程方式启动四路 MCP，对每路发送 JSON-RPC `initialize` 并校验响应，同时复用单元测试同款的 `mcp.list_tools()` 在进程内枚举，确认 5 + 7 + 3 + 6 工具齐全。
- 单元测试自动化可达：193 passed, 1 skipped（基线 101 + 新增 92），`charts.py` 98%、`crosstab.py` 100%、`docx_gen.py` 89% 覆盖；详见 `pytest poc/tests --cov=poc/report_mcp --cov=poc/excel_guard_mcp --cov-report=term-missing`。
- 仅人工可达（无法自动化）：Console GUI 的"创建 MCP + 下发 Skill + 智能体绑定"步骤——按上文 §导入 MCP / §挂载 Skill 在浏览器里点即可。

---

## Phase 5 — 多模态文件问答助手（知识库，用例 2-1 / 2-2）

### 挂载 Skill（kb-qa-bank）

Skill 目录：`poc/skills/kb-qa-bank/`（含 `SKILL.md`，含触发词 / 参数 / 返回值 / 边界）。挂载方式同 Phase 1。

### 导入 MCP（kb-qa）

配置样例：[`poc/config/mcp-kb-qa.json`](config/mcp-kb-qa.json)。

1. 打开 QwenPaw Console → **智能体 → MCP**
2. 粘贴 JSON 并将所有 `<REPO_ROOT>` 换成绝对路径
3. `env.POC_WORKSPACE=<REPO_ROOT>`；接通 `ELASTICSEARCH_URL` / `MYSQL_URL` / `GALASYBASE_URL` / `MINERU_ENDPOINT`（URL 写在 `~/.qwenpaw.secret/middleware.env`，mode 600）。Harness 上独立容器：ES `127.0.0.1:19200`、MySQL `127.0.0.1:13306`（**不占用**已有 9200/3306）。创邻 GALASYBASE 无官方镜像时图库走本地 `graph.json`，答案里不得写成已写入 Galaxybase。未接通时同一套函数走 sqlite + 本地向量 + 本地图。
4. **向量模型（推荐）**：把火山方舟 Coding Plan 的 Key 写进 `~/.qwenpaw.secret/embedding.env` 或 gitignored `.env`（**不要提交仓库**）：
   `POC_EMBEDDING_URL=https://ark.cn-beijing.volces.com/api/coding/v3`
   `POC_EMBEDDING_MODEL=doubao-embedding-vision`
   `POC_EMBEDDING_API_KEY=...`
   `POC_CHAT_MODEL=glm-5.3-flash`（可选：检索后用对话模型改写答案；向量质量只取决于 embedding，不取决于 glm）。
   未配置 embedding 时仍用确定性哈希向量，单测不打外网。
5. **MinerU（官方仓库已克隆到 `MinerU/`，gitignore）**：
   ```bash
   bash scripts/start_mineru_api.sh          # http://127.0.0.1:18000
   export MINERU_ENDPOINT=http://127.0.0.1:18000
   export MINERU_BACKEND=pipeline            # Mac / 无 NVIDIA；有 GPU 可改 hybrid-engine
   ```
   或不启服务、直接 CLI：`export MINERU_LOCAL=1`。首次解析会下载模型。未配置时仍用本地 pypdf/OCR 解析器。

工具：`parse_document`、`ingest_document`、`ingest_spreadsheet`、`search_knowledge`、`answer_knowledge`、`analyze_page`。Excel 只入库表头/样例行用于定位文件。

```bash
source .venv/bin/activate
python -m poc.kb_mcp </dev/null          # stdio 遇 EOF 退出
python scripts/mcp_stdio_smoke.py        # 含 kb-qa 连续两次 initialize + 夹具检索
pytest poc/tests/test_kb_parse.py poc/tests/test_kb_store_retrieve.py poc/tests/test_kb_mcp_server.py -q
```

### 多模态能力升级（2026-09）

并行迭代中的四项升级（工具名在此只作引用，实现在各自分支上落地）：

- **`analyze_page(doc_id, path, page, query)` 视觉问答工具**：用视觉模型直接看某页的页面 PNG 作答，是「答案只在图里」类问题（如柱状图数值）的唯一通路。视觉模型由 `POC_VISION_MODEL` 指定，chat/密钥走 `POC_CHAT_URL` / `POC_ALIYUN_API_KEY`。
- **重排序**：RRF 融合后取 **top16** 送 `qwen3.7-text-rerank` 交叉编码器重排，再截回 top-k。配置 `POC_RERANKER_URL` / `POC_RERANKER_MODEL`；未配置时保持原 RRF 顺序。
- **图像向量**：`qwen3-vl-embedding`（**dim 2560，独立向量空间**），仅对 `kind=image` 块、且配置了 `POC_IMAGE_EMBEDDING_URL` 时启用；没有图（或未配置）时 image 块仍沿用原文本向量，互不影响。
- **chat 模型切换**：答案改写 / 编排用的对话模型由 `POC_CHAT_URL` + `POC_CHAT_MODEL` 决定（如切回 `glm-5.3-flash`），向量质量只取决于 embedding，与 chat 模型无关。

以上真实 Key 只放 `~/.qwenpaw.secret/middleware.env`（mode 600）或 gitignored `.env`，见 `.env.example` 的「Multimodal KB upgrades」段（全部留空，不提交）。

**Golden QA 评测**：`poc/fixtures/kb_golden_qa.json`（9 条，覆盖 3 个夹具 PDF：信贷政策 / 产品定价 / 网点余额图，按 `text` / `table` / `image` 分模态）。图表夹具 `网点余额图.pdf` 由 `poc/fixtures/generate_fixtures.py` 确定性生成——**柱状图数值只存在于柱子高度里**，正文不含数字，因此 image 组离线必然失配，这正是该评测要量化的差距。

```bash
python scripts/kb_eval.py                 # 离线：hash 向量 + 本地库，强制 pop 全部端点变量
python scripts/kb_eval.py --live          # 读 ~/.qwenpaw.secret，image 题调 analyze_page 判 vision 命中
python scripts/kb_eval.py --k 8 --min-hit-rate 0.8 --keep-workspace
```

判定：top-k 块的 `text` / `image_description` / `table_csv` 任一包含全部 `expected_keywords`（或命中 `expected_page`）计 hit；报告按模态分组输出 `hit@k` 与纯关键词命中（`kw命中`，image 组的差距指标），JSON 写入 `POC_WORKSPACE/kb_eval_report.json`。**text+table 组 hit rate < `--min-hit-rate`（默认 0.8）退出码 1**，image 组只报告不拦截。单测：`pytest poc/tests/test_kb_eval.py -q`（全离线）。

### 任务 A 完成度核对

| DoD 子项 | 状态 | 证据 |
|---------|------|------|
| charts 覆盖率 ≥85% | ✅ 98% | `pytest poc/tests --cov=poc/report_mcp` |
| crosstab 覆盖率 ≥90% | ✅ 100% | 同上 |
| 7 工具全部注册且可调用 | ✅ | `poc/tests/test_report_mcp_server.py` + `scripts/mcp_stdio_smoke.py` |
| CSV 分块 | ✅ | `poc/tests/test_chunk_csv.py` 覆盖 xlsx + csv + 边界 |
| 一键 demo 脚本 | ✅ | `scripts/report_demo.py` 已跑通 |
| Console 实挂彩排 | 🟡 自动化部分完成，GUI 仅人工 | 见上"实测记录" |

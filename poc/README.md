# 顺德农商行 POC（Phase 1）

本目录为 QwenPaw **v2.0.0** 旁路扩展：**不 fork 核心**。Phase 1 提供 Excel 异常 MCP（`excel-guard`）与表格问答 Skill（`excel-qa-bank`）。

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

工具：`detect_corrupt_workbook`、`detect_encoding`、`chunk_large_workbook`。

**禁止**在配置或仓库中写入 API Key；模型密钥仅用环境变量 / `QWENPAW_SECRET_DIR`。

## 测试

```bash
source /Users/linan/Desktop/aicode/shunde/.venv/bin/activate
cd /Users/linan/Desktop/aicode/shunde
pytest poc/tests -v
```

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

### 实测记录（2026-09）

- 一键 demo（无需启动 Console）：`source .venv/bin/activate && python scripts/report_demo.py`，产出 `poc/fixtures/report_demo/out/report.docx`（13 段落 + 1 交叉表 + 5 嵌入图）。验证脚本内置对所有工具 `ok` 的断言，任一失败立即非零退出。
- stdio 彩排：`python scripts/mcp_stdio_smoke.py`——以子进程方式 `python -m poc.excel_guard_mcp` 与 `python -m poc.report_mcp` 启动，对每路发送 JSON-RPC `initialize` 并校验响应，同时复用单元测试同款的 `mcp.list_tools()` 在进程内枚举，确认 3 + 7 工具齐全。
- 单元测试自动化可达：193 passed, 1 skipped（基线 101 + 新增 92），`charts.py` 98%、`crosstab.py` 100%、`docx_gen.py` 89% 覆盖；详见 `pytest poc/tests --cov=poc/report_mcp --cov=poc/excel_guard_mcp --cov-report=term-missing`。
- 仅人工可达（无法自动化）：Console GUI 的"创建 MCP + 下发 Skill + 智能体绑定"步骤——按上文 §导入 MCP / §挂载 Skill 在浏览器里点即可。

### 任务 A 完成度核对

| DoD 子项 | 状态 | 证据 |
|---------|------|------|
| charts 覆盖率 ≥85% | ✅ 98% | `pytest poc/tests --cov=poc/report_mcp` |
| crosstab 覆盖率 ≥90% | ✅ 100% | 同上 |
| 7 工具全部注册且可调用 | ✅ | `poc/tests/test_report_mcp_server.py` + `scripts/mcp_stdio_smoke.py` |
| CSV 分块 | ✅ | `poc/tests/test_chunk_csv.py` 覆盖 xlsx + csv + 边界 |
| 一键 demo 脚本 | ✅ | `scripts/report_demo.py` 已跑通 |
| Console 实挂彩排 | 🟡 自动化部分完成，GUI 仅人工 | 见上"实测记录" |

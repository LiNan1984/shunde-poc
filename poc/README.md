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

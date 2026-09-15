# officecli 助手池接入说明

> 更新日期：2026-09-15　|　二进制版本：officecli 1.0.148（`/Users/linan/.local/bin/officecli`）

本项目 Excel 助手对 officecli 有**两条接入通道**，共用同一二进制：

| 通道 | 形态 | 守卫 | 适用 |
|------|------|------|------|
| 守卫 MCP 桥接 | `excel-guard` MCP 的 `edit_workbook` / `inspect_workbook` / `validate_workbook` / `render_workbook` | ✅ 工作区沙箱 + 损坏/超限预检 + 动词白名单 + 原子回滚 + 写后审计 | 业务数据写回（默认） |
| 官方 skill 直调 | officecli 官方 skill（Claude Code 全量安装） | ❌ 仅流程约定 | 排版复杂 / MCP 工具覆盖不到的能力 |

## 已安装状态（Claude Code）

- 基础层：`officecli-docx` / `officecli-pptx` / `officecli-xlsx`
- 场景层：`officecli-financial-model`、`officecli-data-dashboard`、`officecli-pitch-deck`、`officecli-academic-paper`、`officecli-word-form`、`morph-ppt`、`morph-ppt-3d`
- 落点：`~/.claude/skills/officecli*`

## 其他助手安装方法（池内自助）

```bash
officecli skills install                  # 基础 SKILL.md → 所有检测到的助手
officecli skills install <skill> <agent>  # 指定 skill + 指定助手（如 excel claude）
officecli skills list                     # 查看可用/已装状态
officecli mcp <target>                    # 可选：官方 MCP 直连（无守卫，透传所有命令）
```

Agents：`claude, copilot, codex, cursor, windsurf, minimax, opencode, openclaw, nanobot, zeroclaw, hermes, all`

当前池内已装：Copilot、Codex、Cursor、OpenCode、Hermes、OpenClaw（基础 SKILL.md）。

## 守卫桥接的环境变量

- `OFFICECLI_BIN`：指定二进制路径（默认走 PATH）
- `POC_OFFICECLI_TIMEOUT`：单次调用超时秒数（默认 120，下限 5）
- batch 动词白名单：`add / set / remove / move / swap`（`raw-set`、`import`、`create` 永不透传）

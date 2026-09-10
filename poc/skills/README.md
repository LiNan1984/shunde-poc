# POC Skills

| Skill | 路径 | 说明 |
|-------|------|------|
| `excel-qa-bank` | [`excel-qa-bank/SKILL.md`](excel-qa-bank/SKILL.md) | Excel/CSV 问答；先调 `excel-guard` MCP 再读查析写 |

## 接入 QwenPaw

1. **`skill_paths`**：在 `$QWENPAW_WORKING_DIR/config.json` 登记本目录绝对路径，技能原地进入技能池视图。
2. **复制到主池**：将 `excel-qa-bank/` 拷入 `$QWENPAW_WORKING_DIR/skill_pool/`，再下发到工作区。

验收字段（名称、描述、触发词、参数、返回值、边界）见各 `SKILL.md`。Phase 计划：`docs/superpowers/plans/2026-03-22-poc-phase1-excel-plan.md`。

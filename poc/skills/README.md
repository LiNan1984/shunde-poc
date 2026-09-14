# POC Skills

| Skill | 路径 | 说明 |
|-------|------|------|
| `excel-qa-bank` | [`excel-qa-bank/SKILL.md`](excel-qa-bank/SKILL.md) | Excel/CSV 问答；先调 `excel-guard` MCP 再读查析写 |
| `report-visualizer` | [`report-visualizer/SKILL.md`](report-visualizer/SKILL.md) | 报告可视化：交叉表 + 五类图 + docx 拼装；调 `report-visualizer` MCP |
| `ops-assistant` | [`ops-assistant/SKILL.md`](ops-assistant/SKILL.md) | 运营问答：调用量/Token/工具成败/耗时四类埋点数据；调 `ops-data` MCP |
| `kb-qa-bank` | [`kb-qa-bank/SKILL.md`](kb-qa-bank/SKILL.md) | 多模态知识库：PDF 解析/入库/检索；调 `kb-qa` MCP |

## 接入 QwenPaw

1. **`skill_paths`**：在 `$QWENPAW_WORKING_DIR/config.json` 登记本目录绝对路径，技能原地进入技能池视图。
2. **复制到主池**：将各 Skill 目录拷入 `$QWENPAW_WORKING_DIR/skill_pool/`，再下发到工作区。

验收字段（名称、描述、触发词、参数、返回值、边界）见各 `SKILL.md`。阶段计划：
- Phase 1：`docs/superpowers/plans/2026-03-22-poc-phase1-excel-plan.md`
- Phase 2：`docs/superpowers/plans/2026-03-22-poc-phase2-report-visualizer-plan.md`

# POC Phase 2 — 报告可视化助手实施计划

**日期：** 2026-03-22  
**对应 HANDOFF 优先级：** P2  
**预估人·日：** 4～6（本计划按 4 人·日骨架 + 余量估算）  
**基线：** QwenPaw v2.0.0，Phase 1 Excel MCP 已落地

---

## 1. 目标

实现**报告可视化助手** Skill + MCP，满足 POC 验收 Q5.E 第 16-18 条：

| # | 验收项 | 状态 |
|---|-------|------|
| 16 | 纯文字 + 数据 → docx，内容无损失 | ✅ 脚手架完成 |
| 17 | 标题层级 / 段落 / 间距 / 字体 / 页眉页脚 | ✅ 脚手架完成 |
| 18 | 动态多维交叉表 + 五类图（柱/折/饼/散点/热力） | ✅ 脚手架完成 |

---

## 2. 架构

```
poc/
├── report_mcp/                # FastMCP stdio 服务器
│   ├── charts.py              # 五类图渲染（matplotlib Agg）
│   ├── crosstab.py            # 交叉表（pandas pivot_table）
│   ├── docx_gen.py            # docx 组装（python-docx）
│   ├── server.py              # FastMCP 入口，7 个工具
│   ├── __init__.py
│   └── __main__.py
├── skills/
│   └── report-visualizer/
│       └── SKILL.md           # Skill 定义（LLM 编排层）
├── config/
│   └── mcp-report-visualizer.json   # MCP 配置模板
├── tests/
│   └── test_report_mcp.py     # 8 个真实测试
└── requirements.txt           # + python-docx, matplotlib
```

### 扩展策略
- 与 Phase 1 一致：**旁路扩展，不 fork QwenPaw 内核**
- Skill 只做 LLM 编排（解析用户意图 → 调 MCP → 汇总结果）
- MCP 承担所有确定性计算（图表、交叉表、docx 排版）
- 沙箱：`POC_WORKSPACE` 路径约束，与 Phase 1 完全相同的 `_resolve_allowed_path` 契约

---

## 3. MCP 工具清单（7 个）

| 工具 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `pivot_table_tool` | data, rows, cols, value, aggfunc, max_categories | {ok, table, row_count, col_count, message} | 多维交叉表；max_categories 防维度爆炸 |
| `render_bar_tool` | data, x, y, series?, title, output_path | {ok, chart_type, output_path, width_px, height_px} | 柱状图（支持分组） |
| `render_line_tool` | data, x, y, series?, title, output_path | 同上 | 折线图（支持多系列） |
| `render_pie_tool` | data, label, value, title, output_path | 同上 | 饼图 |
| `render_scatter_tool` | data, x, y, color?, title, output_path | 同上 | 散点图（支持分组着色） |
| `render_heatmap_tool` | data+row+col+value 或 matrix+x_labels+y_labels | 同上 | 热力图（两种输入模式） |
| `render_docx_report_tool` | title, sections, output_path, header?, footer? | {ok, output_path, sections_count, charts_inserted} | docx 组装；sections 含 heading/paragraphs/table/charts |

### 技术选型理由
- **matplotlib (Agg)**：PNG 直接嵌入 docx，无需浏览器，避免 P4 镜像体积问题（与 Chromium 解耦）
- **python-docx**：程序化构建，不依赖模板引擎，POC 演示灵活
- **pandas pivot_table**：复用已安装依赖，交叉表功能开箱即用
- **7 个独立工具 vs 1 个带 chart_type 参数**：工具 schema 更小更清晰，LLM 选错概率低

---

## 4. Skill 编排流程

```
用户："给这份销售数据做一份报告，要有分地区柱状图和交叉表"
│
├─ 解析：识别数据来源、报告结构、图表类型
├─ 调 pivot_table_tool → 得到交叉表数据
├─ 调 render_bar_tool → 得到柱状图 PNG 路径
├─ （可选更多图表...）
├─ 调 render_docx_report_tool → 组装 docx
└─ 返回：报告路径 + 章节/图表摘要
```

**护栏：**
- 路径越界 → 拒绝
- 列缺失 → 提示缺少的列名
- 维度超限 → 提示减少维度或先做 top-N
- 图表渲染失败 → 跳过该图，继续组装报告

---

## 5. 测试策略

| 层 | 测试数 | 覆盖 |
|----|-------|------|
| crosstab 单元 | 2 | happy path + 维度超限 |
| charts 单元 | 4+ | bar/heatmap 详细 + line/pie/scatter 冒烟 |
| docx 集成 | 1 | 端到端 round-trip：生成 → 打开 → 验证标题/段落/表格/图片 |
| 沙箱安全 | 1 | 路径越界拒绝 |
| MCP server | 1 | 模块可导入 |
| Skill 文档 | 3（参数化） | 存在性 + frontmatter + 验收字段 |

**当前覆盖率（脚手架阶段）：**
- crosstab: 66%
- charts: 60%（主要是错误路径未覆盖）
- docx_gen: 89%
- server: 71%

**建议后续补齐：** charts 各种错误路径（列缺失、空数据、数据类型错误等）

---

## 6. DoD（完成定义）

Phase 2 脚手架 DoD（当前已达）：
- [x] MCP 模块结构完整，可导入
- [x] 五类图 + 交叉表 + docx 三个核心模块有基本实现
- [x] 8 个测试全部通过
- [x] SKILL.md 包含全部 4 个验收字段（触发词/参数/返回值/边界）
- [x] 沙箱与 Phase 1 一致
- [x] MCP 配置模板就位（`<REPO_ROOT>` 占位符）
- [x] 与 poc/README.md / skills/README.md 文档对齐

Phase 2 完全体 DoD（需后续推进）：
- [ ] 挂到 QwenPaw Console 并演示端到端流程
- [ ] 12 道报告类测题预跑答卷
- [ ] 中文字体在 Docker 环境验证不出现方块
- [ ] charts 测试覆盖率 ≥ 85%
- [ ] 报告模板化（银行风格）

---

## 7. 风险与依赖

| 风险 | 影响 | 缓解 |
|------|------|------|
| 中文字体在 Linux 容器缺失 | docx 中文字体回退 | 打包 fonts-wqy-zenhei；在 docx_gen 中 fallback |
| matplotlib 后端配置问题 | 无显示器环境报错 | 代码顶部强制 `matplotlib.use("Agg")` |
| 图表数据量过大导致慢 | 用户体验 | 与交叉表共用 max_categories 思路；默认 DPI 适中 |
| python-docx 样式有限 | 复杂排版需求不满足 | POC 够用；复杂模板可后续接 docxtpl |

---

## 8. 与其他阶段的关系

- **Phase 1**：共享沙箱契约、测试风格、MCP 配置模式
- **Phase 3 运营助手**：可复用 report_mcp 生成运营报告
- **Phase 5 知识库**：知识库检索结果可直接喂给 report_mcp 生成报告
- **Phase 4 部署**：中文字体需加到 POC 专用 Dockerfile 中

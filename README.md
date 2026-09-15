# 顺德农商行 POC — 四助手旁路扩展

基于 [agentscope-ai/QwenPaw](https://github.com/agentscope-ai/QwenPaw) 的**旁路扩展**（不 fork、不改内核）：所有扩展代码都在 `poc/` 目录内，通过 **MCP / Skill / 插件** 三种方式接入 QwenPaw Console，`git diff QwenPaw/` 始终为空。

对应《人工智能场景拓展与迭代开发技术服务项目 — POC 选型方案》六大考察类中的四个助手场景：

| 助手 | MCP Server | Skill | 能力 |
|------|-----------|-------|------|
| ① Excel 文件问答 | `poc/excel_guard_mcp`（`excel_guard`） | `poc/skills/excel-qa-bank` | 损坏/编码/超大分块预检、结构描述、守卫批量写回（officecli 原子回滚）、OpenXML 校验、渲染目检 |
| ② 多模态知识库 | `poc/kb_mcp`（`kb_qa`） | `poc/skills/kb-qa-bank` | PDF 解析入库、表格元数据索引、BM25+文本向量+图像向量混合检索、带页码引用的问答、视觉模型读图 |
| ③ 运营助手 | `poc/ops_mcp`（`ops_data`） | `poc/skills/ops-assistant` | 埋点 JSONL 汇总/查询；配套 `poc/plugins/ops-telemetry` Hook 插件（调用量/Token/工具成败/耗时/身份） |
| ④ 报告可视化 | `poc/report_mcp`（`report_visualizer`） | `poc/skills/report-visualizer` | 交叉表、柱/折/饼/散/热力图渲染、DOCX 报告组装 |

## 仓库结构

```
shunde/
├── QwenPaw/            # 上游框架 git 子模块（固定在已验证版本，不做本地修改）
├── poc/                # 全部扩展代码（见 poc/README.md）
│   ├── *_mcp/          # 四个 FastMCP server（python -m poc.<name> 启动 stdio）
│   ├── skills/         # 四助手 Skill + officecli 系/morph 等技能收录
│   ├── config/         # mcp-*.json Console 导入样例（含 namespace）
│   ├── fixtures/       # 测试夹具与黄金回归集（kb_golden_qa.json）
│   ├── evals/          # 问答评测打分
│   ├── hooks/          # 运营埋点 Hook 实现
│   ├── deploy/         # Dockerfile 与 web 依赖
│   ├── web/            # 演示 Web 端
│   └── tests/          # pytest 全量回归（400+ 用例）
├── docs/               # 交接文档（HANDOFF.md）、演示材料、专题说明
└── scripts/            # 评测与证明文档生成脚本
```

## 快速开始

```bash
# 1. 环境（Python 3.11+，推荐 uv）
uv venv && source .venv/bin/activate
uv pip install -r poc/requirements.txt

# 2. 全量测试（约 1 分钟）
pytest poc/tests -q

# 3. 手动启动某个 MCP server（stdio）
python -m poc.excel_guard_mcp
```

接入 QwenPaw Console（挂载 Skill、导入 MCP、密钥环境变量）见 **[poc/README.md](poc/README.md)**；部署（镜像 / `/health`）见 `poc/deploy/`。

## 设计约定

- **渐进加载（L1/L2/L3）**：上下文按「skill列表摘要 → skill → mcp列表（namespace 前缀）→ 详细 mcp → 文件摘要 → 文件详情」逐级展开，稳定前缀提高缓存命中率。合同由 `poc/progressive_load.py` 命名并有测试守护。
- **安全沙箱**：MCP 通过 `POC_WORKSPACE` 限定可读目录，防路径穿越；写回操作有损坏/超限预检与写后审计。
- **密钥管理**：禁止在配置或仓库写入 API Key，仅用环境变量 / `QWENPAW_SECRET_DIR`。
- **密钥文件优先级**：`middleware.env` → `embedding.env`（先到先得）。

## 关键文档

| 文档 | 内容 |
|------|------|
| [docs/HANDOFF.md](docs/HANDOFF.md) | 项目交接总览（现状、范围、缺口） |
| [poc/README.md](poc/README.md) | 扩展接入操作手册（Skill/MCP 挂载步骤） |
| [docs/officecli助手池接入.md](docs/officecli助手池接入.md) | officecli 双通道接入（守卫 MCP 桥接 + 官方技能池） |
| [docs/HOOK交接文档.md](docs/HOOK交接文档.md) | 运营埋点 Hook 专题 |
| [docs/四助手演示测试案例.md](docs/四助手演示测试案例.md) | 每助手 5 条演示/回归测试案例（含黄金预期值） |
| [docs/演示材料/](docs/演示材料/) | 四助手架构图、演示 PPT 与幻灯片源 |

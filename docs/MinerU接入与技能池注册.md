# MinerU 接入与技能池注册

> 更新日期：2026-09-15　|　全部为 opendatalab 官方实现

## 组件清单（已安装并实测）

| 组件 | 官方仓库 | 本机（Mac） | VPS（72.60.193.189） |
|------|---------|------------|---------------------|
| mineru-open-api CLI（v 精准/flash 解析） | opendatalab/MinerU-Ecosystem | `~/.local/bin/mineru-open-api` | 未装（走 MCP 通道） |
| mineru-open-mcp（解析 MCP） | 同上 `mcp/`（PyPI `mineru-open-mcp`） | `uvx mineru-open-mcp` | venv `/root/mineru-mcp-py`，pm2 `mineru-mcp` → `http://127.0.0.1:8201/mcp` |
| MinerU Document Explorer（qmd，检索/深读/wiki） | opendatalab/MinerU-Document-Explorer（npm `mineru-document-explorer`） | `qmd` 1.0.9 + 本机 daemon :8181 | `/usr/bin/qmd` 1.0.9，pm2 `qmd-mcp` → `http://localhost:8181/mcp`（监听 `[::1]`） |
| Document Explorer Agent Skill | 同上 `skills/` | `qmd skill install --global` → `~/.claude/skills/mineru-document-explorer` | 随技能池下发 |
| MinerU 核心引擎（本地版，1.2G） | opendatalab/MinerU | 仓库内 clone（备用，在线 API 已覆盖需求） | 未装（VPS 无 GPU） |

## 认证

- 密钥环境变量：`MINERU_API_TOKEN` / `MINERU_TOKEN`（解析 API/MCP/CLI）、`MINERU_API_KEY`（qmd 的 MinerU Cloud 深读）。
- 本机：`~/.config/mineru/env`（chmod 600，source 后使用）。
- VPS：`/root/.qwenpaw.secret/mineru.env`（仅 root），由 `/root/bin/start-mineru-mcp.sh`、`/root/bin/start-qmd-mcp.sh` 注入。
- **密钥不落任何文档/代码/Console 描述。**

## Skill Pool 注册（3 个 skill）

位于 `poc/skills/`（rsync → VPS `/root/shunde-poc/poc/skills`），在 QwenPaw pool manifest（`/root/.qwenpaw/skill_pool/skill.json`）以 `external: true` 注册，Console `/settings/skill-pool` 可见：

- **mineru-document-parser**：PDF/DOCX/PPTX/图片/网页 → Markdown/JSON/DOCX/LaTeX；OCR 109 语种；flash vs 精准；批处理
- **mineru-document-explorer**：qmd 15 工具决策树（检索/深度阅读/wiki），references/ 带官方 SKILL.md 全文
- **mineru-mcp**：两个 MCP 服务端点、pm2/wrapper 布局、HTTP 握手、排障手册

## Agent Runtime 绑定

kb-agent 已通过 API（`POST /api/mcp`，X-Agent-Id: kb-agent）绑定两个 streamable_http MCP 客户端：

| client_key | url | 实测 tools |
|-----------|-----|-----------|
| mineru | `http://127.0.0.1:8201/mcp` | parse_documents、get_ocr_languages |
| qmd | `http://localhost:8181/mcp` | 15/15 |

其他智能体绑定：Console → 工作区 → MCP 添加同样 URL，或
`curl -X POST https://shunde-poc.harness-agent.app/api/mcp -H "X-Agent-Id: <agent>" -d '{"client_key":"mineru","client":{...同上...}}'`。

## 实测记录（2026-09-15）

- CLI 精准解析：东吴证券 PDF（38 页）→ 76KB Markdown + 45 图，`-f md,docx,html` 多格式 ✓
- CLI flash 模式（无 key）：demo_table.pdf 表格 → HTML 表 ✓
- MCP stdio + HTTP：握手/tools/list/parse_documents（页码范围 1-1）✓（本机 + VPS）
- qmd 深读：doc-toc/doc-read(pages:0)/doc-grep，PDF 提取来源 `"source": "mineru"`（走 MinerU Cloud）✓
- qmd 检索：BM25 `search` 命中；混合 `query`（查询扩展+重排，模型已缓存本机）Score 100% ✓
- VPS qmd：kb-agent-docs 集合（`**/*.pdf`，5 份 PDF）索引 + `search "信贷 政策"` 命中 ✓
- kb-agent 运行时经 API 拉取 mineru/qmd 工具清单 ✓

## 已踩的坑（详见 mineru-mcp skill 排障表）

1. VPS 8001 端口被旧 MCP（HN/arxiv）占用 → mineru-mcp 用 **8201**
2. pm2 daemon 不继承 CLI 环境变量 → 必须 wrapper 脚本注入 secret
3. qmd HTTP 监听 `[::1]` → 客户端 URL 写 `localhost` 不写 `127.0.0.1`
4. qmd 索引 PDF 静默 0 文件 → 缺 `mineru-open-sdk`（装进 qmd 专用 venv，PATH 前置）
5. 集合默认 mask `**/*.md`，PDF 要显式 `--mask '**/*.{md,pdf,docx,pptx}'`
6. SSH 频繁新建连接触发 VPS 限流 → ControlMaster 复用

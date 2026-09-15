---
name: mineru-mcp
description: "MinerU 两个 MCP 服务的接入与运维：mineru-mcp（解析，streamable-http :8201）与 qmd-mcp（检索/深读 :8181）。触发词：MCP 配置、mineru 服务挂了、MCP 端口、给智能体接 MinerU。含端点、pm2、stdio/http 配置样例与故障排查。"
metadata:
  poc_version: "0.1"
---

# mineru-mcp

## 渐进加载合同

L1 摘要（YAML description）→ L2 本正文 → L3 故障排查时看「排障」节。

## 名称

`mineru-mcp`

## 描述

MinerU 两个官方 MCP Server 在顺德 POC 环境的接入与运维手册。给 QwenPaw 智能体（或 Claude Code / Cursor 等）绑定 MinerU 能力时用本技能。

## 两个服务

| 服务 | 端点（VPS 72.60.193.189 本机回环） | 提供 | pm2 名 | 启动脚本 |
|------|------|------|------|------|
| mineru-open-mcp（文档解析） | `http://127.0.0.1:8201/mcp`（streamable-http） | `parse_documents`、`get_ocr_languages` | `mineru-mcp` | `/root/bin/start-mineru-mcp.sh` |
| qmd mcp（检索/深读/wiki） | `http://localhost:8181/mcp`（HTTP，**监听 `[::1]`，用 localhost 不要写 127.0.0.1**） | 15 工具：query/get/multi_get/status/doc_toc/doc_read/doc_grep/doc_query/doc_elements/doc_links/wiki_ingest/doc_write/wiki_lint/wiki_log/wiki_index | `qmd-mcp` | `/root/bin/start-qmd-mcp.sh` |

本机（Mac）对应：`qmd mcp --http --daemon`（:8181）；`uvx mineru-open-mcp`（stdio 或 `--transport streamable-http --port 8001`，**本机 8001 若被占用换端口**）。

## 认证

- 密钥环境变量：`MINERU_API_TOKEN` / `MINERU_TOKEN`（解析、CLI）、`MINERU_API_KEY`（qmd 的 MinerU Cloud 深读）。
- VPS 统一放 `/root/.qwenpaw.secret/mineru.env`，由启动脚本 `set -a; source; set +a` 注入。**密钥禁止写入文档、代码、Console 描述。**
- 不带 key 服务也能起（Flash 模式），但功能受限。

## 客户端配置样例

stdio（Claude Code / Cursor 等）：

```json
{ "mcpServers": { "mineru": { "command": "uvx", "args": ["mineru-open-mcp"],
    "env": { "MINERU_API_TOKEN": "<从 secret 注入>" } } } }
```

Streamable HTTP（QwenPaw 智能体 / Web 客户端）：

```json
{ "mcpServers": {
  "mineru":    { "type": "streamableHttp", "url": "http://127.0.0.1:8201/mcp" },
  "qmd":       { "type": "streamableHttp", "url": "http://localhost:8181/mcp" } } }
```

QwenPaw 绑定：Console → 智能体工作区 → MCP，按上面 URL 加 streamableHttp 客户端；skill 从技能池下发 `mineru-document-parser` / `mineru-document-explorer`。

## HTTP 握手协议（手工排障用）

1. `POST /mcp` initialize → 从响应头拿 `mcp-session-id`
2. `POST /mcp` + session 头 → `notifications/initialized`
3. `POST /mcp` + session 头 → `tools/list` / `tools/call`
每次 POST 必须 `Accept: application/json, text/event-stream`；结果在 SSE `data:` 行（可能多行，取含对应 id 的那条）。

## 安装布局（VPS）

| 组件 | 位置 |
|------|------|
| qmd（npm 全局） | `/usr/bin/qmd`（node v22） |
| qmd python venv（pymupdf/python-docx/python-pptx/mineru-open-sdk） | `/root/qmd-py` |
| mineru-open-mcp venv | `/root/mineru-mcp-py` |
| 解析输出目录 | `/root/mineru-downloads` |

## 排障

| 症状 | 原因/处理 |
|------|-----------|
| 8201 返回的工具是 search_hn/arxiv | 端口撞了别的 MCP，mineru-mcp 必须用 8201（8001 已被占） |
| pm2 起服务后环境变量丢失 | pm2 daemon 不继承 CLI env；一律走 `/root/bin/start-*.sh` wrapper |
| mineru-mcp errored 反复重启 | 看端口占用 `ss -tlnp \| grep 8201`；换端口改 wrapper 后 `pm2 restart` |
| curl 127.0.0.1:8181 不通 | qmd 绑 `[::1]`，用 `http://localhost:8181/mcp` 或 `http://[::1]:8181/` |
| qmd 索引 PDF 全是 0 个 | 缺 python 依赖：确认 `/root/qmd-py` 里有 pymupdf + mineru-open-sdk，且 qmd 运行时 PATH 里 python3 指向该 venv |
| HTTP 模式无 /health 响应（qmd） | 前台模式 health 探活可能为空，直接 POST initialize 验证 |
| parse 报 401/配额 | token 失效或额度耗尽，去 mineru.net/apiManage 查 |

## 边界

- 两个服务都只绑回环，**不对公网**；nginx 不要反代它们。
- 解析内容上传 mineru.net 云端，涉密文件禁用（见 mineru-document-parser 边界）。
- pm2 已 `pm2 save`，随开机自启清单持久化。

## 相关

技能用法见 [mineru-document-parser]（解析）与 [mineru-document-explorer]（检索/深读）。

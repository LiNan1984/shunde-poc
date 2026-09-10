# QwenPaw v2.0.0 × 顺德农商行 POC 选型：改造评估

> 基于仓库 `QwenPaw/`（`gh` 克隆 `agentscope-ai/QwenPaw`，检出标签 **v2.0.0**，`git describe --tags --exact-match` = `v2.0.0`）对照《人工智能场景拓展与迭代开发技术服务项目-POC选型方案》给出可落地的改造点。  
> **范围**：评估「如何改」；不实现完整 POC 助手，不改需求正文。  
> **密钥纪律**：本文只写环境变量名与配置路径；**禁止**把 Bearer / API Key 写入任何被 git 跟踪的文件。

---

## 0. 结论摘要

| POC 大类 | 与 v2.0.0 的匹配度 | 主要改法 |
|----------|-------------------|----------|
| EXCEL 问答助手（MCP+SKILL） | 高（内置 `xlsx` skill） | 定制 SKILL + 可选 Excel MCP；补异常文件处理 |
| 多模态知识库问答 | 低–中（无银行级 ES/MySQL/图库建库） | 外挂解析管线 + ES/MySQL/GALASYBASE；经 MCP/自定义 Memory 接入 |
| 运营助手（MCP+SKILL+HOOK） | 中–高 | MCP 接运营数据源；Runtime Hook / Middleware 采运营指标 |
| 报告可视化助手 | 中–高（内置 `docx`/`pptx`/`pdf`） | 强化 docx 排版/表格/图表 SKILL 或 MCP |
| 后端部署 | 中（已有多阶段 Dockerfile） | 控镜像体积、补 `/health`、测启动与资源 |
| HARNESS 二次开发 | 高（scroll + ReMe + sandbox 齐全） | 阐述并按需调参/扩展，而非从零造 |

**推荐改造顺序**见文末 §8。

---

## 1. EXCEL 文件问答助手（MCP + SKILL）

### POC 要求（对照）

- 基于 MCP+SKILL 在 QwenPaw 上开发 Excel 问答助手；12 道测题覆盖读/查/析/写。
- MCP：损坏检测、编码自动识别、超大文件分块。
- SKILL：描述清晰、触发条件明确、输入输出与边界；交付 SKILL 文档。

### 源码中已有的扩展点

| 机制 | 真实路径 / 说明 |
|------|-----------------|
| 内置 Excel Skill | `src/qwenpaw/agents/skills/xlsx-zh/SKILL.md`、`xlsx-en/`（openpyxl + pandas + `scripts/recalc.py`） |
| Skill 池 / 工作区副本 | 文档 `website/public/docs/skills.zh.md`；运行时 `$QWENPAW_WORKING_DIR/skill_pool/` 与 `workspaces/{agent_id}/skills/` |
| Skill 加载 | `src/qwenpaw/agents/skill_system/`；`runtime/builder.py` 注入 Toolkit |
| 元 Skill（现场造 Skill） | `src/qwenpaw/agents/skills/make-skill-zh/SKILL.md` |
| MCP 客户端配置 | `src/qwenpaw/app/mcp/schemas.py`（`transport`: `stdio` \| `streamable_http` \| `sse`）；`app/mcp/config_service.py`；路由 `app/routers/mcp.py` |
| MCP 文档与导入格式 | `website/public/docs/mcp.zh.md`（`mcpServers` JSON） |
| 测试夹具 | `tests/fixtures/mcp/stdio_echo_server.py`、`http_echo_server.py` |

### 建议改造点

1. **SKILL（必做）**  
   - 在技能池新建 `excel-qa-bank/`（或改名），`SKILL.md` frontmatter 写清 `name` / `description`（触发词）/ 参数与边界。  
   - 可基于 `xlsx-zh` 复制后收窄：只回答「读取、筛选、聚合、写回」类意图；明确「非表格交付物勿触发」。  
   - 用 Console「工作区 → 技能」或 `skill_paths` 挂团队目录；演示时提供 SKILL 文档截图。

2. **MCP（POC 考点：三种异常 Excel）**  
   - 内置 `xlsx` skill **不会**系统化覆盖「损坏 / 编码 / 超大分块」三类 MCP 验收项。  
   - **改造**：单独实现 `excel-guard` MCP（stdio，FastMCP 可参考 `tests/fixtures/mcp/stdio_echo_server.py`），工具例如：  
     - `detect_corrupt_workbook`  
     - `detect_encoding`  
     - `chunk_large_workbook`  
   - 在 Console「智能体 → MCP」导入 `mcpServers` 配置，或写入 `workspaces/{agent_id}/agent.json` → `mcp.clients`。

3. **Agent 装配**  
   - 启用 `xlsx` + 自定义 `excel-qa-bank` skill；启用上述 MCP；必要时关闭无关 builtin tools，降低误调。

### 风险

- Skill 触发依赖模型对 `description` 的匹配；演示前用固定问法回归。  
- 超大 Excel 在沙箱内内存/超时需结合 `src/qwenpaw/sandbox/` 与工具超时策略调参。

---

## 2. 多模态文件问答助手（知识库）

### POC 要求（对照）

- 文档解析：原生文本、扫描 OCR、表格保留 csv/html/json、图片短描述；切块截图。  
- 建库：对象存储存页图；关系库存元数据；向量库存块向量。  
- 检索：关键词/BM25、文本向量、图像向量、过滤（文档 ID/章节/页码）。  
- 缺块漏块问答（4 题）。  
- 软件要求：向量库 **ElasticSearch**，关系库 **MySQL**，图库 **GALASYBASE**；模型含 MinerU / Reranker / Embedding。

### 源码中已有的扩展点

| 机制 | 真实路径 / 说明 |
|------|-----------------|
| 长期记忆 ReMe（本地 BM25 + 可选向量 + RRF） | `src/qwenpaw/agents/memory/reme_light_memory_manager.py`、`reme_config.py`；文档 `website/public/docs/memory.zh.md` |
| Embedding 配置 | `src/qwenpaw/config/config.py` → `EmbeddingModelConfig`（`backend`/`api_key`/`base_url`/`model_name`） |
| 云 PG 记忆备选 | `agents/memory/adbpg_*.py`（AnalyticDB PG REST，**不是** MySQL/ES/GALASYBASE） |
| PDF/OCR Skill | `agents/skills/pdf-zh/SKILL.md`（含 pytesseract OCR 示例，按需解析，非入库管线） |
| 媒体查看 | `agents/tools/view_media.py` |
| Memory 后端注册 | `agents/memory/base_memory_manager.py`（`memory_registry`） |

### 建议改造点

1. **不要指望开箱即用的「银行知识库」**  
   - v2.0.0 **没有** ElasticSearch / MySQL / GALASYBASE 客户端或建库流水线。  
   - ReMe 默认是工作区文件 + 本地 BM25/本地 embedding store，资源监听后缀主要为 `md/txt/json/csv/...`，不是 PDF/扫描件对象存储体系。

2. **推荐架构（二次开发）**  
   - **离线/旁路服务**：MinerU（POC 要求 `MinerU2.5-Pro-2604-1.2B`）做解析与切块 → 页图进对象存储 → 元数据写 MySQL → 块向量写 ElasticSearch；图关系写 GALASYBASE（若测题需要）。  
   - **接入 QwenPaw**：  
     - **路径 A（推荐 POC）**：实现 `kb-rag` MCP（检索/过滤/缺块补召回工具），Agent 侧再配 `kb-qa` Skill 规定问答流程。  
     - **路径 B**：实现自定义 `BaseMemoryManager`（`@memory_registry.register(...)`），把 `memory_search` 转到 ES+Reranker。  
   - Embedding / Rerank：用 OpenAI 兼容 `base_url` 指向行内部署的 `Qwen3-Embedding-8B`、`Qwen3-Reranker-0.6B`（见 §7）。

3. **演示物**  
   - 解析/切块/索引代码截图；缺块测题走 MCP `retrieve(doc_id, page_range, ...)` 可观测日志。

### 未知 / 勿臆造

- GALASYBASE 在本公开仓库中 **零引用**；连接协议与 schema 需行方另行提供。  
- 行方「对象存储」具体产品未在 POC 正文钉死；评估时按 MinIO/OSS 兼容接口预留。

---

## 3. 运营助手（MCP + SKILL + HOOK）

### POC 要求（对照）

- 运营数据问答与分析；业务理解（如何把智能体使用情况反馈运营/开发）。  
- HOOK：会话/渠道/用户活跃；token/模型/失败率；用户反馈/转化；工具调用/耗时/人工确认。

### 源码中已有的扩展点

| 机制 | 真实路径 / 说明 |
|------|-----------------|
| Runtime 生命周期 Hook（8 相位） | `src/qwenpaw/runtime/phases.py`（`PRE_DISPATCH`…`FINALLY`）；`runtime/hooks.py`；业务钩子目录 `src/qwenpaw/hooks/` |
| 插件注册 Runtime Hook | `src/qwenpaw/plugins/api.py` → `register_runtime_hook` |
| AgentScope Middleware | `plugins/api.py` → `register_middleware`；示例 `plugins/middleware-demo/thinking-log-middleware/`、`tracing-middleware/` |
| 进程级 startup/shutdown Hook | `register_startup_hook` / `register_shutdown_hook` |
| Token 用量 API | `src/qwenpaw/app/routers/token_usage.py`、`src/qwenpaw/token_usage/` |
| Agent 统计 API | `src/qwenpaw/app/routers/agent_stats.py`、`src/qwenpaw/agent_stats/` |
| MCP | 同 §1 |
| Langfuse 观测 Hook | `src/qwenpaw/hooks/observability/langfuse_hook.py` |

### 建议改造点

1. **MCP**  
   - 对接模拟/真实运营库（指标、活动、转化表）：`ops-metrics` MCP（HTTP 或 stdio）。  
   - 工具命名与测题字段对齐，便于评分。

2. **SKILL**  
   - `ops-assistant` Skill：触发词含「活跃度 / 转化 / token / 失败率 / 工具耗时」；规定先调 MCP/内置 stats API，再总结。

3. **HOOK（POC 重点讲解）** — 对应指标的获取方案：  
   - **会话/渠道/用户活跃**：`POST_RESPONSE` / `PRE_DISPATCH` LifecycleHook 读 `HookContext`（`session_id`/`agent_id`/channel）写入运营侧；或复用 `agent_stats` 服务聚合。  
   - **token/模型/失败率**：订阅 `token_usage` 汇总 + `ON_ERROR` Hook 记失败；可选 Langfuse。  
   - **用户反馈/转化**：自定义 HTTP 插件路由（`register_http_router`）收反馈事件；或 MCP 写回。  
   - **工具调用/耗时/人工确认**：Middleware `on_acting`（见 middleware-demo）+ Drivers 审批策略（`src/qwenpaw/drivers/`）；人工确认走 MCP access policy `ask`。

4. **插件骨架**  
   - `plugins/` 下新增 `ops-telemetry`：`plugin.json` + `register_runtime_hook` + 可选 `register_middleware`。文档：`website/public/docs/plugins.zh.md`。

---

## 4. 报告可视化助手

### POC 要求（对照）

- 纯文字（含数据）→ 可视化报告（doc）；考察解析、排版、动态表格、图表（柱/折/饼/面积/散点）。

### 源码中已有的扩展点

| 机制 | 真实路径 / 说明 |
|------|-----------------|
| Word Skill | `src/qwenpaw/agents/skills/docx-zh/SKILL.md`（标题/页眉页脚/表格等） |
| PPT / PDF | `pptx-zh/`、`pdf-zh/`（reportlab 等） |
| 表格 | `xlsx-zh/` |
| 图像生成插件 | `plugins/tool/qwen-image/`、`gpt-image2/`、`wan27/` |
| MCP | 可挂「图表渲染」服务 |

### 建议改造点

1. 新建 `report-viz` Skill：强制输出 `.docx`；清单化验收项（标题层级、段落间距、页眉页脚、交叉表、五类图）。  
2. 图表：在 Skill `scripts/` 用 matplotlib/plotly 生成图 → 插入 docx；或 MCP `render_chart` 返回图片路径。  
3. 动态交叉表：pandas pivot → openpyxl/docx 表格；与 Excel 助手复用解析逻辑。  
4. HOOK 可选：`POST_RESPONSE` 归档报告路径到工作区 `resource/` 便于评委复查。

### 缺口

- 核心**无**内置 ECharts/BI 引擎；可视化能力需 Skill/MCP 补齐。

---

## 5. 后端部署能力

### POC 要求（对照）

- Dockerfile 多阶段、层优化；镜像体积低于 500MB；构建低于 5min。  
- 启动低于 30s；健康检查 `/health`；CPU 低于 2 核、内存低于 2GB。

### 源码中已有的扩展点

| 机制 | 真实路径 / 说明 |
|------|-----------------|
| 多阶段 Dockerfile | `deploy/Dockerfile`（console-builder → runtime；Chromium/Xvfb；端口 8088） |
| 入口 / supervisord | `deploy/entrypoint.sh`、`deploy/config/supervisord.conf.template` |
| Compose | `docker-compose.yml`（`qwenpaw-data` / `qwenpaw-secrets` / `qwenpaw-backups`） |
| 版本探测 | `GET /api/version`（`src/qwenpaw/app/_app.py`） |
| 频道健康 | `/api/config/channels/{channel}/health` |
| 构建脚本 | `scripts/docker_build.sh` |

### 建议改造点

1. **镜像体积**：官方镜像含 Chromium + 桌面相关包，**极易超过 500MB**。POC 应用：  
   - 裁剪 Dockerfile（去掉 xfce/chromium 若不测浏览器 Skill）；多阶段只拷必要 wheel；`.dockerignore`。  
   - 或单独打「精简 POC 镜像」分支，演示时用该镜像截图。  
2. **健康检查**：仓库**无**标准 `GET /health`。需新增 FastAPI 路由（例如返回 `{"status":"ok"}`），Docker/`docker-compose` `healthcheck` 指向它；勿把 `/api/version` 口头当成 `/health` 而不改代码。  
3. **启动与资源**：测 `qwenpaw app` 冷启动；限制 compose `cpus`/`mem_limit`；截图 `docker stats`。  
4. **密钥卷**：继续把 secrets 挂在 `QWENPAW_SECRET_DIR`（默认容器内 `/app/working.secret`），与数据卷分离（已有 compose 设计）。

---

## 6. HARNESS 能力（源码二次开发阐述）

### POC 要求（对照）

- 上下文压缩优化；长期记忆优化；工具执行沙箱隔离（进程/网络/文件系统 + 资源限制 + 审计）。

### 源码中已有的扩展点

| 主题 | 真实路径 / 说明 |
|------|-----------------|
| 默认 scroll 上下文（非摘要驱逐 + `history.db` + `recall_history`） | `website/public/docs/context.zh.md`；`src/qwenpaw/agents/context/scroll/`；配置 `light_context_config.strategy`: `scroll` \| `native`（`config/config.py`） |
| 长期记忆 ReMe | `website/public/docs/memory.zh.md`；`agents/memory/reme_*`；BM25+向量 RRF |
| 沙箱 | `src/qwenpaw/sandbox/config.py`（`SEATBELT`/`BUBBLEWRAP`/`LANDLOCK`/`APPCONTAINER`/`NONE`）；各平台 `*_sandbox.py` |
| 治理 / 工具守卫 | `src/qwenpaw/governance/`、`security/tool_guard/` |
| 工具结果裁剪 | `agents/middlewares.py`（ToolResultPruningMiddleware） |

### 建议改造点（以「方案阐述 + 可演示调参」为主）

1. **上下文压缩**  
   - 阐述 scroll：先落盘再驱逐、headline 索引、三级泄压（驱逐→压实→折叠工具结果）。  
   - 可调：`compact_threshold_ratio`、`QWENPAW_MEMORY_COMPACT_RATIO`、`QWENPAW_MEMORY_COMPACT_KEEP_RECENT`。  
   - 若评委要「摘要式压缩」：对比切换 `strategy: "native"` 的利弊（信息保留率 vs 可回溯性）。

2. **长期记忆**  
   - 数据结构：`memory/YYYY-MM-DD/*.md`、`digest/`、`mem_metadata/`、SQLite `history.db`。  
   - 更新策略：auto_memory / auto_dream / resource watch。  
   - 若必须接 ES/MySQL：走自定义 MemoryManager（与 §2 合并），勿谎称 ReMe 已是 ES。

3. **沙箱隔离**  
   - Linux POC 环境优先 `bubblewrap`；配置 `SandboxConfig` 的 mounts / deny_paths / 网络 PortRule。  
   - 结合 security 策略做操作日志与人工确认（MCP policy `ask`）。  
   - 明确：公开树里的沙箱是 **OS 级隔离原语**，CPU/内存 cgroup 限额更多依赖容器运行时（compose/k8s）叠加。

---

## 7. Aliyun MaaS OpenAI 兼容端点接入（密钥仅环境/本地）

### 给定端点形态（OBJECTIVE curl）

- Chat Completions：`https://llm-sdrdvdc4nofepa95.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions`  
- 故 Provider **Base URL** 应为：  
  `https://llm-sdrdvdc4nofepa95.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`  
- curl 中的 **model id**：`qwen3.5-35b-a3b`（注意：与 POC 软件要求中的 **Qwen3.6-35B / Qwen3.6-27B** 不一致，合规差距见 §8）

### 推荐接入方式（不改核心也可）

1. Console：**设置 → 模型 → 添加提供商**  
   - API 兼容模式：OpenAI `chat.completions`  
   - 基础 URL：上列 Base URL  
   - API 密钥：粘贴后仅写入本地密钥目录  
2. 在该提供商下 **添加模型**：模型 ID = 实际 API 的 model 字段；展示名可自定。  
3. 设为默认 LLM 或在聊天页指定。

文档依据：`website/public/docs/models.zh.md`（自定义供应商 / OpenAI 兼容）；密钥落盘：`$QWENPAW_SECRET_DIR/providers/`（默认 `~/.qwenpaw.secret/providers`，Docker `/app/working.secret`）。  
另见 `website/public/docs/config.zh.md`：`QWENPAW_SECRET_DIR`、`providers.json` / `envs.json`。

### 与内置阿里云入口的关系

- 内置 `dashscope`：`https://dashscope.aliyuncs.com/compatible-mode/v1`（`providers/provider_manager.py`）。  
- 内置 `aliyun-tokenplan`：`https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`（**freeze_url**，与本次自定义 hostname `llm-sdrdvdc4nofepa95...` **不同**）。  
- **结论**：本次 POC 探针端点应走 **自定义 OpenAI 兼容提供商**（或 fork 增加 builtin），不要硬塞进 freeze 的 token-plan URL。

### 环境变量约定（写入 gitignored 本地，禁止提交密钥）

建议仅在本机 / CI secret / Docker `-e` 使用：

| 变量名 | 用途 |
|--------|------|
| `QWENPAW_MAAS_API_KEY` | Bearer token（或同步到 Console 环境变量页 / `envs.json`） |
| `QWENPAW_MAAS_BASE_URL` | `https://llm-sdrdvdc4nofepa95.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |
| `QWENPAW_MAAS_MODEL` | 实际调用的 model id（演示可用 `qwen3.5-35b-a3b`；验收清单仍应对齐 Qwen3.6-*） |

仓库已忽略 `.env`、`.env.*`、`providers.json`（见 `QwenPaw/.gitignore`）。  
**禁止**把密钥写进 `docs/`、`tests/`、compose 明文、或任何跟踪文件。若密钥曾出现在聊天/OBJECTIVE 中，建议在云控制台轮换。

### 探针示例（仅本地执行）

```bash
# 密钥必须来自环境，勿写入仓库
curl -sS -X POST "${QWENPAW_MAAS_BASE_URL}/chat/completions" \
  -H "Authorization: Bearer ${QWENPAW_MAAS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"${QWENPAW_MAAS_MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"max_tokens\":64}"
```

---

## 8. 与 POC「软件要求」的差距清单 + 优先改造顺序

### 差距清单

| 要求 | v2.0.0 现状 | 差距等级 |
|------|-------------|----------|
| QwenPaw **v2.0.0** | 已克隆并检出该 tag | 已满足（基线） |
| 向量库 ElasticSearch | 无；ReMe 本地 BM25/local embedding | **高** |
| 关系库 MySQL | 无应用级 MySQL；多为文件 + SQLite | **高** |
| 图库 GALASYBASE | 仓库无引用 | **高**（接口未知） |
| 模型 Qwen3.6-35B / Qwen3.6-27B | 需行内部署或 MaaS 提供对应 model id | **高**（与探针 `qwen3.5-35b-a3b` 不一致） |
| MinerU2.5-Pro / Qwen3-Reranker / Qwen3-Embedding | 无内置托管；需外挂服务 + 配置 embedding/rerank | **高** |
| 服务自研可内网部署（除模型） | QwenPaw 开源可内网；依赖需离线镜像 | **中** |
| Vscode+Cline+Qwen3.6-27B vibe-coding | 流程/环境约束，非产品功能 | **中**（人力与环境准备） |
| `/health` 健康检查 | 仅有 `/api/version` 与频道 health | **中** |
| 镜像体积低于 500MB | 官方 Dockerfile 含 Chromium，偏大 | **中** |
| Excel 损坏/编码/分块 MCP | 需自研 MCP | **中** |
| 报告五类图表 | 需 Skill/脚本补齐 | **中** |
| HARNESS（压缩/记忆/沙箱） | 能力已在树内，偏「讲清+调参」 | **低**（方案工作量） |

### 推荐改造优先级（实施顺序）

1. **模型与密钥接入** — 自定义 OpenAI 兼容 Provider + 环境变量；同时确认行方是否提供 **Qwen3.6-*** 与 embedding/rerank/MinerU 端点（堵住合规口径）。  
2. **Excel 助手（SKILL + 异常 MCP）** — 最快出演示分；复用 `xlsx`。  
3. **报告可视化 Skill** — 复用 `docx` + 图表脚本；与 Excel 共享数据能力。  
4. **运营助手 Hook/Middleware + stats MCP** — 展示对 Runtime Hook 与 token/agent_stats 的掌握。  
5. **后端镜像精简 + `/health`** — 满足部署截图项。  
6. **多模态知识库旁路（ES+MySQL[+GALASYBASE]）+ MCP/自定义 Memory** — 工作量最大，与软件要求绑定最紧，需并行排期。  
7. **HARNESS 方案文档与调参演示** — 基于 scroll/ReMe/sandbox 源码讲解，按需小改配置。

---

## 9. 非目标与后续

- 本评估不实现 12/4 测题跑分、不搭建完整银行中间件、不替换 QwenPaw。  
- 后续实现目标可按 §8 顺序开独立 goal；密钥继续只进 `QWENPAW_SECRET_DIR` / 环境变量。

---

## 附录 A. 关键路径速查

```
QwenPaw/   # tag v2.0.0
├── deploy/Dockerfile
├── docker-compose.yml
├── website/public/docs/{mcp,skills,models,memory,context,plugins,config}.zh.md
├── src/qwenpaw/
│   ├── app/mcp/
│   ├── hooks/ + runtime/{hooks,phases}.py
│   ├── plugins/api.py
│   ├── providers/provider_manager.py
│   ├── agents/skills/{xlsx,docx,pdf,pptx,make-skill}-zh/
│   ├── agents/memory/ + agents/context/scroll/
│   └── sandbox/
└── plugins/middleware-demo/
```

## 附录 B. 证据文件（本目标 scratch）

- `{SCRATCH}/gh-clone.log` — clone / tag 校验  
- `{SCRATCH}/qwenpaw-extension-scan.log` — 扩展点扫描  
- `{SCRATCH}/maas-probe.log` — 可选 MaaS 探针（成功增强信心；失败不否定文档评估）

# 顺德农商行 POC 交接文档

| 项 | 内容 |
|----|------|
| 项目 | 人工智能场景拓展与迭代开发技术服务项目 — POC 选型 |
| 宿主框架 | [agentscope-ai/QwenPaw](https://github.com/agentscope-ai/QwenPaw) **v2.0.0** |
| 工作区 | `/Users/linan/Desktop/aicode/shunde`（本机路径；交接后请替换为接手人 clone 路径） |
| 交接日期 | 2026-03-22 |
| 文档版本 | v1.0 |

---

## 1. 一句话现状

**评估与改造路径已写清；QwenPaw v2.0.0 已本地检出；Phase 1（Excel 异常 MCP + 问答 Skill）代码已落地并通过单测，但尚未挂到 QwenPaw Console 做现场演示。其余五大场景（知识库 / 运营 / 报告 / 部署 / HARNESS）未开发。缺口主因不是「数据埋点」。**

---

## 2. 目标与范围（接手人必读）

### 2.1 POC 考察六大类

1. EXCEL 文件问答助手（MCP + SKILL）  
2. 多模态文件问答助手（知识库：ES + MySQL + GALASYBASE 等）  
3. 运营助手（MCP + SKILL + **HOOK/埋点**）  
4. 报告可视化助手  
5. 后端部署能力（镜像 / `/health` / 资源）  
6. HARNESS 二次开发（上下文压缩 / 长期记忆 / 沙箱方案阐述）

需求原文：仓库根目录  
`人工智能场景拓展与迭代开发技术服务项目-POC选型方案.docx`（未纳入 git，请自行保管）。

### 2.2 本仓库 intentionally 不做的事

- **不 fork 改 QwenPaw 核心**：扩展放在 `poc/`，通过 MCP / Skill / 插件旁路接入。  
- **不提交 API Key**：密钥只进环境变量 / `QWENPAW_SECRET_DIR`（默认 `~/.qwenpaw.secret`）。  
- **未跑官方 12/4 测题满分回归**、未出部署达标截图。

---

## 3. 仓库结构

```
shunde/
├── 人工智能场景拓展与迭代开发技术服务项目-POC选型方案.docx   # 需求（未跟踪）
├── QwenPaw/                    # gh 克隆，tag v2.0.0（workspace .gitignore，本地保留）
├── docs/
│   ├── HANDOFF.md              # 本文
│   ├── qwenpaw-poc-modification-evaluation.md   # 如何改（扩展点+差距）
│   ├── poc-completion-gap-qa.md                 # 还差多少 / 埋点结论 / 工期 / 验收
│   └── superpowers/plans/
│       └── 2026-03-22-poc-phase1-excel-plan.md  # 分阶段计划 + P1 任务
├── poc/                        # ★ Phase 1 已实现代码
│   ├── excel_guard_mcp/        # FastMCP：损坏 / 编码 / 分块
│   ├── skills/excel-qa-bank/   # SKILL.md
│   ├── config/mcp-excel-guard.json
│   ├── fixtures/               # 三种异常样例
│   ├── tests/                  # pytest
│   └── README.md               # 挂载到 QwenPaw 的步骤
├── tests/                      # 评估文档结构性测试
├── .venv/                      # 本地虚拟环境（gitignore）
├── .env.example                # MaaS 环境变量名（无密钥）
└── .gitignore
```

**注意：** `QwenPaw/` 在 workspace git 中被 ignore，接手后需自行：

```bash
gh repo clone agentscope-ai/QwenPaw -- --branch v2.0.0
# 或 cd QwenPaw && git fetch --tags && git checkout v2.0.0
git -C QwenPaw describe --tags --exact-match   # 期望输出：v2.0.0
```

---

## 4. 已完成清单

| 项 | 位置 / 证据 | 说明 |
|----|-------------|------|
| QwenPaw v2.0.0 检出 | 本地 `QwenPaw/` | POC 软件要求基线 |
| 改造评估 | `docs/qwenpaw-poc-modification-evaluation.md` | 六大类扩展点与真实路径 |
| 完成度问答 | `docs/poc-completion-gap-qa.md` | Verdict：**主要不是埋点**；工期 34～52 人·日 |
| 分阶段开发计划 | `docs/superpowers/plans/2026-03-22-poc-phase1-excel-plan.md` | P0～P6 |
| Phase 1 Excel MCP | `poc/excel_guard_mcp/` | 三工具 + `POC_WORKSPACE` 路径沙箱 |
| Phase 1 Excel Skill | `poc/skills/excel-qa-bank/SKILL.md` | 含触发词/参数/边界/MCP 协作 |
| Phase 1 测试 | `pytest poc/tests` | **13 passed**（交接前已跑通） |
| MaaS 探针约定 | `.env.example` + 评估 §7 | Base URL / model 用环境变量；**勿提交 Bearer** |
| 评估文档测试 | `tests/test_poc_*.py` | 结构校验 |

### Phase 1 MCP 工具一览

| 工具名 | 作用 |
|--------|------|
| `detect_corrupt_workbook` | 损坏 / 非 OOXML 提示 |
| `detect_encoding` | CSV/文本编码探测（限流采样） |
| `chunk_large_workbook` | 超大表行分块范围 |

样例文件：`poc/fixtures/{corrupt.xlsx, encoding_gbk.csv, encoding_latin1.csv, large_chunk_demo.xlsx}`。

---

## 5. 未完成 / 接手优先序

> `poc-completion-gap-qa.md` 写于 Phase 1 落地前；下表以**当前代码事实**为准。

| 优先级 | 工作 | 状态 | 建议人·日 |
|--------|------|------|-----------|
| **立刻** | 将 Phase 1 MCP/Skill **挂到 QwenPaw Console** 并彩排三种异常文件 | 文档有步骤，未实机挂载验收 | 0.5～1 |
| **立刻** | 确认行方模型：**Qwen3.6-35B/27B**（当前探针曾用 `qwen3.5-35b-a3b`，不合规口径） | 未对齐 | 0.5～1 |
| P1 收尾 | 12 道 Excel 测题预跑答卷 + Agent 装配剧本 | 未做 | 2～3 |
| P2 | 报告可视化 Skill（docx + 交叉表 + 五类图） | 未开始 | 4～6 |
| P3 | 运营助手 + HOOK 四类埋点 | 未开始 | 5～7 |
| P4 | Dockerfile 精简、`GET /health`、资源截图 | 未开始 | 3～5 |
| P5 | 多模态知识库（ES/MySQL/GALASYBASE/MinerU…） | 未开始（最大块） | 12～18 |
| P6 | HARNESS 三方案讲义与调参演示 | 未开始 | 2～3 |

**总日历（2 人并行，环境按时）：约 3.5～5.5 周到 demo-ready。** 详见 gap-qa。

---

## 6. 接手后 48 小时建议动作

1. **拉代码与环境**
   ```bash
   cd <REPO_ROOT>
   git checkout main
   uv venv && source .venv/bin/activate
   uv pip install -r poc/requirements.txt
   pytest poc/tests -v
   ```
2. **确认 QwenPaw tag**
   ```bash
   git -C QwenPaw describe --tags --exact-match   # → v2.0.0
   ```
3. **挂载 Phase 1（按 `poc/README.md`）**
   - 复制 `poc/config/mcp-excel-guard.json`，把所有 `<REPO_ROOT>` 换成绝对路径；  
   - `env.POC_WORKSPACE=<REPO_ROOT>`；  
   - Console → 智能体 → MCP 导入；  
   - `config.json` 增加 `skill_paths: ["<REPO_ROOT>/poc/skills"]`，广播 `excel-qa-bank`。  
4. **用 fixtures 手测三种异常提示是否出现在对话里。**  
5. **向行方确认**：Qwen3.6 端点、ES/MySQL/GALASYBASE、MinerU/Embedding/Reranker、GALASYBASE 接口文档。  
6. **轮换密钥**：若 MaaS Bearer 曾出现在聊天记录中，请在云控制台轮换；仓库内不应有明文 key。

---

## 7. 密钥与安全约定

| 规则 | 说明 |
|------|------|
| 禁止提交 | `.env`、Bearer、`providers.json`、真实 API Key |
| 推荐变量 | `QWENPAW_MAAS_API_KEY` / `QWENPAW_MAAS_BASE_URL` / `QWENPAW_MAAS_MODEL` |
| 密钥目录 | `$QWENPAW_SECRET_DIR`（Docker 常见 `/app/working.secret`） |
| MCP 沙箱 | `POC_WORKSPACE` 限制可读路径，防止读 `/etc/passwd` 等 |
| 配置模板 | `poc/config/mcp-excel-guard.json` 使用占位符 `<REPO_ROOT>`，勿提交本机绝对路径进共享分支（可本地另存） |

MaaS 形态参考（无密钥）：

- Base URL：`https://llm-sdrdvdc4nofepa95.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`  
- 在 QwenPaw：**自定义 OpenAI compatible Provider**（勿硬套 freeze 的 token-plan 内置 URL）

---

## 8. 关键文档索引

| 文档 | 用途 |
|------|------|
| 本文 `docs/HANDOFF.md` | 交接总览与接手步骤 |
| `docs/qwenpaw-poc-modification-evaluation.md` | 源码扩展点、怎么改 |
| `docs/poc-completion-gap-qa.md` | 完成度、埋点结论、工期、24 条验收标准 |
| `docs/superpowers/plans/2026-03-22-poc-phase1-excel-plan.md` | 阶段计划与 P1 DoD |
| `poc/README.md` | Phase 1 挂载实操 |
| POC 选型方案 `.docx` | 官方考察点与测例 |

---

## 9. 已知风险与坑

1. **官方镜像偏大**：含 Chromium，500MB 指标需裁剪 Dockerfile，勿直接交官方镜像体积。  
2. **无 `/health`**：目前仅有 `/api/version` 等；部署项需自加路由。  
3. **知识库不能指望 ReMe 顶替 ES/MySQL/GALASYBASE**：公开树无 GALASYBASE 引用。  
4. **gap-qa 中 Excel「未开发」表述已过时**：代码已有，缺的是 Console 挂载与 12 题答卷。  
5. **chardet 对短 latin-1 样例置信度可能很低**：演示优先用 `encoding_gbk.csv`。  
6. **Vibe Coding 环境**：行方要求 VS Code + Cline + Qwen3.6-27B，属过程举证，非产品功能。

---

## 10. 验收标准速查（演示打分用）

完整 24 条见 `docs/poc-completion-gap-qa.md` §Q5。最低记忆：

- Excel：12 题 + **三种异常 MCP 提示** + SKILL 文档字段齐全  
- 知识库：解析/三库/检索 + 缺块 4 题  
- 运营：数据问答 + 业务理解 + **HOOK 四类**  
- 报告：docx 排版/表/五类图  
- 部署：镜像 &lt;500MB、启动、**`/health`**、资源截图  
- HARNESS：压缩 / 记忆 / 沙箱三方案可讲清  

---

## 11. 联系与决策备忘

| 议题 | 当前结论 |
|------|----------|
| 是不是差埋点？ | **主要不是**；埋点属运营助手子集（约 10%～15%） |
| 扩展策略 | `poc/` 旁路，不改 QwenPaw 内核 |
| 下一波开发建议 | 先完成 Phase 1 Console 挂载彩排 → P2 报告 或 P3 运营（按评委权重选） |
| Agent Team | 已用过多 agent 并行做过评估扫描与 P1 实现；后续阶段可同样拆 MCP / Skill / Hook |

---

## 12. 交接检查表（签字用）

- [ ] 接手人已 `pytest poc/tests -v` 全绿  
- [ ] 接手人已确认 `QwenPaw` = v2.0.0  
- [ ] 接手人已阅读评估文 + gap-qa + 本 HANDOFF  
- [ ] 密钥未从聊天记录明文落盘；需轮换的已轮换  
- [ ] Phase 1 MCP/Skill 已在至少一台机器挂到 Console 并手测 fixtures  
- [ ] 行方模型与中间件环境接口人、时间点已对齐  

**交出方：** ________________　日期：________  
**接手方：** ________________　日期：________  

---

*本文随仓库维护；重大进度变化请同步改 §4 / §5，并视情况修订 gap-qa 中已过时条目。*

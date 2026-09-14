# 顺德 POC — HOOK 开发能力交接文档

> **性质**：场景③（需求用例 3-3「HOOK 开发能力」）的开发侧专题交接。  
> **与其它文档分工**：`docs/HANDOFF.md` 管全局接手；`docs/最终验收交接文档.md` 管行方验收；`docs/前端四助手交接文档.md` 管 Console 演示。本文只讲 **Hook 从哪来、数据写到哪、怎么挂、怎么验收**。  
> **交接日期**：2026-09-14 ｜ **宿主**：QwenPaw **v2.0.0** ｜ **内核改动**：0 行

---

## 1. 一句话结论

**QwenPaw 原本就有完整 Hook 体系。POC 没有给内核补 Hook，只是用官方 `HookBase` + `register_runtime_hook` 旁路写了 4 类运营埋点。埋点不进数据库，落盘为 JSONL。**

---

## 2. 接手人先记住的 4 件事

| # | 事实 | 不要搞反 |
|---|------|----------|
| 1 | Hook **框架**是 QwenPaw 内核原有能力 | 不要去 `QwenPaw/src` 里「加一套 hook」 |
| 2 | POC 只写 **观察型** 业务 hook | 禁止 `SHORT_CIRCUIT` / 改 agent 状态 |
| 3 | 数据在 **JSONL 文件**，不是 MySQL / ES / SQLite | 不要去库里找埋点 |
| 4 | 运营问答走 `ops-data` MCP 读这些 JSONL | 没有文件时必须说「暂无埋点」，禁止编造 |

---

## 3. QwenPaw 原本有没有 Hook？

**有。** 本仓库锁定的 `QwenPaw v2.0.0` 里 Hook 是 Runtime 一等公民，不是 POC 后加的。

### 3.1 三层不要混

| 层 | 作用 | 官方入口 | 本 POC 用没用 |
|----|------|----------|---------------|
| **Runtime 生命周期 Hook** | 每次请求经过 8 个固定相位 | `src/qwenpaw/runtime/hooks.py` 的 `HookBase`；插件 `api.register_runtime_hook()` | **用了**（场景③） |
| **App 级 Hook 插件** | 进程启动 / 关闭执行一次 | `register_startup_hook` / `register_shutdown_hook`；官方文档「Hook 插件」主要指这个 | 没用（埋点不需要） |
| **v1 Agent 级 Hook** | 当时项目还叫 CoPaw，走 AgentScope callable | `src/copaw/agents/hooks/`（仅历史 tag `v1.0.0`） | 不用；v2 已换成 Runtime 8 相位 |

### 3.2 Runtime 8 相位（固定点位，可插拔 hook）

来源：`QwenPaw/src/qwenpaw/runtime/phases.py`。**相位点位不能改**；新增能力 = 注册新 hook，不改 `Runtime.run()`。

```
PRE_DISPATCH → slash 分发 → POST_DISPATCH
→ PRE_AGENT_BUILD → 构建 agent → POST_AGENT_BUILD
→ PRE_EXECUTE → 执行 agent → POST_RESPONSE
→（异常）ON_ERROR →（始终）FINALLY
```

每个 hook 可返回：`CONTINUE` / `SHORT_CIRCUIT` / `SKIP_AGENT`。POC 全部观察，等价于 `CONTINUE`（`run()` 返回 `None`）。

### 3.3 内核自己已经在用的 LifecycleHook（举例）

`SessionLoadHook`、`SessionSaveHook`、`BootstrapHook`、`SkillEnvHook`、`LangfuseTraceHook`、`ErrorNormalizeHook` 等，目录：`QwenPaw/src/qwenpaw/hooks/`。

**版本时间线（本机 clone 的 git 事实）：**

- 2026-04-08：插件系统（`#3101`），含 app 启停 hook
- 2026-06-12：Runtime 2.0（`#5078`）引入 `HookBase` + 8 相位
- 2026-07-02：`PluginApi.register_runtime_hook`（`#5665`）
- 2026-07-10：打 tag **v2.0.0**（本仓库基线）

官方说明：`QwenPaw/website/public/blog/runtime-architecture-upgrade.zh.md`、`QwenPaw/website/public/docs/plugins-migration.zh.md`（`register_runtime_hook` 一节）。

---

## 4. POC 交付了什么

需求用例 **3-3 HOOK 开发能力**（场景③运营助手的一部分）。配套还有 3-1 运营数据问答、3-2 业务理解。

```
请求进入 Runtime
    │
    ├─ 6 个 HookBase（poc/hooks/ops_hooks.py）
    │     └─ telemetry.write() 追加一行 JSON
    │           └─ $POC_WORKSPACE/telemetry/<UTC-日期>/ops.jsonl
    │
    └─ 运营问答
          Skill ops-assistant
          → MCP ops-data（3 工具读 JSONL）
          → 禁止编造数字
```

| 部件 | 路径 | 职责 |
|------|------|------|
| 6 个 Hook | `poc/hooks/ops_hooks.py` | 覆盖 5 个 Phase，写 5 类事件 |
| JSONL sink | `poc/hooks/telemetry.py` | 旁路落盘；写失败只打 stderr，**绝不抛回主请求** |
| 插件注册 | `poc/plugins/ops-telemetry/` | `plugin.json` type=`hook`；`register()` 里循环 `api.register_runtime_hook` |
| 读侧 MCP | `poc/ops_mcp/` | `list_telemetry_files_tool` / `summarize_calls_tool` / `recent_events_tool` |
| MCP 配置样例 | `poc/config/mcp-ops-data.json` | 把 `<REPO_ROOT>` 换成绝对路径 |
| Skill | `poc/skills/ops-assistant/SKILL.md` | 触发词 + 先列文件再汇总/列举 |
| 单测 | `poc/tests/test_ops_hooks.py`、`poc/tests/test_ops_mcp.py` | 不启完整 QwenPaw 进程 |

**没有做的事：**

- 没有改 `QwenPaw/` 一行代码（红线 2）
- 没有把埋点写入 MySQL / ES / Galaxybase / sqlite
- 没有接 Langfuse 做 POC 埋点（内核自带 Langfuse hook，与本 JSONL 无关）

---

## 5. 数据存在哪？不是数据库

### 5.1 落盘路径

`poc/hooks/telemetry.py` 解析顺序：

1. 环境变量 `POC_WORKSPACE`
2. 否则 `QWENPAW_WORKING_DIR`
3. 都没有 / 目录不可用 → **静默不写**（主请求继续）

实际文件：

```text
<workspace>/telemetry/<UTC-YYYY-MM-DD>/ops.jsonl
```

典型现场：

| 环境 | 常见路径 |
|------|----------|
| MCP 配置按样例设了 `POC_WORKSPACE=<REPO_ROOT>` | `<REPO_ROOT>/telemetry/2026-09-14/ops.jsonl` |
| Console 默认工作目录（前端交接文档口径） | `~/.qwenpaw/telemetry/YYYY-MM-DD/ops.jsonl` |

**同一台机器可能两处都有文件。** 问答读的是 MCP 进程里的 `POC_WORKSPACE`，Hook 写的是 Hook 进程里的 `POC_WORKSPACE` 或 `QWENPAW_WORKING_DIR`。两边必须对齐，否则演示会「暂无埋点」。

### 5.2 一行长什么样

每行一条 JSON，扁平字段，给 `jq` / pandas 直接用：

```json
{"agent_id":"a1","category":"call_volume","event":"start","session_id":"s1","ts":"2026-09-14T03:12:00Z","workspace_dir":"..."}
```

| `category` | 谁写的 | 关键字段 |
|------------|--------|----------|
| `call_volume` | PRE_DISPATCH start + POST_DISPATCH end | `event`, `session_id`, `agent_id` |
| `latency` | POST_DISPATCH（有 start 时间才写） | `latency_ms` |
| `identity` | PRE_AGENT_BUILD | session/agent/root 对 |
| `token_usage` | POST_RESPONSE | `tokens_in`, `tokens_out`（供应商不给则为 0） |
| `tool_outcome` | PRE_EXECUTE start / ON_ERROR end | `tool`, `status`=`ok`\|`error` |

### 5.3 和「库」的边界

| 存储 | 用途 | 是不是 Hook 埋点 |
|------|------|------------------|
| `telemetry/**/ops.jsonl` | POC Hook 埋点 | **是** |
| 本机 / VPS 的 MySQL、ES | 知识库场景② | 否 |
| `poc/web` 的 `kb_store/meta.sqlite` | 知识库本地 fallback | 否 |
| QwenPaw `token_usage.json` | 内核 token 统计 | 否（POC Token hook 另写 JSONL） |
| Langfuse | 内核观测 hook | 否 |
| session 文件 | 内核 `SessionLoad/SaveHook` | 否 |

`poc/ops_mcp/server_lib.py` 文件头写明：真正的运营库属于后续任务；当前三个工具只读 JSONL。

---

## 6. 六条 Hook 对照

全部在 `poc/hooks/ops_hooks.py` 的 `ALL_HOOKS`。`plugin.py` 按这个列表注册。

| 类 | `name` | `phase` | `priority` | 写出的 category |
|----|--------|---------|------------|-----------------|
| `CallVolumeStartHook` | `poc_call_volume_start` | `PRE_DISPATCH` | 90 | `call_volume`（event=start）；并往 `ctx.extras["poc_dispatch_start"]` 塞 monotonic |
| `CallVolumeEndHook` | `poc_call_volume_end` | `POST_DISPATCH` | 110 | `call_volume`（event=end）；有 start 时再写 `latency` |
| `IdentityHook` | `poc_identity` | `PRE_AGENT_BUILD` | 90 | `identity`（PRE_DISPATCH 被短路时仍能记身份） |
| `TokenUsageHook` | `poc_token_usage` | `POST_RESPONSE` | 90 | `token_usage` |
| `ToolOutcomeHook` | `poc_tool_outcome` | `PRE_EXECUTE` | 90 | `tool_outcome`（status=ok） |
| `ToolErrorHook` | `poc_tool_error` | `ON_ERROR` | 90 | `tool_outcome`（status=error） |

未覆盖的相位：`POST_AGENT_BUILD`、`FINALLY`（清理相位不适合记业务埋点）。

`phase` 在 POC 里用的是 **字符串**（`"PRE_DISPATCH"`），不是 import `Phase` 枚举——为了 CI 在没装 qwenpaw 时也能 import。插件侧 `register_runtime_hook` 会做类型检查。

---

## 7. 安装、挂载、验收

### 7.1 插件（写侧）

QwenPaw **必须离线**才能装插件：

```bash
# 确认内核 tag
git -C QwenPaw describe --tags --exact-match   # → v2.0.0

qwenpaw plugin install <REPO_ROOT>/poc/plugins/ops-telemetry
qwenpaw plugin list    # 应看到 poc-ops-telemetry
```

`plugin.json`：`id=poc-ops-telemetry`，`type=hook`，`meta.hook_type=runtime`，`min_version=2.0.0`。

**已知坑**：`poc/plugins/ops-telemetry/plugin.py` 的 `_bootstrap_poc()` 会把仓库根加入 `sys.path`，候选路径是「插件文件往上两级」以及硬编码 `/Users/linan/Desktop/aicode/shunde`。插件被拷进 `~/.qwenpaw/plugins/` 后，**必须还能 import 到 `poc.hooks`**。换机器时优先保证仓库布局不变，或改候选路径，不要只靠那条硬编码。

### 7.2 MCP + Skill（读侧）

1. Console → 智能体 → MCP，粘贴 `poc/config/mcp-ops-data.json`，所有 `<REPO_ROOT>` 换成绝对路径。  
2. `env.POC_WORKSPACE` 指向**和 Hook 写入相同**的目录。  
3. `skill_paths` 含 `<REPO_ROOT>/poc/skills`，下发 `ops-assistant`。  
4. 演示 Agent：`ops-agent`（见 `docs/前端四助手交接文档.md`）。

### 7.3 单测（不启 Console）

```bash
cd <REPO_ROOT>
source .venv/bin/activate
pytest poc/tests/test_ops_hooks.py poc/tests/test_ops_mcp.py poc/tests/test_skill_doc.py -q
```

`test_ops_hooks.py` 断言：正好 6 个 hook、name 唯一、phase 属于 8 个官方值、`run()` 缺字段也不抛、有 start 时间时写出 `latency`。

### 7.4 现场看有没有写上

触发任意一次对话后：

```bash
tail -f "$POC_WORKSPACE/telemetry/$(date -u +%Y-%m-%d)/ops.jsonl"
```

应陆续看到 `call_volume` / `identity` / `token_usage` 等。没有文件先查：

- 插件是否安装、QwenPaw 是否重启过
- `POC_WORKSPACE` 与 `QWENPAW_WORKING_DIR` 是否指向存在的目录
- 插件能否 `import poc.hooks.ops_hooks`

---

## 8. 演示怎么问

切到 **运营助手**（`ops-agent`）：

- `今天调用量怎么样`
- `最近一次失败的工具是什么`
- `token 用量`
- `哪个工具用得最多`

Skill 规定的工具顺序：

1. `list_telemetry_files_tool` — 确认文件在  
2. 汇总类 → `summarize_calls_tool`  
3. 列举类 → `recent_events_tool`（可带 `category`）

没有 JSONL：返回 `ok=false`，文案含「暂无埋点」。**数字必须来自工具 JSON，禁止模型口算。** 时间用事件里的 UTC `ts`，不要换算营业日。`token_usage` 为 0 时要说明「供应商可能没回用量」。

---

## 9. 红线

1. **不改 `QwenPaw/`**。`git diff QwenPaw/` 必须为空。  
2. **telemetry 不能影响主流程**。写盘失败只 `stderr`，`run()` 不得抛给 Runtime。  
3. **MCP stdio 不污染 stdout**。日志走 stderr。  
4. **不提交密钥**。Hook 链路不需要新密钥。  
5. **不把 JSONL 说成已写入 Galaxybase / MySQL**。

---

## 10. 接手 30 分钟动作

1. 读本文 §2、§5（路径对齐是演示最常见翻车点）。  
2. `git -C QwenPaw describe --tags --exact-match` → `v2.0.0`。  
3. `pytest poc/tests/test_ops_hooks.py poc/tests/test_ops_mcp.py -q`。  
4. 确认插件：`qwenpaw plugin list | grep poc-ops-telemetry`。  
5. 对齐 `POC_WORKSPACE`，发一句「今天调用量怎么样」，`tail` JSONL。  
6. 若换机器：检查 `plugin.py` 能否找到 `poc/hooks/ops_hooks.py`，必要时改 `_bootstrap_poc()` 候选路径。

---

## 11. 相关文档

| 文档 | 关系 |
|------|------|
| `docs/HANDOFF.md` | 开发侧总交接；P3 一行状态 |
| `docs/最终验收交接文档.md` | 行方验收；§3.4 是 HOOK 演示 |
| `docs/前端四助手交接文档.md` | Console 里运营助手怎么问 |
| `docs/qwenpaw-poc-modification-evaluation.md` §3 | 评估阶段：内核已有哪些扩展点 |
| `poc/README.md` Phase 3 | 挂载命令 |
| `QwenPaw/website/public/blog/runtime-architecture-upgrade.zh.md` | 官方 Runtime 2.0 / Hook 设计 |

---

## 12. 签字备忘（开发侧）

| 项 | 内容 |
|----|------|
| 需求编号 | 3-3 HOOK 开发能力（随 3-1 / 3-2 一起构成场景③） |
| 实现策略 | 旁路插件，复用官方 Runtime Hook，不改内核 |
| 存储 | JSONL 文件，非数据库 |
| 状态 | 代码 + 单测已完成；现场效果取决于插件安装与 `POC_WORKSPACE` 对齐 |

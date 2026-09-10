# HARNESS 讲义 2：长期记忆方案

> 场景：智能体跨会话/跨任务保留关键事实，避免用户重复交代。
> 适用：评委问"它怎么记得我是哪家分行的"、"用户偏好怎么不丢"。

## 1. 一页要点

- **QwenPaw v2.0.0 提供完整的记忆抽象层**：`BaseMemoryManager` + 多种实现（dummy / reme_light / adbpg / agent_md）。
- **多种后端**：本地 JSON（dummy）、ReMe 框架（light）、ADBPG（企业级 PG）、Agent MD（用户级纯文本）。
- **POC 侧暂未启用**：当前 demo 走单会话；任务 C（运营助手）会正式启用 adbpg 后端。
- **现场可演示**：在 Console 里绑定一个 Agent MD 记忆文件，让智能体记住分行名称、产品偏好；重启会话后召回。

## 2. 架构小图

```
┌──────────────────────────────────────────────────┐
│ ReActAgent (agents/react_agent.py:48)             │
│   ├ memory_manager: BaseMemoryManager             │
│   │   ├ DummyMemoryManager  (无持久化)             │
│   │   ├ ReMeLightMemoryManager  (Reme 框架, 轻量)  │
│   │   ├ ADBPGMemoryManager  (ADBPG 长期库)         │
│   │   └ AgentMDMemoryManager (用户级 HEARTBEAT.md) │
│   │                                                │
│   └ memory_tools: list[Callable]  (注入到 ToolKit) │
└──────────────────────────────────────────────────┘
        ↑
        │ list_memory_tools() 把记忆读写注册为工具
        │ Agent 通过工具调用读/写记忆
```

## 3. 真实机制（基于 QwenPaw v2.0.0 源码）

- **抽象基类**：`QwenPaw/src/qwenpaw/agents/memory/base_memory_manager.py` 定义 `BaseMemoryManager` 接口；`react_agent.py:41` `from ..agents.memory import BaseMemoryManager`。
- **Agent 集成**：`react_agent.py:71` `memory_manager: "BaseMemoryManager | None = None"`，构造时挂上。
- **工具暴露**：`react_agent.py:102-106` 通过 `memory_manager.list_memory_tools()` 拿到工具列表，注入到 toolkit，让模型能像调其他工具一样读/写记忆。
- **多种实现**（同目录）：
  - `dummy.py`——无持久化，仅进程内。
  - `reme_light_memory_manager.py` + `reme_config.py`——ReMe 框架轻量版。
  - `adbpg_memory_manager.py` + `adbpg_client.py` + `adbpg_prompts.py`——ADBPG（AnalyticDB for PostgreSQL）后端。
  - `agent_md_manager.py`——基于 HEARTBEAT.md（用户级）。
  - `proactive/`——主动记忆（不等用户问就写入）。
- **HEARTBEAT.md**：`QwenPaw/src/qwenpaw/cli/init_cmd.py` 初始化用户 working_dir 时会创建 HEARTBEAT.md，作为用户级记忆文件。

## 4. 现场演示剧本

1. 打开 QwenPaw Console → 创建新智能体，选择 Agent MD 记忆后端（最直观）。
2. 在 working_dir 下手动编辑 HEARTBEAT.md，加一行：`# 用户背景：顺德分行客户经理，关注零售业务 Q3 数据。`
3. 在智能体对话中让它"读一下 HEARTBEAT.md 然后告诉我我的关注点"。
4. 切换会话/重启 Console，再问同一问题，验证记忆召回。
5. 切到 ReMe 后端：开启 proactive 模式，让智能体主动把对话中提到的事实写入。

## 5. 常见追问

- **Q：记忆会不会"幻觉"回填？**
  A：记忆是事实存储，不会编造；但 summary 后的召回可能丢精度。
- **Q：能多用户隔离吗？**
  A：ADBPG 后端支持租户隔离；Agent MD 是 per-user 文件天然隔离。
- **Q：合规要求敏感信息不能上云怎么办？**
  A：本地后端（Dummy / Agent MD）完全离线；ReMe 可配本地模型摘要。
- **Q：POC 选了哪个？**
  A：POC Phase 2 暂未启用；任务 C（运营助手）将用 ADBPG 行方后端——等行方端点提供。

## 6. 局限性

- 跨后端切换无统一迁移工具，需要手动导出/导入。
- Proactive 模式会增加 token 消耗（每次主动写入都要调用模型）。
- Agent MD 后端无并发保护（纯文本文件），多 Agent 同写会冲突。

## 7. 待人工操作

- Console GUI 选择记忆后端、绑定 HEARTBEAT.md——GUI 操作。
- ADBPG 后端需要行方提供连接串。
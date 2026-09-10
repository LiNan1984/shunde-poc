# HARNESS 讲义 1：上下文压缩方案

> 场景：长对话上下文超过模型窗口时怎么办。
> 适用：评委问答"演示长对话会不会爆"、"几千轮工具调用怎么不超限"。

## 1. 一页要点

- **QwenPaw v2.0.0 提供两层手段**：① doom_loop 检测与截断（按工具调用参数 hash 防重复触发），② 第三方 ReMe 记忆框架（`reme_light_memory_manager`）按需把历史压缩/召回。
- **POC 侧旁路补强**：POC 暂未触发任何压缩，但所有大文件读取经 `chunk_large_workbook`（行范围分块）和 `detect_corrupt_workbook`（流式采样前 1 MiB），保证单工具返回不会拖爆上下文。
- **现场可演示**：把 `max_input_tokens` 配置调小制造溢出，再观察 doom_loop 截断生效；以及用 RemeConfig 调整记忆压缩阈值。

## 2. 架构小图

```
┌──────────────────────────────────────┐
│ Agent Loop (loop/run.py)             │
│   ↓ 收集历史 messages                 │
│ Doom-Loop Gate (gates/doom_loop.py)  │  ← 参数 hash 命中 N 次后截断
│   ↓                                   │
│ Reme Memory Manager                  │  ← 把过期消息总结、丢入 long-term store
│   ↓                                   │
│ Provider Context Window              │  ← 当前 slot 的 max_tokens
└──────────────────────────────────────┘
        ↑
        │ 旁路 POC：tools 内部就截流（chunk / 流式采样）
```

## 3. 真实机制（基于 QwenPaw v2.0.0 源码）

- **Doom-Loop 截断**：`QwenPaw/src/qwenpaw/loop/gates/doom_loop.py:228`
  > "Hash tool call args with truncation for large inputs."
  
  按工具参数 hash 计数，命中阈值后该调用被截断为简短消息，避免无限重试。
- **Provider context window**：`QwenPaw/src/qwenpaw/providers/context_windows.py` 提供每个模型 slot 的窗口大小；`config/config.py:2617` 走 `Provider.get_context_size(model_slot.model)`。
- **Reme 记忆压缩**：`QwenPaw/src/qwenpaw/agents/memory/reme_light_memory_manager.py` + `agents/memory/reme_config.py` 提供 ReMeConfig，可调 summary 阈值、召回窗口。
- **Proactive memory**：`QwenPaw/src/qwenpaw/agents/memory/proactive/`（多个模块）主动把重要事实写入长期记忆。

## 4. 现场演示剧本

1. 打开 QwenPaw Console → 当前智能体的"上下文/Token"页，确认默认 `max_input_tokens`。
2. 在配置里把 `max_input_tokens` 临时降到 1024，进入一段长对话，复现截断。
3. 切换到 Reme memory manager，开启"自动总结历史消息"，重新进入长对话，对比上下文长度。
4. POC 旁路：用 `poc/excel_guard_mcp` 故意读一个 100 MiB 的 xlsx，观察 `chunk_large_workbook` 返回结构（每块 < 5000 行），证明单次工具调用不会把大文件全塞进上下文。

## 5. 常见追问

- **Q：会不会丢关键上下文？**
  A：Doom-loop 只截断重复触发；Reme summary 阈值默认保守且可调。
- **Q：能不能完全不丢？**
  A：不行——窗口是硬上限，能做的是把"丢什么"变聪明（先丢冗余工具输出，保留用户原话和最终结论）。
- **Q：POC 用了什么？**
  A：POC 暂未启用 Reme；只用工具层 chunk + 流式采样保证单调用不会过大。
- **Q：演示时如何稳定可重现？**
  A：用一份预先生成的 100 MiB xlsx fixture（写入 `<REPO_ROOT>/poc/fixtures/`，加入 .gitignore），每次 demo 重新跑。

## 6. 局限性

- Doom-loop 只防"重复调用爆炸"，不防"每次调用都返回几 MB 数据"——后者必须靠工具内部截流（POC 已做）。
- Reme summary 是非确定性的；同一段对话两次压缩结果不会 100% 一致，demo 时不要逐字对照。

## 7. 待人工操作

- 在 Console 里实际打开/关 Reme 配置、调整 `max_input_tokens`——GUI 操作无法自动化。
- 100 MiB fixture 不入 git，需要演示前临时生成。
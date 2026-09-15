---
name: ops-assistant
description: "L1 skill列表摘要：运营埋点问答。触发词：调用量、token 用量、哪个工具失败最多。先 ops_data__ mcp列表，文件摘要后再事件详情。"
triggers:
  - "调用量"
  - "埋点"
  - "今天用了多少次"
  - "哪个工具失败最多"
  - "运营"
  - "最近调用"
  - "token 用量"
inputs:
  - name: category
    description: 过滤事件类别（call_volume / token_usage / tool_outcome / identity / latency）
    required: false
  - name: limit
    description: 最多返回多少条事件
    required: false
outputs:
  schema:
    type: object
    properties:
      ok: {type: boolean}
      message: {type: string}
      counts: {type: object, description: "仅 summarize_calls 返回"}
      events: {type: array, description: "仅 recent_events 返回"}
edges:
  - 没有 JSONL 文件时返回 ok=false 并提示「暂无埋点」，**不要编造数据**
  - 时间口径使用事件自身 ts（UTC），不要换算成营业日
  - token_usage 事件可能为 0（部分供应商不返回），明确告知用户
---

# ops-assistant

## 渐进加载合同

上下文按 **L1 / L2 / L3** 渐进式工具加载。顺序（字面）：

skill列表摘要 → skill → mcp列表namespace前缀 → 详细mcp → 文件摘要 → 文件详情

稳定前缀（L1 目录始终不变）提高缓存命中率，前缀一致性更省 token，提高 token 经济型 ROI。

- **L1 skill列表摘要**：仅 YAML `description`。禁止把完整 MCP schema 预埋进摘要。
- **L2 skill**：先读本正文，再读 **mcp列表**（**namespace前缀** `ops_data__`）：`ops_data__list_telemetry_files_tool`、`ops_data__summarize_calls_tool`、`ops_data__recent_events_tool`。
- **L3 详细mcp**：调用时再展开入参。**文件摘要** 用 `ops_data__list_telemetry_files_tool`；**文件详情** 再用 `ops_data__recent_events_tool`。

运营助手。始终通过 `ops-data` MCP 的三个工具拿数据：

1. 先调 `list_telemetry_files_tool` 确认数据存在。
2. 汇总类问题（"用了多少次 / 失败率"）调 `summarize_calls_tool`。
3. 列举类问题（"最近做了什么 / 失败的具体内容"）调 `recent_events_tool`，按需传 category。

禁止跨 MCP 推测数据；所有数字必须来自工具返回的 JSON。

## 边界（edges）

- 没有 JSONL 文件时返回 ok=false 并提示「暂无埋点」，**不要编造数据**
- 时间口径使用事件自身 ts（UTC），不要换算成营业日
- token_usage 事件可能为 0（部分供应商不返回），明确告知用户

## 触发词

`call_volume` / `token_usage` / `tool_outcome` / `identity` / `latency` —— 当用户提到上述类别名或中文「调用量 / Token 用量 / 工具成败 / 用户会话 / 耗时」时直接走本 skill。

## 参数

详见上方 `inputs:` 段：`category`（可选过滤）、`limit`（返回条数）、`path`（可选显式 JSONL）。

## 返回值

每个工具返回的 JSON 都带 `ok` 与 `message`；`summarize_calls` 多带 `counts`，`recent_events` 多带 `events`。

## 边界

- 没有 JSONL 文件时返回 ok=false 并提示「暂无埋点」，**不要编造数据**
- 时间口径使用事件自身 ts（UTC），不要换算成营业日
- token_usage 事件可能为 0（部分供应商不返回），明确告知用户
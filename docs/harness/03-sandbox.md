# HARNESS 讲义 3：沙箱方案

> 场景：智能体调 MCP 工具读/写文件时，怎么保证不会读到/写到工作目录外、不会被攻击者换包、不会失控执行危险命令。
> 适用：评委问"它会不会读到我的 ~/.ssh/"、"用户上传一个恶意 xlsx 怎么办"。

## 1. 一页要点

- **QwenPaw v2.0.0 提供两层沙箱**：① 宿主级 OS 沙箱（`src/qwenpaw/sandbox/`：bubblewrap / linux / macos / windows），隔离命令执行；② 配置级 working_dir，限制文件读写根目录。
- **POC 侧旁路沙箱**：`poc/excel_guard_mcp/guards.py` 在工具内再做一次 `_resolve_allowed_path` + `os.open(O_NOFOLLOW)` 的 fd-based 校验。
- **核心防御点**：① 拒绝 `POC_WORKSPACE=/`（fail-closed）；② 文件打开走 openat + O_NOFOLLOW 链路，杜绝 symlink swap（TOCTOU）；③ 输出路径必须以 `.docx/.png` 等白名单后缀结尾。
- **现场可演示**：构造 symlink 攻击向量和 `POC_WORKSPACE=/` 配置，让评委看到工具拒绝全过程。

## 2. 架构小图

```
┌────────────────────────────────────────────────────┐
│ QwenPaw Agent Loop                                  │
│   ↓ 工具调用 (MCP stdio)                            │
│ MCP Server (poc/excel_guard_mcp)                    │
│   ├ ① _resolve_allowed_path  ─ 校验 root 是合法目录 │
│   ├ ② lstat (不跟随 symlink)                        │
│   └ ③ _open_contained: openat(O_NOFOLLOW|O_DIRECTORY)
│              从 root fd 一层层走到 final 组件       │
│              final 用 O_RDONLY|O_NOFOLLOW             │
│              拿 fd → ZipFile(fd) / openpyxl(fd)      │
│   ↓ 返回结果                                          │
│ Agent Loop                                            │
└────────────────────────────────────────────────────┘
        ↑
        │ 宿主级 OS sandbox (bubblewrap 等) 隔离命令执行
```

## 3. 真实机制（基于 QwenPaw v2.0.0 源码 + POC 实现）

### 宿主层

- **`QwenPaw/src/qwenpaw/sandbox/`**：bubblewrap（Linux 容器化）、linux/macos/windows 各自适配。
- **`QwenPaw/src/qwenpaw/sandbox/config.py`**：沙箱配置中心（白名单命令、挂载点等）。
- **working_dir**：`QWENPAW_WORKING_DIR` 环境变量指向用户工作目录（默认 `~/.qwenpaw/`）；CLI 在该目录下创建 `config.json` 和 `HEARTBEAT.md`（`cli/init_cmd.py:184`）。

### POC 旁路层

- **`poc/excel_guard_mcp/guards.py`**：
  - `_workspace_root()` (`guards.py:68`) —— 解析 `POC_WORKSPACE`/`QWENPAW_WORKING_DIR`；**显式拒绝 `/`**（fail-closed 修复 M1）；不存在/非目录也拒绝。
  - `_resolve_allowed_path()` (`guards.py:158`) —— `Path.resolve(strict=False)` + `is_relative_to(root)`。
  - `_check_file_size()` —— 用 `lstat()`（不跟随）拿字节数，过大返回 `too_large`。
  - `_open_contained()` (`guards.py:244`) —— **fd-based openat 链路**：从 root fd 用 `O_NOFOLLOW|O_DIRECTORY` 一层层走到 final，final 用 `O_RDONLY|O_NOFOLLOW`；返回 `io.BufferedReader`。中途任何 `OSError`（包括 `ELOOP`、`EACCES`、`ENOENT`）都映射为结构化错误（`path_denied` / `missing` / `unreadable`）。
  - 输出路径（chart png / docx）同样过 `_resolve_allowed_path` 且必须以 `.png`/`.docx` 等白名单后缀结尾（见 `report_mcp/charts.py` 与 `report_mcp/docx_gen.py` 的 `_resolve_allowed_path`）。
- **`poc/report_mcp/charts.py:114` 的 `_resolve_allowed_path`**：报告输出沙箱，独立但同思路（白名单后缀 + 拒绝越界）。

## 4. 现场演示剧本

1. **fail-closed 演示**：
   ```bash
   POC_WORKSPACE=/ python -m poc.excel_guard_mcp </dev/null
   # 期望：进程能启动，但任何工具调用都返回 {"ok": false, "issue": "workspace_invalid", ...}
   ```
   验证消息明示"不能使用文件系统根目录 '/'（等于关闭沙箱）"。
2. **TOCTOU 演示**：
   ```bash
   # 在 tmp_path 下放一个真文件
   mkdir /tmp/demo_sandbox && echo "SECRET" > /tmp/secret.xlsx
   POC_WORKSPACE=/tmp/demo_sandbox python -c "
   import os; os.symlink('/tmp/secret.xlsx', '/tmp/demo_sandbox/innocent.xlsx')
   from poc.excel_guard_mcp.guards import detect_corrupt_workbook
   print(detect_corrupt_workbook('/tmp/demo_sandbox/innocent.xlsx'))
   "
   # 期望：{"ok": false, "issue": "path_denied", ...}
   ```
   symlink 换包攻击在 `O_NOFOLLOW` 下返回 ELOOP，被拒绝。
3. **日志通道演示**：
   ```bash
   POC_WORKSPACE=/tmp/demo_sandbox python -m poc.excel_guard_mcp 2>stderr.log </dev/null >stdout.log
   diff stdout.log stderr.log
   # 期望：stdout 为空（只发 MCP JSON-RPC），stderr 含 "sandbox workspace root active: ..."
   ```
   验证 stdout 协议通道不被污染（红线 4）。
4. **攻击回归套件**：
   ```bash
   pytest poc/tests/test_security_regressions.py -v
   # 期望：8 passed（symlink 三种 + sandbox 三种 + MemoryError 审计）
   ```

## 5. 常见追问

- **Q：宿主层 sandbox 已经隔离了，为什么 POC 还要再做？**
  A：宿主 sandbox 主要隔离命令执行（subprocess / bash），不约束 MCP 工具自身的文件 I/O；旁路沙箱是工具侧最后一道。
- **Q：能不能用容器（Docker）替代？**
  A：可叠加；行方给容器后，工具侧仍应保留（防御纵深）。
- **Q：`O_NOFOLLOW` 在 macOS 上行为一致吗？**
  A：是（BSD 起源，macOS 与 Linux 都支持）；但中间路径段若有 symlink，必须靠 openat+O_NOFOLLOW+O_DIRECTORY 链路处理，单纯顶层 O_NOFOLLOW 不够——见 `_open_contained` 设计。
- **Q：用户传一个 `../../../etc/passwd` 怎么办？**
  A：`Path.resolve()` 解析后 `is_relative_to(root)` 校验，越界即 `path_denied`。
- **Q：超大文件怎么防？**
  A：`_check_file_size()` 用 `POC_EXCEL_MAX_BYTES`（默认几 MiB）阈值；超限返回 `too_large`，不让 `openpyxl` 读入内存爆炸。

## 6. 局限性

- 工具侧白名单只校验扩展名，不校验 MIME——攻击者可把 `.docx` 内容写成任意字节。openpyxl/python-docx 会拒绝解析，但已耗 IO。
- 进程内单根沙箱，无法跨进程共享约束——每个 MCP 子进程需独立设环境变量。
- `POC_WORKSPACE` 是单一根；多租户场景需要每个会话独立根（任务 C 涉及）。

## 7. 待人工操作

- 宿主的 `QWENPAW_WORKING_DIR` 在 Console GUI 里配置——GUI 操作。
- bubblewrap sandbox 需要 Linux 容器运行时；macOS/Windows 用平台适配版本（功能等价但非完全相同）。
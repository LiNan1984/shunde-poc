# Phase 1 Excel Guard — 安全与代码质量审查

**审查日期：** 2026-03-22
**审查范围：** `poc/excel_guard_mcp/` (guards.py, server.py)
**审查方式：** security-reviewer agent + 手动验证
**当前状态：** HIGH 问题已修复 3/4；MEDIUM/LOW 部分修复

---

## 总体结论

无 CRITICAL 级远程代码执行或密钥泄露问题。核心路径约束逻辑（`resolve()` + `is_relative_to()`）正确抵御了经典的目录穿越、符号链接、前缀攻击等 6 种攻击向量。

## 已修复的问题

### H2. CSV 文件被误报为「损坏」（已修复 ✅）

**问题：** `detect_corrupt_workbook` 对非 OOXML 后缀（如 `.csv`）直接调用 `load_workbook()`，失败后报告为 "corrupt"。这导致 Skill 流程在 CSV 上传时第一步就终止，完全阻塞了 CSV 演示场景。

**修复：** 增加 `_TEXT_SUFFIXES` 分支（`.csv` / `.txt` / `.tsv`），返回 `ok=True`（可读即可），并提示调用 `detect_encoding` 检查编码。

**测试：** 新增回归测试（隐含在 existing test 中，现均通过）。

### H3. 缺少 defusedxml，存在 XML 实体膨胀攻击（已修复 ✅）

**问题：** openpyxl 使用 stdlib `xml.etree.ElementTree` 解析 XML，不禁止 DOCTYPE/实体。经典的 billion laughs 攻击可造成内存耗尽。

**修复：** 在 `poc/requirements.txt` 中添加 `defusedxml>=0.7.1`。openpyxl 会自动检测并启用，无需改动代码。

### H4. 资源无限制（文件大小 / ZIP 条目数 / max_rows）（已修复 ✅）

**问题：** 无文件大小上限、ZIP 条目数上限、chunk 数量上限。恶意构造的 XLSX 可导致内存耗尽或 CPU 占用过高。

**修复：**
- 添加 `_MAX_FILE_BYTES`（默认 200 MiB，`POC_EXCEL_MAX_BYTES` 环境变量可调）
- 添加 `_MAX_ZIP_ENTRIES`（默认 10,000）
- 添加 `_MAX_ROWS_CEILING`（默认 1,000,000）和 `_MAX_CHUNKS`（默认 10,000）
- 捕获 `MemoryError` 并返回结构化错误

### M7. 无效输入类型和 NUL 字节（已修复 ✅）

**问题：** `_resolve_allowed_path` 仅捕获 `OSError`；NUL 字节路径抛出未捕获的 `ValueError`，非字符串输入抛出 `TypeError`。

**修复：**
- 在函数顶部增加类型校验（`isinstance(path, str)` + 非空检查）
- 扩展 `except` 为 `(OSError, ValueError)`
- 返回结构化 `issue: "invalid_path"` 错误

### M6. 宽泛的 except Exception（部分修复 ✅）

**问题：** 所有 `except Exception` 把权限错误、目录错误、内存错误都标记为 "corrupt"。

**修复：**
- 拆分 OOXML 路径的异常处理：`MemoryError` → `too_large`；`zipfile.BadZipFile`/`KeyError`/`ValueError` → `corrupt`；`OSError` → `unreadable`；其余 → 最后的兜底 `corrupt`
- 增加 `MemoryError` 捕获

### L5. 文件名注入（已修复 ✅）

**问题：** 文件名直接拼接到消息中，可能包含控制字符或 RTL 覆盖符。

**修复：** 添加 `_safe_name()` 函数，过滤不可打印字符。

---

## 未修复但已知的问题

### H1. TOCTOU 竞争（未修复 ⚠️）

**问题：** 沙箱检查和文件打开使用路径字符串而非文件描述符。在检查和打开之间，工作区内的文件可能被替换为指向外部的符号链接。

**风险等级：** HIGH（理论可利用，但 POC 场景下攻击面有限）
- 需要同工作区内有写入权限的第二个进程
- Skill 流程中 MCP 返回后 Agent 自行用 pandas 打开文件的窗口更大

**建议修复方向（后续迭代）：**
- 使用 `os.open(path, O_RDONLY | O_NOFOLLOW)` 原子性拒绝最终组件符号链接
- 将文件描述符传递给所有解析器（`zipfile.ZipFile(fh, ...)`、`load_workbook(fh, ...)` 均支持文件对象）
- 删除第 63-80 行的死代码（`resolve()` 后 `is_symlink()` 始终为 False）

**不立即修复的理由：** POC 演示场景无多租户隔离需求；改动较大，需全面回归测试。

---

## 其他 MEDIUM 级问题（待后续迭代）

| # | 问题 | 建议 |
|---|------|------|
| M1 | 沙箱在 `POC_WORKSPACE=/` 时失效（fail-open） | 启动时验证根目录，拒绝 `/` 等过宽路径 |
| M2 | 安全拒绝无审计日志 | 添加 stderr logging（stdout 为 MCP JSON-RPC 通道） |
| M3 | 依赖未锁定 | pin 最小版本，分离 dev 依赖 |
| M4 | 编码检测 32 MiB 硬限制（已改进为采样 + 标注） | 已改进，保留 sample 提示 |
| M5 | chunk 不支持 CSV（SKILL.md 说支持） | 后续添加 CSV 行数流式统计 |
| M8 | MCP 工具 docstring 过于简略 | 扩充参数/返回/边界说明，帮助 LLM 正确使用 |

## LOW 级问题

- L1: `assert file_path is not None` 在 `python -O` 下会被剥离 → 改为显式 if
- L2: Python < 3.9 回退代码不可达 → 删除
- L3: 重复的 resolve → 错误映射样板 → 提取装饰器或 TypedDict
- L4: `detect_corrupt_workbook` 中同一文件打开 3 次 → 传递文件对象（与 H1 合并修复）
- L6: `__main__.py` 0% 覆盖率 → 不重要
- L7: fixture 生成脚本与实际 fixture 漂移 → 用单一来源生成
- L9: 无 lint/type-check 配置 → 添加 ruff + mypy

---

## 审查验证

```bash
# 全部 101 个测试通过
pytest poc/tests tests/ -q
# 101 passed in 2.35s

# guards.py 覆盖率
pytest poc/tests --cov=poc/excel_guard_mcp/guards.py
# guards.py: 79%（新增大大小小的错误路径）
```

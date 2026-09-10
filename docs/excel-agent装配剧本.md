# Excel 问答智能体 — QwenPaw Console 装配剧本（场景 ①）

> 目标：在 QwenPaw **v2.0.0** Console 里从零配出一个能完成 [excel-12题标准答卷.md](excel-12题标准答卷.md) 中
> Q1–Q12 + Y1–Y3 的智能体：挂载 `excel-guard` MCP（3 工具）+ `excel-qa-bank` Skill。
> 全部配置只用 `<REPO_ROOT>` 占位符；正式填写时替换为本机仓库根目录的**绝对路径**。
> 本文不包含、也不允许在任何配置文件中写入 Bearer / API Key（密钥只走环境变量或 `QWENPAW_SECRET_DIR`）。

---

## 0. 装配拓扑

```
QwenPaw Console 智能体（模型走行方口径 Qwen3.6 系列，密钥由平台注入）
        │
        ├── Skill：excel-qa-bank（poc/skills/excel-qa-bank/SKILL.md）
        │     └─ 规定答题流程：先调 MCP 三工具做闸门，再 pandas/openpyxl 读查析写
        │
        └── MCP client：excel-guard（stdio 子进程）
              command: <REPO_ROOT>/.venv/bin/python -m poc.excel_guard_mcp
              cwd:     <REPO_ROOT>
              env:     POC_WORKSPACE=<REPO_ROOT>   ← 文件系统沙箱根
                    │
                    ├─ detect_corrupt_workbook(path)
                    ├─ detect_encoding(path)
                    └─ chunk_large_workbook(path, max_rows=5000)
```

关键点：MCP 是**无状态 stdio 子进程**，只能读写 `POC_WORKSPACE` 目录树内的文件；
所以演示用的 xlsx/csv 必须放在 `<REPO_ROOT>` 之内（仓库内即 `poc/fixtures/`）。

---

## 1. 前置准备（命令行，约 10 分钟）

```bash
cd <REPO_ROOT>
git -C QwenPaw describe --tags --exact-match   # 期望 v2.0.0；目录缺失则：
                                               # gh repo clone agentscope-ai/QwenPaw -- --branch v2.0.0
source .venv/bin/activate                      # 必须用仓库 venv（系统 Python 无依赖）
uv pip install -r poc/requirements.txt
pytest poc/tests tests/ -q                     # 期望 101 passed
python -m poc.excel_guard_mcp </dev/null       # 期望 exit code 0（stdio 进程遇 EOF 干净退出）
```

确认 fixture 在位：`poc/fixtures/corrupt.xlsx`、`encoding_gbk.csv`、`encoding_latin1.csv`、
`large_chunk_demo.xlsx`。答卷中 F1–F6 的补造数据见答卷 §6（**人工补造，全部合成数据**）。

---

## 2. 挂载 MCP：excel-guard

### 2.1 Console 导入（推荐， poc/README 记载的路径）

1. 打开 QwenPaw Console → **智能体 → MCP**；
2. 点击 **+ 创建**；
3. 粘贴下面 JSON 全文（即仓库内 `poc/config/mcp-excel-guard.json`，`mcpServers` 形态 Console 可直接接收）；
4. **把两处 `<REPO_ROOT>` 全部替换成本机绝对路径**后保存；
5. 保存后在 MCP 列表确认 client `excel-guard` 状态为启用/已连接，展开工具列表应看到且仅有三个工具：
   `detect_corrupt_workbook`、`detect_encoding`、`chunk_large_workbook`。

```json
{
  "mcpServers": {
    "excel-guard": {
      "command": "<REPO_ROOT>/.venv/bin/python",
      "args": ["-m", "poc.excel_guard_mcp"],
      "cwd": "<REPO_ROOT>",
      "env": {
        "POC_WORKSPACE": "<REPO_ROOT>"
      }
    }
  }
}
```

### 2.2 备选：直接写 QwenPaw config.json（Console 导入不顺时用）

QwenPaw v2.0.0 原生配置形态是 `mcp.clients` 字典（键为 client 名），
配置文件在 `$QWENPAW_WORKING_DIR/config.json`（默认 `~/.qwenpaw/config.json`）：

```json
{
  "mcp": {
    "clients": {
      "excel-guard": {
        "name": "excel-guard",
        "description": "Excel 损坏/编码/超大分块检测（顺德 POC）",
        "enabled": true,
        "transport": "stdio",
        "command": "<REPO_ROOT>/.venv/bin/python",
        "args": ["-m", "poc.excel_guard_mcp"],
        "cwd": "<REPO_ROOT>",
        "env": {
          "POC_WORKSPACE": "<REPO_ROOT>"
        },
        "tools": [
          "detect_corrupt_workbook",
          "detect_encoding",
          "chunk_large_workbook"
        ]
      }
    }
  }
}
```

字段语义（v2.0.0 源码）：stdio 必须有非空 `command`；`tools` 是白名单（可省略表示全量加载）；
改完配置重启 QwenPaw 服务/刷新 Console 使 client 拉起。

### 2.3 挂载验证（不依赖 Console）

任一方式配完后，可先用仓库自带测试确认子进程行为没被配置破坏：

```bash
cd <REPO_ROOT> && source .venv/bin/activate
pytest poc/tests/test_mcp_server.py -q      # 32 个 MCP 集成测试全绿
```

Console 内验证话术见 §5 的 Y1（工具真的被智能体调到才算挂成功）。

---

## 3. 挂载 Skill：excel-qa-bank

### 方式 A：外部 skill_paths（推荐，不复制文件）

编辑 `$QWENPAW_WORKING_DIR/config.json`（默认 `~/.qwenpaw/config.json`），加入：

```json
{
  "skill_paths": ["<REPO_ROOT>/poc/skills"]
}
```

重启/刷新后，Console **技能池**中应出现 `excel-qa-bank`（目录下还有 `report-visualizer`，属场景④，本场景不用可不下发）。

### 方式 B：复制进技能池

```bash
cp -R <REPO_ROOT>/poc/skills/excel-qa-bank \
  "$QWENPAW_WORKING_DIR/skill_pool/excel-qa-bank"
```

### 下发到智能体

在 Console 进入目标智能体的**工作区 → 技能**，从技能池把 `excel-qa-bank` **下发/广播**给该智能体；
打开技能详情应能看到 SKILL.md 的名称、触发词（excel问答 / 表格分析 / xlsx / csv查询 等）。

---

## 4. 创建并调教智能体

1. Console → **智能体 → 新建**，命名如"Excel 文件问答助手（POC）"。
2. 模型选择行方口径模型（POC 文件要求 Qwen3.6-35B / Qwen3.6-27B；演示前确认现场实际可用模型 ID）。
   **密钥不在本剧本配置**——由 QwenPaw 平台的 provider 配置 / 环境变量 / `QWENPAW_SECRET_DIR` 注入。
3. 能力勾选：启用 MCP `excel-guard`；启用技能 `excel-qa-bank`；保证智能体具备代码执行（pandas/openpyxl 读查析写）能力。
4. 系统提示词粘贴以下模板（护栏顺序是硬性要求）：

```text
你是顺德农商银行 POC 的 Excel/CSV 文件问答助手。回答任何表格问题时必须遵守：

1. 拿到文件后，先依次调用 MCP excel-guard：
   (1) detect_corrupt_workbook(path)：ok=false 时，原样把 message 转述给用户并停止，绝不强行打开；
   (2) CSV/文本文件必须再调 detect_encoding(path)，按返回的 encoding/confidence 选择读取编码，
       置信度低时按 gb18030→gbk→latin-1 候选尝试，禁止默认 UTF-8 硬读；
   (3) 调 chunk_large_workbook(path, max_rows=5000)：needs_chunking=true 时严格按返回的 chunks
       （start_row/end_row/sheet，行号含表头）分块读取、逐块聚合，并做行数闭合校验。
2. 大 CSV 不能用 chunk_large_workbook（它只支持 xlsx，会返回 InvalidFileException），
   改用 pandas read_csv(chunksize=5000) 流式处理，并向用户说明。
3. 读查析写优先 pandas；需要保留公式/格式时用 openpyxl。所有读写只允许在工作区目录内；
   写回一律生成新文件、不覆盖用户原文件，并在答复中给出输出路径。
4. 数字类答案给出可复算的口径（筛选条件、合计式、占比公式）；查无结果明说，禁止编造单元格内容。
5. 支持多轮对话：用户追问时复用上一轮的筛选结果与口径，不要求用户重复条件。
```

5. 保存并新建一个会话，确认工具面板里能看到三个 MCP 工具、技能状态为已启用。

---

## 5. 逐类型验证话术（装配完成后的冒烟测试）

把 F1（`bank_transactions.xlsx`，待造）与现有 fixture 放到 `poc/fixtures/` 后，逐题在会话里发下面的话术。
判据列用于现场快速判定"装配成功"。

| 题 | 类型 | 验证话术（直接发） | 通过判据 |
|---|---|---|---|
| Q1 | 读取 | "poc/fixtures/bank_transactions.xlsx 里有几张表？各多少行多少列、表头是什么？" | 答出 2 sheet、行列数、列名；工具面板可见先调了 detect_corrupt_workbook |
| Q2 | 读取 | "把 2026 年 1 月转账汇出的前 20 笔，只列日期、对方户名、借方金额" | ≤20 行三列表，不足 20 笔有说明 |
| Q3 | 读取/编码 | "poc/fixtures/bank_branch_gbk.csv 里有哪些支行？"（GBK 文件，F2） | 中文无乱码；先出现 detect_encoding 调用并说明按何种编码读取 |
| Q4 | 查询 | "容桂支行 3 月金额超过 5 万的转账汇出有哪几笔？" | 多条件筛选结果 + 笔数 + 合计 |
| Q5 | 多轮 | 不重发文件直接追问："里面最大的三笔？这三笔占当月该支行转账汇出的百分之多少？" | 复用上一轮条件，给出三笔、合计、占比计算式 |
| Q6 | 查询/跨表 | "客户号 C0017 是谁？开户网点、等级、交易笔数和总金额？" | 关联两表；借贷金额分开列 |
| Q7 | 分析 | "按交易类型汇总笔数、发生额和占比" | 六类齐全、笔数合计=总行数、占比≈100% 且有口径 |
| Q8 | 分析 | "按月看转账汇出趋势，哪个月最高、月均多少？工作日和周末笔数对比？" | 月合计/均值/最高月 + 工作日周末计数 |
| Q9 | 分块分析 | "poc/fixtures/large_chunk_demo.xlsx 的 amount 总和和均值，分块算给我看" | chunk 返回两块（1–5000/5001–6001）；答案 **sum=189,031,500、mean=31,505.25、count=6000**；有 4999+1001 闭合校验 |
| Q10 | 写入 | "把刚才那几笔大额转账导成新 xlsx" | 给出工作区内新文件路径；原文件未改动；新文件内容笔数一致 |
| Q11 | 写入 | "给流水加一列'大额标记'，借方超 5 万标是否则否，另存一份" | 新文件列数 +1、行数不变；"是"笔数与 Q4 一致 |
| Q12 | 写入 | "生成含'明细'和'网点汇总'两个 sheet 的新工作簿" | 两 sheet；网点笔数合计=明细总行数 |
| Y1 | 损坏护栏 | "帮我分析 poc/fixtures/corrupt.xlsx" | 逐字返回 issue=corrupt 提示（不是有效 ZIP 包…重新导出或修复）并**停止**，没有后续读取 |
| Y2 | 编码护栏 | "读一下 poc/fixtures/encoding_gbk.csv" | 先报 detect_encoding 结果（gb18030 低置信度提示），再按候选编码读出"姓名,城市/张三,北京"无乱码 |
| Y3 | 超大护栏 | "poc/fixtures/large_chunk_demo.xlsx 行数超 5000 了吗？怎么分块？" | needs_chunking=true、2 个分块范围、message 含"已生成 2 个分块范围" |

补测（可选，30 秒）：传一个不存在的路径 → "文件不存在 / File not found…"；
传工作区外路径 → "路径越界 / Path outside workspace…"；把一个 `.xls` 文件放进去 →
"旧版 Excel 格式不支持…请另存为 .xlsx 后再试"。三种文案与答卷 §4.x 完全一致即合格。

---

## 6. 故障排查

| 现象 | 排查 |
|---|---|
| MCP 列表里没有 excel-guard / 连接失败 | 先在终端跑 `python -m poc.excel_guard_mcp </dev/null`，期望 exit 0；检查 JSON 里 `<REPO_ROOT>` 是否三处全替换（command/cwd/POC_WORKSPACE）、venv 路径是否存在 |
| 工具只有 0 个 | 子进程启动即崩：Console 详情/日志看 stderr（stdout 是 MCP JSON-RPC 通道，任何日志污染都会导致握手失败；本项目日志只走 stderr） |
| 任何文件都报"路径越界 / Path outside workspace" | 文件不在 `POC_WORKSPACE` 指向的目录树内；把演示文件移到 `<REPO_ROOT>/poc/fixtures/`，或把 POC_WORKSPACE 改成共同父目录后重启 MCP |
| 技能池里看不到 excel-qa-bank | 确认 config.json 的 `skill_paths` 是 **poc/skills 目录**（不是技能子目录本身）；重启/刷新；或改用方式 B 复制到 skill_pool |
| 智能体不先调 MCP 直接读文件 | 系统提示词未生效或未启用技能：重贴 §4 模板，确认技能已下发到该智能体工作区 |
| 对 CSV 调分块返回 InvalidFileException | 这是代码真实行为（分块工具仅支持 xlsx）；按提示词第 2 条改用 pandas `chunksize`，不是 bug，现场应主动解释 |
| GBK 文件检测置信度只有 0.1x | chardet 短样本已知特性；低置信度提示本身就是正确产品行为，按 gb18030 候选读取即可，不要"修"检测器 |
| 改了配置不生效 | 重启 QwenPaw 服务；MCP client 是启动时拉起的 stdio 子进程，不热加载 |

---

## 7. 留给人工操作的步骤（agent 无法代办）

1. 在 QwenPaw Console UI 中完成点击操作：新建 MCP、新建智能体、下发技能、勾选工具（§2.1、§3、§4），
   并把模板中 `<REPO_ROOT>` 手工替换为本机绝对路径（替换后的配置含本机路径，**不要提交进 git**）。
2. 配置模型 provider 与密钥（环境变量 / `QWENPAW_SECRET_DIR`），确认现场可用的 Qwen3.6 模型 ID。
3. 按答卷 §6 补造 F1–F6 fixture（合成数据；其中 F1 是 9 道题的共用数据，优先造）。
4. 演示前 3 个工作日行方真题与数据到达后，按答卷 §7 SOP 替换题面/数据/期望数字并预跑留截图。
5. 现场冒烟：照 §5 把 15 条话术跑一遍，保存工具调用轨迹与答案截图，作为用例 1-1/1-2 的测试报告附件。
6. 演示用机若与开发机不同，重跑 §1 四条命令并重新替换占位路径。

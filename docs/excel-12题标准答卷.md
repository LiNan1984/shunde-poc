# Excel 文件问答 — 12 题标准答卷（POC 场景 ①，用例 1-1 / 1-2 / 1-3）

> 对应需求：《人工智能场景拓展与迭代开发技术服务项目-POC选型方案》中"现场演示内容 → EXCEL文件问答助手"
> 配套文档：[excel-agent装配剧本.md](excel-agent装配剧本.md)
> 代码基线：`poc/excel_guard_mcp/`（MCP `excel-guard`，3 工具）+ `poc/skills/excel-qa-bank/SKILL.md`
> 原则：文档与代码冲突时以代码为准；本卷全部工具名、参数、返回 key、issue 码与提示文案均已对照
> `poc/excel_guard_mcp/guards.py`、`server.py` 实测核对。

---

## 0. 关于"12 道题"的重要说明（先读）

从需求 docx 全文（正文段落 + 全部 13 个表格）抽取的结果是：

- **docx 中并没有列出 12 道题的具体题面**。用例 1-1 只写了"提供12个测试问题，涉及文件的读取、查询、分析、写入方面的问题"，
  且"主要演示流程"明确：*测试问题集在演示前 3 个工作日才由行方下发*，供应商需提前跑出结果。
- docx 对本场景的硬性要求只有三条：
  1. **用例 1-1（EXCEL文件问答能力）**：准确理解意图、支持**多轮对话上下文**，准确回答 12 个问题，覆盖**读取、查询、分析、写入**四类；
  2. **用例 1-2（MCP开发）**：现场给三种异常文件 —— **文件损坏检测、编码自动识别、超大文件分块处理**，返回正确提示；
  3. **用例 1-3（SKILL开发）**：SKILL 文档五要素 —— 名称/描述/触发词/参数/返回值，且触发条件明确、输入输出规范、边界清晰（已由
     `poc/skills/excel-qa-bank/SKILL.md` 满足，并有测试强制）。

因此本卷做法：**按 docx 的四类覆盖面 + 多轮上下文要求，自拟 12 道预置模拟题（Q1–Q12，银行流水业务口径）**，每题给出可直接照演的
标准答卷；行方真题到达后，按同一模板逐题替换题面与期望答案即可，MCP 调用顺序与护栏部分不需要改。用例 1-2 的三道异常题
（Y1–Y3）是 docx 明确要现场测的，单列一章，并附其余护栏分支矩阵。

题类分布：读取 Q1–Q3 ｜ 查询 Q4–Q6（Q5 为多轮追问）｜ 分析 Q7–Q9（Q9 为超大分块）｜ 写入 Q10–Q12。

---

## 1. 工具事实卡（答卷共用，以代码为准）

### 1.1 三个 MCP 工具（server 名 `excel-guard`，stdio）

| 工具名（真实注册名） | 入参 | 成功/关键返回 key | 说明 |
|---|---|---|---|
| `detect_corrupt_workbook` | `path: string`（必填） | `ok` / `issue` / `message` | 损坏与格式闸门。`.csv/.txt/.tsv` 只要可读即 `ok=true`（编码不归它管）；`.xls/.xla/.xlt` 与未知后缀返回 `unsupported` |
| `detect_encoding` | `path: string`（必填） | `encoding` / `confidence` / `message` | chardet 检测，**只读前 1 MiB 采样**；xlsx 返回 `encoding=utf-8`（有效 ZIP 时 `confidence=1.0`）；空文件返回 `utf-8`、`confidence=0.0` |
| `chunk_large_workbook` | `path: string`（必填），`max_rows: integer = 5000`（选填，1–1,000,000） | `needs_chunking` / `total_rows` / `max_sheet_rows` / `chunks[]`（每块 `start_row`/`end_row`/`sheet`，**Excel 行号，含表头行**）/ `message` | 取所有工作表中最大行数判断；`chunks` 连续不重不漏覆盖超限工作表 |

### 1.2 issue 码与触发条件（`detect_corrupt_workbook`）

| issue 码 | 触发条件（代码实测） |
|---|---|
| `corrupt` | 不是 ZIP 包；ZIP 内缺 `[Content_Types].xml`；openpyxl 打开抛 `BadZipFile/KeyError/ValueError` 或其他异常 |
| `unsupported` | 后缀为 `.xls/.xla/.xlt`（旧版 BIFF），或任何未识别后缀 |
| `too_large` | 文件字节数超过 `POC_EXCEL_MAX_BYTES`（默认 **200 MiB**）；或解析时 `MemoryError` |
| `unsafe_archive` | ZIP 条目数超过 `POC_EXCEL_MAX_ZIP_ENTRIES`（默认 **10,000**，防 zip bomb） |
| `missing` | 文件不存在 |
| `invalid_path` | 入参非字符串/空串；路径是目录 |
| `path_denied` | 解析后不在沙箱根内（含越界符号链接） |
| `unreadable` | stat/读取时 `OSError` |

另两个工具的异常形态不同（下游兼容约束，勿改名）：

- `detect_encoding` 异常时返回 `encoding="unknown", confidence=0.0` + 双语 message（**没有 issue 字段**）；
- `chunk_large_workbook` 异常时返回 `needs_chunking=false, total_rows=0, chunks=[]` + message；
  文件超限时 message 直接是 `too_large` 的那句中文文案。

### 1.3 必须照实告知演示人员的三条边界

1. **`chunk_large_workbook` 目前只支持 xlsx 系（`.xlsx/.xlsm/.xltx/.xltm`）**。对 CSV 调用会返回
   `needs_chunking=false`、message=`无法打开工作簿做分块 / Cannot open workbook for chunking: InvalidFileException`。
   超大 CSV 的正确答法是 agent 直接用 `pandas.read_csv(..., chunksize=...)` 流式读（这是已知缺口，不在本任务改代码）。
2. **chardet 对短样本不可靠**：现有 `encoding_gbk.csv`（20 字节）实测报 `gb18030, confidence=0.12`，
   `encoding_latin1.csv` 报 `windows-1252, confidence=0.03` —— 走的是"编码置信度偏低"提示分支；
   只有 **UTF-16 实测稳定 1.00**。演示高置信度转码要造 UTF-16 文件（见 fixture 清单 F5）。
3. **所有路径必须在沙箱内**：MCP 进程靠 `POC_WORKSPACE`（兜底 `QWENPAW_WORKING_DIR`）圈定可读根，
   越界一律 `path_denied`。演示文件必须放在工作区（配置中 `POC_WORKSPACE=<REPO_ROOT>`，即用仓库根）内。

---

## 2. 业务样例数据约定（Q1–Q12 共用）

除已标注"用现有 fixture"的题目外，Q1–Q8、Q10–Q12 围绕一份**需补造**的合成工作簿
`poc/fixtures/bank_transactions.xlsx`（全部虚构数据，禁止真实客户信息）：

- Sheet `交易流水`（建议 300+ 行，2026-01～2026-03），列：
  `交易流水号, 交易日期, 客户号, 客户名称, 账号, 对方户名, 对方账号, 网点编号, 网点名称, 交易类型, 借方金额, 贷方金额, 余额, 摘要, 渠道`
  - `交易类型` 取值：现金存入、现金支取、转账汇入、转账汇出、消费、还款；
  - `渠道` 取值：柜面、手机银行、网上银行、ATM、POS；
  - 网点 5～8 个（如"总行营业部""容桂支行""大良支行"等本地化名），含至少 10 笔金额 > 50,000 的转账汇出。
- Sheet `客户信息`（30 行），列：
  `客户号, 客户名称, 证件类型, 证件号后4位, 手机号, 开户网点编号, 客户等级, 开户日期`（手机号/证件号一律合成假值）。

每题"MCP 调用顺序"中 path 一律写相对工作区路径（如 `poc/fixtures/bank_transactions.xlsx`），实际由 agent 拼工作区根。

---

## 3. Q1–Q12 标准答卷

### Q1（读取·结构概览）

- **题面（模拟）**："这个 Excel 里有几张表？每张表多少行、多少列？表头分别是什么？数据从什么时候到什么时候？"
- **考点**：基础读取、多 sheet 枚举、列名与日期范围。
- **样例输入**：`poc/fixtures/bank_transactions.xlsx`（**待造 F1**）。
- **调用顺序**：
  1. `detect_corrupt_workbook({"path": "poc/fixtures/bank_transactions.xlsx"})` → 期望 `ok=true, issue=""`，message"工作簿正常 / Workbook OK"。
  2. xlsx 无需编码检测（若调 `detect_encoding`，返回 utf-8/1.0 的 ZIP 说明，不影响）。
  3. `chunk_large_workbook({"path": "...", "max_rows": 5000})` → 期望 `needs_chunking=false`（300 行小表）。
  4. Skill 分析：`pd.read_excel(path, sheet_name=None)` 得 dict；逐 sheet 报 `df.shape`、`list(df.columns)`；
     对"交易日期"列 `min()/max()`。
- **答案要点**：2 张表；`交易流水` 行列数与 15 个列名、`客户信息` 行列数与 8 个列名；日期范围 2026-01-xx～2026-03-xx。
- **护栏**：若第 1 步 `ok=false`，原样转述 `message` 并停止，不得继续读。

### Q2（读取·定点取数）

- **题面（模拟）**："把交易流水里 2026 年 1 月'转账汇出'的前 20 笔，只给我日期、对方户名、借方金额三列。"
- **考点**：条件过滤 + 列裁剪 + 行限量；答案以表格呈现。
- **样例输入**：F1。
- **调用顺序**：corrupt 检查 → chunk（无需分块）→ Skill：
  `df[(df.交易日期.dt.month==1) & (df.交易类型=="转账汇出")][["交易日期","对方户名","借方金额"]].head(20)`。
- **答案要点**：≤20 行三列表；行数、每笔金额与文件一致；若不足 20 笔要明说"1 月转账汇出共 N 笔，全部列出"。
- **护栏**：无（小表正常路径）。

### Q3（读取·CSV 编码）

- **题面（模拟）**："这份网点名单 CSV 帮我读出来，把所有支行名称列一下。"（文件为 **GBK 编码**）
- **考点**：CSV 必走 `detect_encoding`；按识别编码读取，不乱码、不硬按 UTF-8 读。
- **样例输入**：**待造 F2** `poc/fixtures/bank_branch_gbk.csv`（GBK 编码、含中文网点名、几百字节，
  不要用现有的 `encoding_gbk.csv`，它只有 20 字节，仅够演示护栏提示、不够答题）。
- **调用顺序**：
  1. `detect_corrupt_workbook({"path": "...bank_branch_gbk.csv"})` → `ok=true`，message"文本文件可读…建议调用 detect_encoding 确认编码"。
  2. `detect_encoding({"path": "...bank_branch_gbk.csv"})` → 中文 GBK 样本实测可能为 `gb18030/gbk`，
     `confidence` 可能 < 0.5，message 为"**编码置信度偏低**…建议按 latin-1/gbk 尝试转码…勿直接当 UTF-8 打开"。
  3. Skill 处理：以候选编码链 `["gb18030", "gbk", "utf-8"]` 依次尝试 `pd.read_csv(path, encoding=enc)`，
     gb18030 是 GBK 超集，一次成功；回答后附一句"文件为 GBK 系列编码，已按 gb18030 读取"。
- **答案要点**：支行名称中文无乱码；数量与文件行数一致。
- **护栏**：禁止跳过第 2 步直接 UTF-8 硬读（会抛 UnicodeDecodeError 或出乱码）；低置信度不是错误，是"换候选编码尝试"的信号。

### Q4（查询·多维筛选）

- **题面（模拟）**："查一下容桂支行 3 月份金额超过 5 万块的转账汇出有哪几笔？"
- **考点**：多条件（网点 + 月份 + 类型 + 金额阈值）筛选。
- **样例输入**：F1。
- **调用顺序**：corrupt → chunk（无需）→ Skill：
  `df[(df.网点名称=="容桂支行") & (df.交易日期.dt.month==3) & (df.交易类型=="转账汇出") & (df.借方金额>50000)]`。
- **答案要点**：列出流水号/日期/对方户名/金额，给出笔数与金额合计；阈值"超过 5 万"按 `>50000`（不含等于），口径要说清。
- **护栏**：无。

### Q5（查询·多轮上下文，docx 明确考点）

- **接续 Q4 的追问（同一会话，不重发文件、不重复条件）**：
  - 追问 a："这里面金额最大的三笔是哪三笔？"
  - 追问 b："这三笔一共多少钱？占 3 月容桂支行全部转账汇出的百分之多少？"
- **考点**：**多轮对话上下文**——agent 必须复用上一轮筛选结果与口径，不能要求用户重述条件；分母取同网点同类型当月全量。
- **样例输入**：F1（沿用 Q4 会话状态）。
- **调用顺序**：不重复 MCP 检测（同文件本会话已检；若 agent 框架无状态则可幂等再调，三工具均无状态、重复调用结果一致）；
  在 Q4 结果集上 `nlargest(3,"借方金额")`；分母重新按同口径筛选求和，算占比。
- **答案要点**：三笔排序与金额；三笔合计；占比给出计算式（分子/分母=百分比，保留 2 位小数）。
- **护栏**：若上下文丢失（新会话），应主动用一句话复述理解的条件再算，不能换口径。

### Q6（查询·跨表关联，VLOOKUP 语义）

- **题面（模拟）**："客户号 C0017 是谁？他的开户网点和等级是什么？一共发生过几笔交易、总金额多少？"
- **考点**：两 sheet 关联（等价 VLOOKUP）+ 客户级聚合；借贷口径。
- **样例输入**：F1。
- **调用顺序**：corrupt → chunk（无需）→ Skill：`read_excel(sheet_name=None)` 取两表；
  `客户信息[客户号=="C0017"]` 取名称/开户网点/等级；流水按客户号过滤后 `shape[0]` 计笔数，
  金额按交易方向分别合计**借方、贷方**（不要把借贷混加），再按题意汇报。
- **答案要点**：客户名称、开户网点、客户等级与客户信息表一致；笔数；借方/贷方金额分开列示并给口径说明。
- **护栏**：客户号不存在时回答"未找到客户号 Cxxxx，请核对"，不得编造。

### Q7（分析·分组聚合）

- **题面（模拟）**："按交易类型汇总一下：每种类型多少笔、总金额、占全部发生额的比例，画成文字表格。"
- **考点**：groupby 聚合 + 占比；金额口径（按借贷方向分列或统一取发生额，需声明）。
- **样例输入**：F1。
- **调用顺序**：corrupt → chunk（无需）→ Skill：定义"发生额 = 借方金额与贷方金额按行取非空/非零值之和"，
  `groupby("交易类型").agg(笔数=..., 发生额=...)`，占比 = 各类/总额 ×100%。
- **答案要点**：六类交易齐全；笔数合计=总行数（可作闭合校验并在答案中给出）；占比合计≈100%（说明四舍五入误差）。
- **护栏**：占比口径必须写出来，评委可复算。

### Q8（分析·时间趋势）

- **题面（模拟）**："按月看转账汇出的金额趋势，哪个月最高？月均多少？工作日和周末的笔数对比呢？"
- **考点**：时间维度聚合（月）、均值、派生维度（星期）。
- **样例输入**：F1。
- **调用顺序**：corrupt → chunk（无需）→ Skill：`groupby(df.交易日期.dt.to_period("M"))` 求月合计与均值；
  `df.交易日期.dt.dayofweek >= 5` 分工作日/周末计数。
- **答案要点**：三个月各自金额、最高月及金额、月均；工作日/周末笔数及占比；全部数字可由表复算。
- **护栏**：无。

### Q9（分析·超大文件分块，对接用例 1-2 的分块能力）

- **题面（模拟）**："这个 6 千行的大表，amount 列总和、平均值各是多少？我要看你是分块算的，不能一次整表加载。"
- **考点**：`chunk_large_workbook` 规划 → 按 chunks 逐块累加 → **行数闭合校验**。
- **样例输入**：**现有** `poc/fixtures/large_chunk_demo.xlsx`（无需造）。
  结构：sheet `DemoData`，表头 `row_id, amount, note`，6000 条数据（Excel 6001 行），`amount = row_id × 10.5`。
- **调用顺序**：
  1. `detect_corrupt_workbook` → `ok=true`（"工作簿正常"）。
  2. `detect_encoding`（可选）→ utf-8 / 1.0。
  3. `chunk_large_workbook({"path": "poc/fixtures/large_chunk_demo.xlsx"})`（默认 `max_rows=5000`）→
     实测返回：`needs_chunking=true, total_rows=6001, max_sheet_rows=6001`，
     `chunks=[{"start_row":1,"end_row":5000,"sheet":"DemoData"},{"start_row":5001,"end_row":6001,"sheet":"DemoData"}]`。
     演示阈值可调：传 `max_rows=2000` 得 4 块（1–2000/2001–4000/4001–6000/6001–6001）。
  4. Skill 按块用 openpyxl `read_only` 按行号区间迭代（或 pandas `skiprows/nrows`，注意**行号含表头**），
     逐块累加 count/sum，最后 `mean = sum/count`；闭合校验：两块数据行 4999 + 1001 = 6000，与 `total_rows-1`（扣表头）一致。
- **期望答案（确定性，已用脚本核算）**：**sum = 189,031,500.0，mean = 31,505.25，count = 6000**。
- **护栏**：答案必须附两块的行号范围与闭合校验；若演示时换成 CSV 大文件，`chunk_large_workbook` 会返回
  "无法打开工作簿做分块: InvalidFileException" —— 这不是崩溃，agent 应改走 `pd.read_csv(chunksize=5000)` 流式累加并向用户说明。

### Q10（写入·筛选结果另存）

- **题面（模拟）**："把 Q4 查出来的这些大额转账导成一个新的 Excel 给我。"
- **考点**：写回交付；返回输出路径；不覆盖原文件。
- **样例输入**：F1（读）；输出 **待造目录约定** `poc/fixtures/output/`（运行时生成，不放真实数据入库）。
- **调用顺序**：对源文件走完整三工具（同 Q4）→ Skill：筛选结果 `df.to_excel("<工作区>/poc/fixtures/output/容桂支行3月大额转账.xlsx", index=False)`。
- **答案要点**：回答新文件的工作区相对路径；打开复核 sheet 行列与 Q4 笔数一致；原文件未被修改（mtime/内容不变）。
- **护栏**：输出路径同样必须在 `POC_WORKSPACE` 内（agent 自己的写文件动作也受沙箱约束）；
  若用户给了工作区外路径，要拒绝并提示"路径越界 / Path outside workspace"。

### Q11（写入·原表增列另存）

- **题面（模拟）**："给流水加一列'大额标记'，借方金额超过 5 万标'是'，否则'否'，另存一份，原表别动。"
- **考点**：列派生 + 全量保留 + 另存；可演示 openpyxl 定点写或 pandas 重写。
- **样例输入**：F1；输出 `poc/fixtures/output/bank_transactions_flagged.xlsx`。
- **调用顺序**：三工具 → Skill：pandas 读全表（小表）→
  `df["大额标记"] = np.where(df.借方金额>50000, "是", "否")` → `to_excel` 另存；
  若强调保留原格式/公式则改用 openpyxl `load_workbook` → 新表头 → 逐行写 → `save` 新路径。
- **答案要点**：新文件行数=原行数、列数 +1；标记"是"的笔数与 Q4 同口径筛选数一致；原文件保持不变。
- **护栏**：同 Q10（沙箱内写、不覆盖原文件）。

### Q12（写入·多 sheet 汇总工作簿）

- **题面（模拟）**："生成一个新工作簿：第一个 sheet 放原始明细，第二个 sheet 放按网点汇总的笔数和借贷总金额。"
- **考点**：`ExcelWriter` 多 sheet 写出 + 透视/汇总；交付物仍是 xlsx（不触发报告可视化场景边界）。
- **样例输入**：F1；输出 `poc/fixtures/output/branch_summary.xlsx`。
- **调用顺序**：三工具 → Skill：`df.groupby("网点名称").agg(笔数=("交易流水号","count"), 借方合计=("借方金额","sum"), 贷方合计=("贷方金额","sum"))`
  → 用 `pd.ExcelWriter(out) as w:` 两次 `to_excel(w, sheet_name="明细"/"网点汇总")`。
- **答案要点**：新文件 2 个 sheet；汇总表网点数与主数据去重网点数一致；各网点笔数之和=明细总行数（闭合）。
- **护栏**：同 Q10。

---

## 4. 用例 1-2：三道异常题 Y1–Y3（docx 指定现场测试，护栏文案照念）

> 文案均为 `guards.py` 中真实 message 的逐字引用（文件名部分随实际输入变化）；
> 演示纪律：agent 必须**原样转述 MCP message**，损坏场景**停止读写**，不得自行"修复打开"。

### Y1 损坏文件检测

- **输入**：现有 `poc/fixtures/corrupt.xlsx`（44 字节文本伪装成 xlsx）。
- **调用**：`detect_corrupt_workbook({"path": "poc/fixtures/corrupt.xlsx"})`
- **真实返回**：
  `{"ok": false, "issue": "corrupt", "message": "检测到损坏的 Excel 工作簿 / Corrupt workbook detected: corrupt.xlsx。文件不是有效的 Office Open XML (ZIP) 包，无法用 openpyxl 打开。请重新导出或修复后再试。"}`
- **期望行为**：展示提示 → **终止**，不再调用后续读取。
- **变体（建议补造 F4）**：合法 ZIP 但缺 `[Content_Types].xml` 时，issue 同为 `corrupt`，文案为
  "…ZIP 包缺少 [Content_Types].xml，结构不完整。请重新导出或修复后再试。"——证明不是只看扩展名/魔数。
- 此时若硬调 `chunk_large_workbook`，返回 `needs_chunking=false` + "无法打开工作簿做分块: BadZipFile"，同样不得继续。

### Y2 编码自动识别

- **输入 A（现有）**：`poc/fixtures/encoding_gbk.csv`（20 字节，内容 `姓名,城市 / 张三,北京` 的 GBK 编码）。
  `detect_encoding` 实测：`encoding="gb18030", confidence=0.12`，message：
  "编码置信度偏低 / Low-confidence encoding guess: gb18030 (confidence=0.12)，文件：encoding_gbk.csv。建议按 latin-1/gbk 尝试转码为 UTF-8 后再读取，勿直接当 UTF-8 打开。"
- **输入 B（现有）**：`poc/fixtures/encoding_latin1.csv` → `windows-1252, confidence=0.03`，同款低置信度提示。
- **输入 C（建议补造 F5，UTF-16）**：message 走高置信度分支：
  "检测到非 UTF-8 编码 / Non-UTF-8 encoding detected: utf-16 (confidence=1.00)，文件：xxx.csv。读取 CSV/文本前请先转码为 UTF-8，否则中文或特殊字符可能乱码。"
- **期望行为**：agent 不把低置信度当失败，按提示用候选编码（gb18030→gbk→latin-1；utf-16 直接相应编码）读取成功并展示无乱码内容；
  全程向用户讲清"检测→置信度→转码/按候选读取"三步。

### Y3 超大文件分块处理

- **输入**：现有 `poc/fixtures/large_chunk_demo.xlsx`（6001 行 / 约 117 KiB；超的是**行数阈值** 5000，不是字节阈值）。
- **调用**：`chunk_large_workbook({"path": "poc/fixtures/large_chunk_demo.xlsx"})`
- **真实返回**：`needs_chunking=true`，`chunks` 两块 `DemoData!1–5000`、`DemoData!5001–6001`，
  message："工作表行数过大，需要分块处理 / Large sheet needs chunking: max_sheet_rows=6001 > max_rows=5000，已生成 2 个分块范围。"
- **期望行为**：agent 展示分块计划，按块读取、逐块聚合、行数闭合（4999+1001=6000），再给答案（同 Q9）。
- **对照演示**：同一文件传 `max_rows=100000` → `needs_chunking=false`，message 含"行数未超限，无需分块 / No chunking needed: … <= max_rows=100000"。

### 4.x 其余护栏矩阵（被问到时照此回答，全部为代码真实行为）

| 场景 | 造数方式 | issue / 形态 | 用户可见文案（逐字模板） |
|---|---|---|---|
| 旧版 `.xls` | 任意内容改名 `legacy.xls`（建议补造 F3） | `unsupported` | "旧版 Excel 格式不支持 / Legacy .xls format not supported: <文件名>。请另存为 .xlsx 后再试。" |
| 未知后缀 | 如 `data.bin` | `unsupported` | "不支持的文件格式 / Unsupported file format: .bin。请使用 .xlsx / .xlsm / .csv 等支持的格式。" |
| 文件过大 | 文件 > `POC_EXCEL_MAX_BYTES`（默认 200 MiB；演示可临时把环境变量调小复现） | `too_large` | "文件过大 / File too large: <文件名> (<n> bytes > <limit>)。请先拆分或压缩。"（`chunk_large_workbook` 超限时同一文案出现在 message） |
| ZIP 条目炸弹 | > `POC_EXCEL_MAX_ZIP_ENTRIES`（默认 10,000） | `unsafe_archive` | "ZIP 条目过多 / Too many ZIP entries: <n> > <limit>。文件可能异常，请检查来源。" |
| 文件不存在 | 路径写错 | `missing` | "文件不存在 / File not found: <path>。请确认路径是否正确。" |
| 路径越界 | 传工作区外路径或越界符号链接 | `path_denied` | "路径越界 / Path outside workspace root (<root>): <path>"（符号链接变体为"符号链接越界 / Symlink escapes workspace"） |
| 路径是目录/空路径 | 传目录或空串 | `invalid_path` | "路径是目录，不是文件 / Path is a directory, not a file: …"；"路径不能为空 / path must not be empty" |
| 空 CSV | 0 字节 | detect_encoding：`utf-8`/0.0 | "空文件 / Empty file: <文件名>" |
| 对 CSV 调分块 | 任意 .csv | `needs_chunking=false` | "无法打开工作簿做分块 / Cannot open workbook for chunking: InvalidFileException" → agent 改走 pandas `chunksize` |
| max_rows 非法 | 0 或 >1,000,000 | `needs_chunking=false` | "max_rows 必须 >= 1 / max_rows must be >= 1"；"max_rows 过大 / max_rows too large: …" |

---

## 5. 用例 1-3：SKILL 评审自查（现场讲解口径）

打开 `poc/skills/excel-qa-bank/SKILL.md` 对照评委五项逐条指给评委看：

1. **名称**：frontmatter `name: excel-qa-bank`；
2. **描述**：面向银行演示的 Excel/CSV 读查析写，且明确"先调 excel-guard 再问答"；
3. **触发词**：excel问答、表格分析、xlsx、csv查询、读取/查询/分析/写入 Excel 或 CSV、上传表格并提问；
4. **参数**：输入（文件路径 + 自然语言问题）、输出（文字答案 + 可选写回路径 + 护栏提示）均有表格定义；
5. **返回值 + 边界**：成功/失败返回约定；四条边界——非表格交付物不触发、损坏先报 MCP 并停止、超大必须分块、CSV 必先检编码；
   文末有与三个 MCP 工具的协作流程图。

加分口径（可主动讲）：SKILL.md 有 frontmatter、五段式结构由测试 `test_skill_doc.py` 强制；MCP 返回 key（`ok/issue/message` 等）受 32 个集成测试锁定兼容。

---

## 6. Fixture 缺口清单（需人工/后续任务补造，全部合成数据）

| 编号 | 文件 | 用于 | 规格 |
|---|---|---|---|
| F1 | `poc/fixtures/bank_transactions.xlsx` | Q1、Q2、Q4–Q8、Q10–Q12 | 见 §2：`交易流水` 300+ 行（2026-01～03，6 类交易、5～8 网点、≥10 笔 >5 万转账汇出）+ `客户信息` 30 行；两表用客户号关联；数据全部虚构 |
| F2 | `poc/fixtures/bank_branch_gbk.csv` | Q3、Y2 | GBK 编码中文网点名单，≥10 行、几百字节以上（让 chardet 样本更有意义） |
| F3 | `poc/fixtures/legacy_bill.xls` | 4.x 矩阵（unsupported） | 任意字节 + `.xls` 后缀即可（现场临时生成也行） |
| F4 | `poc/fixtures/corrupt_no_manifest.xlsx` | Y1 变体（可选推荐） | 合法 ZIP 但不含 `[Content_Types].xml` |
| F5 | `poc/fixtures/transactions_utf16.csv` | Y2 高置信度分支（推荐） | UTF-16 编码 CSV，含表头与几十行中文数据（chardet 对 UTF-16 稳定 1.00） |
| F6 | `poc/fixtures/output/`（目录） | Q10–Q12 | 写回产物目录，运行时生成；演示前清空，勿把合成输出误当客户数据 |

现有可直接用的 fixture：`corrupt.xlsx`（Y1）、`encoding_gbk.csv` / `encoding_latin1.csv`（Y2）、
`large_chunk_demo.xlsx`（Q9/Y3）、`generate_fixtures.py`（现有三件套的再生成脚本）。

**纪律**：补造数据一律不得使用真实客户姓名、账号、证件号、手机号；Q9 的期望数字（6000 行 / sum 189,031,500 /
mean 31,505.25）与现有 fixture 绑定，若重新生成 `large_chunk_demo.xlsx` 需同步改本卷。

---

## 7. 行方真题到达后的替换 SOP（演示前 3 个工作日）

1. 拿到 12 题题面与配套数据文件后，把数据文件放进 `POC_WORKSPACE` 内（建议 `poc/fixtures/real_set/`，注意保密、不入库）。
2. 每题先空跑一遍三工具，记录真实 issue/encoding/chunks 返回，替换本卷 Q1–Q12 的题面、输入文件名与"答案要点"中的数字。
3. MCP 调用顺序、护栏文案、多轮与分块闭合方法**不需要改**——它们由代码决定。
4. 若真题含 `.xls` 或 >200 MiB 文件，当场预期就是 `unsupported` / `too_large` 提示，按 §4.x 口径答，不要临场改代码硬撑。
5. 12 题结果截图 + 本卷（填好实际答案）作为测试报告附件留档。

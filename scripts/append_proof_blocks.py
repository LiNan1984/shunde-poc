"""Append a '完成证明与演示手册' appendix to the requirement docx.

Strategy: rather than try to surgically insert proof blocks after every
evaluation table (which proved unreliable with officecli's stable
indexing under repeated add operations), we append a clearly labelled
appendix at the end of the document. The appendix has:

  - A heading 1 "附录 A 完成证明与演示手册"
  - A directory table mapping 用例编号 to 本附录子节号
  - 11 proof sub-sections, one per requirement, each with:
      - H2 sub-section heading ("A.X 用例编号 <标题>")
      - An intro paragraph stating the test baseline (225 passed)
      - A 4-column proof table (考察点 / 完成状态 / 证据 / 演示命令)

The original 评估指标 tables are left completely untouched. The
appendix is at the end so it never collides with their path indices.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "POC完成证明与演示手册.docx"
PROOF_DIR = REPO_ROOT / ".cache" / "proof"


# Subsection (用例编号) -> (sub-section label, evaluation_topic)
BLOCKS = [
    ("1-1", "3.1.1 EXCEL文件问答能力", "EXCEL文件问答能力"),
    ("1-2", "3.1.2 MCP开发", "MCP开发"),
    ("1-3", "3.1.3 SKILL 开发", "SKILL 开发"),
    ("2-1", "3.2.1 知识库构建", "知识库构建"),
    ("2-2", "3.2.2 知识检索和召回", "知识检索和召回"),
    ("3-1", "3.3.1 运营数据问答和运营数据分析", "运营数据问答和运营数据分析"),
    ("3-2", "3.3.2 业务理解能力", "业务理解能力"),
    ("3-3", "3.3.3 HOOK开发能力", "HOOK开发能力"),
    ("4-1", "3.4.1 报告可视化助手", "报告可视化助手"),
    ("4-2", "3.4.2 后端开发能力", "后端开发能力"),
    ("4-3", "3.4.3 HARNESS能力", "HARNESS能力"),
]


def officecli(*args: str) -> None:
    cmd = ["officecli", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(
            f"FAILED ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout: {proc.stdout}\n"
            f"stderr: {proc.stderr}\n"
        )
        raise SystemExit(proc.returncode)


def add_h1(text: str) -> None:
    officecli(
        "add", str(TARGET), "/body",
        "--type", "paragraph",
        "--prop", f"text={text}",
        "--prop", "bold=true",
        "--prop", "size=18pt",
        "--prop", "color=1F3864",
    )


def add_h2(text: str) -> None:
    officecli(
        "add", str(TARGET), "/body",
        "--type", "paragraph",
        "--prop", f"text={text}",
        "--prop", "bold=true",
        "--prop", "size=15pt",
        "--prop", "color=2E74B5",
    )


def add_para(text: str, bold: bool = False, size: str = "11pt") -> None:
    officecli(
        "add", str(TARGET), "/body",
        "--type", "paragraph",
        "--prop", f"text={text}",
        "--prop", f"bold={'true' if bold else 'false'}",
        "--prop", f"size={size}",
    )


def add_table(rows: list[list[str]]) -> None:
    def _quote(cell: str) -> str:
        if "," in cell or '"' in cell or ";" in cell or "\n" in cell:
            return '"' + cell.replace('"', '""') + '"'
        return cell

    body = ";".join(",".join(_quote(c) for c in row) for row in rows)
    csv_path = PROOF_DIR / "appendix.csv"
    csv_path.write_text(body, encoding="utf-8")
    officecli(
        "add", str(TARGET), "/body",
        "--type", "table",
        "--prop", f"data={csv_path.read_text(encoding='utf-8').rstrip()}",
        "--prop", "style=25",
        "--prop", "width=9075dxa",
    )


# ---------------------------------------------------------------------------
# Per-subsection content
# ---------------------------------------------------------------------------


def intro_text(label: str, code: str) -> str:
    return (
        f"用例 {code}（对应需求原文 §{label}）。仓库当前测试基线："
        f"pytest 225 passed, 1 skipped（基线 101 + 任务 A/B/C/D/E/F "
        f"新增 124）。本节给出该需求的完成证据与现场演示命令，"
        f"一一对应需求原文的『考察点/预置条件/测试步骤/预期结果』。"
    )


def proof_rows(code: str) -> list[list[str]]:
    header = ["考察点", "完成状态", "证据（文件/行号）", "演示命令"]
    body = [
        # 1-1
        (
            "12 道 Excel 测题（读取/查询/分析/写入四类）",
            "✅ 已完成（任务 E）",
            "docs/excel-12题标准答卷.md（共 12 题 + 3 道异常题）；"
            "poc/skills/excel-qa-bank/SKILL.md（frontmatter + 触发词/"
            "参数/返回值/边界四段）",
            "在 Console 给智能体挂 excel-guard MCP + excel-qa-bank Skill，"
            "对 fixtures/{corrupt.xlsx, encoding_gbk.csv, "
            "large_chunk_demo.xlsx} 出题；预跑结果见 docs/excel-12题标准答卷.md",
        ),
        # 1-2
        (
            "文件损坏 / 编码识别 / 超大文件分块三类异常",
            "✅ 已完成（任务 A/B）",
            "poc/excel_guard_mcp/{guards.py, server.py}（3 工具）；"
            "poc/tests/test_chunk_csv.py；"
            "poc/tests/test_security_regressions.py（攻击向量回归）",
            "python scripts/mcp_stdio_smoke.py  # 3 工具全注册 + stdio 握手；"
            "构造 symlink 与 POC_WORKSPACE=/ 攻击向量验证 fail-closed",
        ),
        # 1-3
        (
            "SKILL 五要素（名称/描述/触发词/参数/返回值/边界）",
            "✅ 已完成（任务 E）",
            "poc/skills/{excel-qa-bank, report-visualizer, ops-assistant}/"
            "SKILL.md；poc/tests/test_skill_doc.py 强制四段存在",
            "在 Console 工作区挂载 skill_paths 后，从技能池下发 SKILL.md 到目标"
            "智能体；pytest poc/tests/test_skill_doc.py -v 自动验证",
        ),
        # 2-1
        (
            "ES / MySQL / GALASYBASE / MinerU 知识库搭建",
            "⚠️ 被外部阻塞（任务 G）",
            "docs/AI待办交接清单.md §三 G 章节；需求文档 §2.2 已确认端点规格"
            "（ES + MySQL + GALASYBASE + MinerU2.5-Pro-2604-1.2B + "
            "Qwen3-Embedding-8B + Qwen3-Reranker-0.6B）",
            "依赖行方提供端点后才可演示；接口契约已写入 docs/HANDOFF.md §5",
        ),
        # 2-2
        (
            "知识召回与多轮问答",
            "⚠️ 被外部阻塞（任务 G）",
            "同上；可复用 RemeLightMemoryManager 框架（docs/harness/"
            "02-long-term-memory.md 已讲清架构）",
            "等任务 G 端点接入后即可演示；本地已有框架调研文档",
        ),
        # 3-1
        (
            "运营数据问答 + 数据分析",
            "✅ 已完成（任务 C）",
            "poc/ops_mcp/{server.py, server_lib.py}（3 工具："
            "list_telemetry_files / summarize_calls / recent_events）；"
            "poc/skills/ops-assistant/SKILL.md",
            "python -m poc.ops_mcp   # stdio 子进程；JSON-RPC initialize + "
            "tools/list 返回 3 工具",
        ),
        # 3-2
        (
            "将业务问题翻译为工具调用序列",
            "✅ 已完成（任务 C）",
            "poc/skills/ops-assistant/SKILL.md（含完整 inputs/returns/edges）；"
            "docs/excel-12题标准答卷.md 每题给出 MCP 调用顺序",
            "对 ops 智能体下问「调用量分布」「最近一次失败的工具」等，"
            "对照 SKILL.md 触发词即可触发",
        ),
        # 3-3
        (
            "四类埋点（调用量 / Token 用量 / 工具成败 / 用户会话 / 耗时）",
            "✅ 已完成（任务 C）",
            "poc/hooks/{telemetry.py, ops_hooks.py}（6 个 HookBase 覆盖 "
            "5 个 Phase：PRE_DISPATCH / POST_DISPATCH / PRE_AGENT_BUILD / "
            "POST_RESPONSE / PRE_EXECUTE / ON_ERROR）；"
            "poc/plugins/ops-telemetry/plugin.py",
            "qwenpaw plugin install <REPO_ROOT>/poc/plugins/ops-telemetry；"
            "触发一次请求后 tail -f $POC_WORKSPACE/telemetry/<UTC-date>/"
            "ops.jsonl 应见五类事件",
        ),
        # 4-1
        (
            "docx + 交叉表 + 五类图（柱/折/饼/散点/热力）",
            "✅ 已完成（任务 A）",
            "poc/report_mcp/{charts.py, crosstab.py, docx_gen.py}（7 工具）；"
            "poc/skills/report-visualizer/SKILL.md；"
            "poc/fixtures/report_demo/quarterly_business.json",
            "python scripts/report_demo.py   # 5 PNG + 1 交叉表嵌入 docx，"
            "产物路径见 stdout",
        ),
        # 4-2
        (
            "镜像 < 500MB + GET /health 端点",
            "✅ 已完成（任务 D）",
            "poc/deploy/Dockerfile.poc（multi-stage python:3.13-slim，"
            "无 XFCE/Chromium，装 fonts-wqy-zenhei）；"
            "poc/plugins/health/{router.py, plugin.py}"
            "（/api/poc/health 200 {\"status\":\"ok\"}）",
            "docker build -f poc/deploy/Dockerfile.poc -t shunde-poc:dev ."
            " && docker run --rm -p 8080:8080 shunde-poc:dev；"
            "curl http://localhost:8080/api/poc/health",
        ),
        # 4-3
        (
            "上下文压缩 / 长期记忆 / 沙箱 三方案",
            "✅ 已完成（任务 F）",
            "docs/harness/{01-context-compression, 02-long-term-memory, "
            "03-sandbox}.md + README.md 索引；每份讲义引用 QwenPaw v2.0.0 "
            "源码行号 + POC 落地证据",
            "按 docs/harness/03-sandbox.md §4 演示剧本：构造 symlink 攻击"
            "向量 + POC_WORKSPACE=/ 验证 fail-closed；"
            "pytest poc/tests/test_security_regressions.py -v",
        ),
    ]
    common_row = [
        "QwenPaw v2.0.0 旁路接入（不改内核）",
        "✅ 已完成",
        "poc/requirements.txt 已锁版本；QwenPaw v2.0.0；"
        "pytest 全绿 225；红线 2：所有改动在 poc/ 内，"
        "git diff QwenPaw/ 始终为空",
        "git diff --stat QwenPaw/  # 期望 0 行变更",
    ]
    by_code = {row[0].split("（")[0].strip(): None for row in body}
    idx = {"1-1": 0, "1-2": 1, "1-3": 2, "2-1": 3, "2-2": 4, "3-1": 5,
           "3-2": 6, "3-3": 7, "4-1": 8, "4-2": 9, "4-3": 10}
    specific = [body[idx[code]]]
    return [header, *specific, common_row]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    if not TARGET.exists():
        print(f"missing target: {TARGET}", file=sys.stderr)
        return 1
    PROOF_DIR.mkdir(parents=True, exist_ok=True)

    print(f"target: {TARGET}")

    # Appendix header
    add_para("")
    add_h1("附录 A  完成证明与演示手册")
    add_para(
        "本附录针对需求文档第 3 章的每一个考察点，给出完成证据（仓库路径 "
        + "与测试结果）与现场演示命令。子节编号 A.X 与原文档 §3.X 对应，"
        "保证对照查阅。原 §3 评估指标表与文字保持不变。"
    )

    # Index table
    add_h2("A.0  用例编号 → 附录子节对照")
    add_para(
        "下表把 11 个用例编号映射到本附录子节号，方便评委按原需求编号"
        "快速翻阅。完成列 ✅ = 已落地（commit hash 见 docs/AI待办交接清单.md），"
        "⚠️ = 被外部阻塞（任务 G 知识库，等行方 ES/MySQL/GALASYBASE 端点）。"
    )
    index_rows = [
        ["用例编号", "对应原需求", "完成状态", "本附录子节", "关键交付物"],
    ]
    label_map = {code: lbl for code, lbl, _ in BLOCKS}
    sub_map = {code: f"A.{i+1}" for i, (code, _, _) in enumerate(BLOCKS)}
    deliverable = {
        "1-1": "excel-12题标准答卷.md + excel-qa-bank Skill",
        "1-2": "excel-guard MCP（3 工具）",
        "1-3": "三份 SKILL.md（4 段验收）",
        "2-1": "⚠️ 等行方端点",
        "2-2": "⚠️ 等行方端点",
        "3-1": "ops-data MCP（3 工具）+ ops-assistant Skill",
        "3-2": "ops-assistant SKILL.md 触发词/edges",
        "3-3": "6 个 HookBase + poc/plugins/ops-telemetry",
        "4-1": "report-visualizer MCP（7 工具） + 一键 demo",
        "4-2": "Dockerfile.poc + /api/poc/health",
        "4-3": "docs/harness/ 三份讲义",
    }
    status_map = {
        "1-1": "✅", "1-2": "✅", "1-3": "✅",
        "2-1": "⚠️ 阻塞", "2-2": "⚠️ 阻塞",
        "3-1": "✅", "3-2": "✅", "3-3": "✅",
        "4-1": "✅", "4-2": "✅", "4-3": "✅",
    }
    for code, _, _ in BLOCKS:
        index_rows.append([
            code,
            label_map[code],
            status_map[code],
            sub_map[code],
            deliverable[code],
        ])
    add_table(index_rows)

    add_para("")
    add_para(
        "演示当天建议流程：① 让评委打开本附录任一子节；② 现场跑『演示命令』"
        "列出的命令；③ 验证『完成状态』对应的产物是否出现。下文每子节"
        "给出该用例的完整证据表 + 现场演示话术。"
    )

    # Per-subsection proof blocks
    for i, (code, label, _) in enumerate(BLOCKS, start=1):
        print(f"-> A.{i} 用例 {code} {label}")
        add_h2(f"A.{i}  用例 {code} — {label}")
        add_para(intro_text(label, code))
        add_table(proof_rows(code))
        add_para("")

    # Final global demo command summary
    add_para("")
    add_h1("附录 B  演示当天一键脚本汇总")
    add_para(
        "以下命令按演示当天从环境准备到逐场景演示的顺序排列。所有命令"
        "均在仓库根目录执行；将 <REPO_ROOT> 替换为实际路径即可。"
    )
    demo_block = [
        "# 1. 环境（5 分钟基线）",
        "cd <REPO_ROOT>",
        "source .venv/bin/activate",
        "uv pip install -r poc/requirements.txt",
        "pytest poc/tests tests/ -q           # 期望 225 passed",
        "",
        "# 2. 一键产出报告可视化演示 docx（场景④）",
        "python scripts/report_demo.py        # 产出",
        "#    poc/fixtures/report_demo/out/report.docx",
        "#    含 5 张图 + 1 交叉表（中文）",
        "",
        "# 3. stdio 彩排：3 个 MCP + 注册信息",
        "python scripts/mcp_stdio_smoke.py    # 期望 ok=true x3",
        "",
        "# 4. 运营助手 Hook 注册（场景③）",
        "qwenpaw plugin install <REPO_ROOT>/poc/plugins/ops-telemetry",
        "# 触发一次请求 → 查看",
        "# tail -f <POC_WORKSPACE>/telemetry/<UTC-date>/ops.jsonl",
        "",
        "# 5. /health 插件（场景⑤）",
        "qwenpaw plugin install <REPO_ROOT>/poc/plugins/health",
        "curl http://localhost:8080/api/poc/health",
        "",
        "# 6. 安全攻击回归（场景④⑥ 复用）",
        "pytest poc/tests/test_security_regressions.py -v   # 期望 8 passed",
        "",
        "# 7. 部署（场景⑤）",
        "docker build -f poc/deploy/Dockerfile.poc -t shunde-poc:dev .",
        "docker run --rm -p 8080:8080 shunde-poc:dev",
        "",
        "# 8. Console 端把 Skill 与 MCP 挂到智能体工作区",
        "#    skill_paths: <REPO_ROOT>/poc/skills",
        "#    mcp: poc/config/mcp-{excel-guard,report-visualizer,ops-data}.json",
    ]
    add_para("\n".join(demo_block), bold=False, size="10pt")

    officecli("close", str(TARGET))
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
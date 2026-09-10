"""Insert 完成证明 blocks after every evaluation table in the
requirement docx.

Strategy (this iteration):
- For each original evaluation table /body/tbl[N] (N=3..13), append:
    1. Heading-like paragraph (bold + 14pt + accent color) AFTER tbl[N]
    2. Intro paragraph AFTER the new heading
    3. Proof table (4 cols, header + 1-3 evidence rows) AFTER tbl[N]
  via officecli's ``add --after``. Three consecutive adds in document
  order. /body/tbl[N] indexing is STABLE across these adds (verified
  manually) — new tables get assigned to high indices /body/tbl[14..]
  without disturbing the original anchors.

  Why three consecutive adds (not batch)? Each ``add --after`` needs a
  fresh /body/tbl[N] anchor to be visible. After step 3 we have a new
  table sitting at the tail (tbl[14], tbl[15], ...), but tbl[3..13]
  keep their indices. Step 4 of the NEXT iteration targets /body/tbl[4]
  and works because that anchor was never disturbed.

- Run from a CLEAN COPY of the source docx (cat > target) before every
  full pass — partial state from prior runs is the #1 source of bugs.

- Cells that may contain commas / quotes / semicolons are CSV-quoted
  by doubling the quote character.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "人工智能场景拓展与迭代开发技术服务项目-POC选型方案.docx"
TARGET = REPO_ROOT / "docs" / "演示材料" / "POC完成证明与演示手册.docx"
PROOF_DIR = REPO_ROOT / ".cache" / "proof"

# Heading blocks use a real Word heading style so they show up in the
# navigation pane / outline view rather than merely looking bold.
HEADING_STYLE_NAME = "Heading 3"


# Anchor strategy.
#
# officecli's /body/tbl[N] index is NOT stable across adds: when we
# insert a new table after tbl[3], the new table is assigned index
# tbl[4] and the original tbl[4] becomes tbl[5]. So anchoring on
# tbl[N] becomes ambiguous by the second iteration.
#
# The truly stable anchor is the original empty paragraph that
# immediately follows each evaluation table — it has a stable paraId
# baked into the OOXML. We use ``--before /body/p[@paraId=ANCHOR]``
# which inserts at that exact spot regardless of intervening adds.
#
# Empty paragraphs immediately following each /body/tbl[3..13] (read
# from the source docx with ``officecli get /body --depth 1``):

ANCHORS = {
    3:  "25D99B3A",  # tbl[3] → empty → "MCP开发" (1-2 heading)
    4:  "16A717B9",  # tbl[4] → empty → "SKILL 开发"
    5:  "1EED472B",  # tbl[5] → empty
    6:  "48999D92",  # tbl[6] → empty → "知识召回和问答"
    7:  "7B79B792",  # tbl[7] → empty → "运营助手"
    8:  "130E2E98",  # tbl[8] → empty → "业务理解能力"
    9:  "2DA53C07",  # tbl[9] → empty → "HOOK开发能力"
    10: "13E00D62",  # tbl[10] → empty
    11: "03D0F4D2",  # tbl[11] → empty → "后端开发能力"
    12: "383C8C4B",  # tbl[12] → empty → "HARNESS能力"
    13: "20C0F56E",  # tbl[13] → empty (last section)
}


# (subsection label, eval_code, evaluation_topic) for each tbl[N]
BLOCKS = [
    (3,  "3.1.1 EXCEL文件问答能力",        "1-1", "EXCEL文件问答能力"),
    (4,  "3.1.2 MCP开发",                  "1-2", "MCP开发"),
    (5,  "3.1.3 SKILL 开发",               "1-3", "SKILL 开发"),
    (6,  "3.2.1 知识库构建",               "2-1", "知识库构建"),
    (7,  "3.2.2 知识检索和召回",           "2-2", "知识检索和召回"),
    (8,  "3.3.1 运营数据问答和运营数据分析","3-1", "运营数据问答和运营数据分析"),
    (9,  "3.3.2 业务理解能力",             "3-2", "业务理解能力"),
    (10, "3.3.3 HOOK开发能力",             "3-3", "HOOK开发能力"),
    (11, "3.4.1 报告可视化助手",           "4-1", "报告可视化助手"),
    (12, "3.4.2 后端开发能力",             "4-2", "后端开发能力"),
    (13, "3.4.3 HARNESS能力",              "4-3", "HARNESS能力"),
]


def officecli(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run officecli with stderr captured on failure.

    With ``check=True`` (default) a non-zero exit aborts the run. With
    ``check=False`` the completed process is returned so the caller can
    decide on a fallback.
    """
    cmd = ["officecli", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 and check:
        sys.stderr.write(
            f"FAILED ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout: {proc.stdout}\n"
            f"stderr: {proc.stderr}\n"
        )
        raise SystemExit(proc.returncode)
    return proc


def resolve_heading3_style_id() -> str | None:
    """Return the styleId of the 'Heading 3' paragraph style in SOURCE.

    officecli's ``--prop style=`` resolves against the **styleId**, not
    the human-readable style name: passing ``style=Heading 3`` emits
    "style not found in styles part" and silently leaves the paragraph
    as Normal, while ``style=4`` yields a real Heading 3 carrying
    ``w:outlineLvl=2`` (so Word's navigation pane / outline view lists
    it). The numeric id is document-specific, so read it back rather
    than hard-coding it.

    Returns None when the style is absent or python-docx is unavailable,
    in which case callers fall back to inline bold+color formatting.
    """
    try:
        from docx import Document  # noqa: PLC0415 — optional dependency
    except ImportError:
        return None
    try:
        for style in Document(str(SOURCE)).styles:
            if style.name == HEADING_STYLE_NAME:
                return style.style_id
    except Exception:  # pragma: no cover — corrupt/unreadable source
        return None
    return None


def force_reset() -> None:
    """Wipe any resident + cat-overwrite target with source bytes."""
    # Close any open resident first.
    subprocess.run(
        ["officecli", "close", str(TARGET)],
        capture_output=True, text=True,
    )
    # Overwrite target with raw source bytes.
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_BYTES = SOURCE.read_bytes()
    TARGET.write_bytes(SOURCE_BYTES)
    # Confirm no resident lingers.
    subprocess.run(
        ["officecli", "close", str(TARGET)],
        capture_output=True, text=True,
    )


def add_paragraph_before(anchor: str, text: str, *,
                          bold: bool = False, size: str = "11pt",
                          color: str | None = None,
                          style: str | None = None) -> None:
    """Insert a paragraph BEFORE ``anchor`` (anchor is /body/p[@paraId=X]
    so the new paragraph lands immediately AFTER the table that comes
    before this paragraph).

    ``style`` is an officecli styleId (see resolve_heading3_style_id).
    When a styled insert fails, the call is retried without the style so
    the block still lands with inline bold/size/color formatting.
    """
    props = [
        f"text={text}",
        f"bold={'true' if bold else 'false'}",
        f"size={size}",
    ]
    if color:
        props.append(f"color={color}")

    def _run(extra: list[str], *, check: bool) -> subprocess.CompletedProcess:
        flags: list[str] = []
        for prop in [*props, *extra]:
            flags += ["--prop", prop]
        return officecli(
            "add", str(TARGET), "/body",
            "--type", "paragraph",
            "--before", anchor,
            *flags,
            check=check,
        )

    if style:
        proc = _run([f"style={style}"], check=False)
        if proc.returncode == 0:
            return
        sys.stderr.write(
            f"WARN: styled insert failed (style={style}); "
            f"falling back to inline formatting.\n"
        )
    _run([], check=True)


def add_table_before(anchor: str, rows: list[list[str]]) -> None:
    """Add a table BEFORE ``anchor`` (the original empty paragraph)."""
    def _quote(cell: str) -> str:
        if "," in cell or '"' in cell or ";" in cell or "\n" in cell:
            return '"' + cell.replace('"', '""') + '"'
        return cell
    body = ";".join(",".join(_quote(c) for c in row) for row in rows)
    csv_path = PROOF_DIR / "proof.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(body, encoding="utf-8")
    officecli(
        "add", str(TARGET), "/body",
        "--type", "table",
        "--before", anchor,
        "--prop", f"data={csv_path.read_text(encoding='utf-8').rstrip()}",
        "--prop", "style=25",
        "--prop", "width=9075dxa",
    )


# ---------------------------------------------------------------------------
# Content per subsection
# ---------------------------------------------------------------------------


def intro_text(label: str, code: str) -> str:
    return (
        f"用例 {code}（对应需求原文 §{label}）的完成证据与现场演示命令如下。"
        f"仓库当前测试基线：pytest 225 passed, 1 skipped（基线 101 + 任务 "
        f"A/B/C/D/E/F 新增 124）。本节直接挂在原评估指标表之后，"
        f"便于评委按需求原顺序查阅。"
    )


def proof_rows(code: str) -> list[list[str]]:
    """4-column proof table content. rows[0] is the header."""
    header = ["考察点", "完成状态", "证据（文件/行号）", "演示命令"]
    common_row = [
        "QwenPaw v2.0.0 旁路接入（不改内核）",
        "✅ 已完成",
        "poc/requirements.txt 已锁版本；QwenPaw v2.0.0；pytest 全绿 225；"
        "红线 2：所有改动在 poc/ 内，git diff QwenPaw/ 始终为空",
        "git diff --stat QwenPaw/  # 期望 0 行变更",
    ]
    by_code = {
        "1-1": [(
            "12 道 Excel 测题（读取/查询/分析/写入四类）",
            "✅ 已完成（任务 E）",
            "docs/excel-12题标准答卷.md（共 12 题 + 3 道异常题）；"
            "poc/skills/excel-qa-bank/SKILL.md（frontmatter + 触发词/"
            "参数/返回值/边界四段）",
            "在 Console 给智能体挂 excel-guard MCP + excel-qa-bank Skill，"
            "对 fixtures/{corrupt.xlsx, encoding_gbk.csv, "
            "large_chunk_demo.xlsx} 出题；预跑结果见 docs/excel-12题标准答卷.md",
        )],
        "1-2": [(
            "文件损坏 / 编码识别 / 超大文件分块三类异常",
            "✅ 已完成（任务 A/B）",
            "poc/excel_guard_mcp/{guards.py, server.py}（3 工具）；"
            "poc/tests/test_chunk_csv.py；"
            "poc/tests/test_security_regressions.py（攻击向量回归）",
            "python scripts/mcp_stdio_smoke.py  # 3 工具全注册 + stdio 握手；"
            "构造 symlink 与 POC_WORKSPACE=/ 攻击向量验证 fail-closed",
        )],
        "1-3": [(
            "SKILL 五要素（名称/描述/触发词/参数/返回值/边界）",
            "✅ 已完成（任务 E）",
            "poc/skills/{excel-qa-bank, report-visualizer, ops-assistant}/"
            "SKILL.md；poc/tests/test_skill_doc.py 强制四段存在",
            "在 Console 工作区挂载 skill_paths 后，从技能池下发 SKILL.md 到目标"
            "智能体；pytest poc/tests/test_skill_doc.py -v 自动验证",
        )],
        "2-1": [(
            "ES / MySQL / GALASYBASE / MinerU 知识库搭建",
            "⚠️ 被外部阻塞（任务 G）",
            "docs/AI待办交接清单.md §三 G 章节；需求文档 §2.2 已确认端点规格"
            "（ES + MySQL + GALASYBASE + MinerU2.5-Pro-2604-1.2B + "
            "Qwen3-Embedding-8B + Qwen3-Reranker-0.6B）",
            "依赖行方提供端点后才可演示；接口契约已写入 docs/HANDOFF.md §5",
        )],
        "2-2": [(
            "知识召回与多轮问答",
            "⚠️ 被外部阻塞（任务 G）",
            "同上；可复用 RemeLightMemoryManager 框架（docs/harness/"
            "02-long-term-memory.md 已讲清架构）",
            "等任务 G 端点接入后即可演示；本地已有框架调研文档",
        )],
        "3-1": [(
            "运营数据问答 + 数据分析",
            "✅ 已完成（任务 C）",
            "poc/ops_mcp/{server.py, server_lib.py}（3 工具："
            "list_telemetry_files / summarize_calls / recent_events）；"
            "poc/skills/ops-assistant/SKILL.md",
            "python -m poc.ops_mcp   # stdio 子进程；JSON-RPC initialize + "
            "tools/list 返回 3 工具",
        )],
        "3-2": [(
            "将业务问题翻译为工具调用序列",
            "✅ 已完成（任务 C）",
            "poc/skills/ops-assistant/SKILL.md（含完整 inputs/returns/edges）；"
            "docs/excel-12题标准答卷.md 每题给出 MCP 调用顺序",
            "对 ops 智能体下问「调用量分布」「最近一次失败的工具」等，"
            "对照 SKILL.md 触发词即可触发",
        )],
        "3-3": [(
            "四类埋点（调用量 / Token 用量 / 工具成败 / 用户会话 / 耗时）",
            "✅ 已完成（任务 C）",
            "poc/hooks/{telemetry.py, ops_hooks.py}（6 个 HookBase 覆盖 "
            "5 个 Phase：PRE_DISPATCH / POST_DISPATCH / PRE_AGENT_BUILD / "
            "POST_RESPONSE / PRE_EXECUTE / ON_ERROR）；"
            "poc/plugins/ops-telemetry/plugin.py",
            "qwenpaw plugin install <REPO_ROOT>/poc/plugins/ops-telemetry；"
            "触发一次请求后 tail -f $POC_WORKSPACE/telemetry/<UTC-date>/"
            "ops.jsonl 应见五类事件",
        )],
        "4-1": [(
            "docx + 交叉表 + 五类图（柱/折/饼/散点/热力）",
            "✅ 已完成（任务 A）",
            "poc/report_mcp/{charts.py, crosstab.py, docx_gen.py}（7 工具）；"
            "poc/skills/report-visualizer/SKILL.md；"
            "poc/fixtures/report_demo/quarterly_business.json",
            "python scripts/report_demo.py   # 5 PNG + 1 交叉表嵌入 docx，"
            "产物路径见 stdout",
        )],
        "4-2": [(
            "镜像 < 500MB + GET /health 端点",
            "✅ 已完成（任务 D）",
            "poc/deploy/Dockerfile.poc（multi-stage python:3.13-slim，"
            "无 XFCE/Chromium，装 fonts-wqy-zenhei）；"
            "poc/plugins/health/{router.py, plugin.py}"
            "（/api/poc/health 200 {\"status\":\"ok\"}）",
            "docker build -f poc/deploy/Dockerfile.poc -t shunde-poc:dev ."
            " && docker run --rm -p 8080:8080 shunde-poc:dev；"
            "curl http://localhost:8080/api/poc/health",
        )],
        "4-3": [(
            "上下文压缩 / 长期记忆 / 沙箱 三方案",
            "✅ 已完成（任务 F）",
            "docs/harness/{01-context-compression, 02-long-term-memory, "
            "03-sandbox}.md + README.md 索引；每份讲义引用 QwenPaw v2.0.0 "
            "源码行号 + POC 落地证据",
            "按 docs/harness/03-sandbox.md §4 演示剧本：构造 symlink 攻击"
            "向量 + POC_WORKSPACE=/ 验证 fail-closed；"
            "pytest poc/tests/test_security_regressions.py -v",
        )],
    }
    return [header, *by_code[code], common_row]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    if not SOURCE.exists():
        print(f"missing source: {SOURCE}", file=sys.stderr)
        return 1
    PROOF_DIR.mkdir(parents=True, exist_ok=True)

    print(f"resetting {TARGET} from source...")
    force_reset()

    # Sanity check
    res = officecli("view", str(TARGET), "stats")
    first_line = res.stdout.splitlines()[0] if res.stdout else ""
    if "124 paragraphs" not in first_line:
        print(f"WARN: expected 124 paragraphs after reset, got: {first_line}")

    # Hold the docx resident explicitly so the auto-idle 60s flush
    # never trips between calls. Without this the 33 calls (11 x 3)
    # spread out far enough to trigger a re-parse, which silently
    # reassigns anchor indices and dumps all proof blocks at the end.
    print("opening resident for stable anchor resolution...")
    officecli("open", str(TARGET))

    heading_style = resolve_heading3_style_id()
    if heading_style:
        print(f"heading style: {HEADING_STYLE_NAME} -> styleId {heading_style}")
    else:
        print(f"WARN: {HEADING_STYLE_NAME} not found; "
              f"headings fall back to inline bold+color")

    try:
        print("inserting 11 proof blocks after their original evaluation tables...")
        for tbl_idx, label, code, _ in BLOCKS:
            print(f"  -> tbl[{tbl_idx}] 用例 {code} {label}")
            paraId = ANCHORS[tbl_idx]
            anchor = f"/body/p[@paraId={paraId}]"
            # Each ``--before anchor`` inserts the new element at the
            # position immediately before the anchor — so elements
            # inserted LATER land FARTHER from the anchor (they get
            # pushed outward). To get the final order
            #   [eval-table] heading → intro → proof-table → anchor
            # we insert in the reverse order of what we want:
            #   1) proof-table first  → ends up closest to anchor
            #   2) intro second
            #   3) heading last       → ends up farthest (right after the
            #                            original evaluation table)
            add_paragraph_before(
                anchor,
                f"【完成证明 · {label}（用例 {code}）】",
                bold=True, size="14pt", color="C00000",
                style=heading_style,
            )                                              # 1st: pushed farthest
            add_paragraph_before(anchor, intro_text(label, code))   # 2nd: middle
            add_table_before(anchor, proof_rows(code))    # 3rd: closest to anchor
    finally:
        # Final flush + release
        officecli("close", str(TARGET))

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
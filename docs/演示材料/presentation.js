const pptxgen = require("pptxgenjs");
const path = require("path");

const ARCH = path.join(__dirname, "architecture");
function arch(name) {
  return path.join(ARCH, name);
}

const C = {
  navy: "1E2A3A",
  navyDark: "172231",
  gold: "C5A55A",
  white: "FFFFFF",
  offWhite: "F7F8FA",
  lightGray: "E8EAED",
  midGray: "9CA3AF",
  darkGray: "4B5563",
  text: "1F2937",
  textLight: "6B7280",
  cream: "FDF6E3",
  red: "C0392B",
  amber: "D4A017",
  green: "27AE60",
  blueGray: "2D3E50",
};

const FONT = "PingFang SC";
const TOTAL = 29;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3" x 7.5" — room for 16:10 architecture PNGs
pres.author = "顺德农商行 POC";
pres.title = "顺德农商行 POC · 四个助手架构";
pres.subject = "Excel / 多模态 / 运营 / 报告可视化";

function addContentHeader(slide, title, slideNum) {
  slide.addText(title, {
    x: 0.6,
    y: 0.28,
    w: 11.4,
    h: 0.5,
    fontSize: 20,
    fontFace: FONT,
    bold: true,
    color: C.text,
    margin: 0,
  });
  if (slideNum) {
    slide.addText(`${slideNum} / ${TOTAL}`, {
      x: 12.0,
      y: 7.1,
      w: 0.9,
      h: 0.25,
      fontSize: 10,
      color: C.midGray,
      align: "right",
      fontFace: FONT,
      margin: 0,
    });
  }
}

function addSourceNote(slide, note) {
  slide.addText(note, {
    x: 0.6,
    y: 7.08,
    w: 11.2,
    h: 0.28,
    fontSize: 10,
    italic: true,
    color: C.midGray,
    fontFace: FONT,
    margin: 0,
  });
}

function goldBar(slide) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 13.3,
    h: 0.05,
    fill: { color: C.gold },
  });
}

function addArchSlide(title, file, slideNum, note) {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, title, slideNum);
  // PNG is 1920x1200 (1.6:1). Max height under title ≈ 6.15"
  const imgH = 5.95;
  const imgW = imgH * 1.6;
  const imgX = (13.3 - imgW) / 2;
  s.addImage({
    path: arch(file),
    x: imgX,
    y: 0.88,
    w: imgW,
    h: imgH,
  });
  addSourceNote(s, note);
}

// ═══════════════════════════════════════════════════════
// SLIDE 1 – Cover
// ═══════════════════════════════════════════════════════
(function slide1() {
  const s = pres.addSlide();
  s.background = { color: C.navyDark };
  goldBar(s);

  s.addText("顺 德 农 商 行   P O C", {
    x: 0.8,
    y: 0.55,
    w: 8,
    h: 0.35,
    fontSize: 14,
    fontFace: FONT,
    color: C.gold,
    charSpacing: 3,
    margin: 0,
  });

  s.addText("四个助手架构", {
    x: 0.8,
    y: 1.15,
    w: 11.5,
    h: 0.85,
    fontSize: 40,
    fontFace: FONT,
    bold: true,
    color: C.white,
    margin: 0,
  });

  s.addText("基于最新旁路代码：Excel 问答 · 多模态知识库 · 运营埋点 · 报告可视化", {
    x: 0.8,
    y: 2.1,
    w: 11,
    h: 0.4,
    fontSize: 16,
    fontFace: FONT,
    italic: true,
    color: C.gold,
    margin: 0,
  });

  s.addText("宿主 QwenPaw 2.2.2b1  ·  相对 2.0.0：缓存命中率 + Files 查看/下载  ·  POC 旁路不改内核", {
    x: 0.8,
    y: 2.55,
    w: 11,
    h: 0.3,
    fontSize: 13,
    fontFace: FONT,
    color: C.midGray,
    margin: 0,
  });

  s.addShape(pres.shapes.LINE, {
    x: 0.8,
    y: 3.1,
    w: 11.6,
    h: 0,
    line: { color: C.gold, width: 1 },
  });

  const kpis = [
    { value: "4", label: "专用助手" },
    { value: "25", label: "MCP 工具" },
    { value: "L1-L3", label: "渐进加载" },
    { value: "Files", label: "可查看下载" },
    { value: "2.0.0", label: "旧版是黑盒" },
  ];
  kpis.forEach((kpi, i) => {
    const cx = 0.8 + i * 2.4;
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx,
      y: 3.45,
      w: 2.2,
      h: 1.35,
      fill: { color: C.blueGray },
    });
    s.addText(kpi.value, {
      x: cx,
      y: 3.6,
      w: 2.2,
      h: 0.65,
      fontSize: 28,
      fontFace: FONT,
      bold: true,
      color: C.gold,
      align: "center",
      margin: 0,
    });
    s.addText(kpi.label, {
      x: cx,
      y: 4.25,
      w: 2.2,
      h: 0.35,
      fontSize: 12,
      fontFace: FONT,
      color: C.midGray,
      align: "center",
      margin: 0,
    });
  });

  s.addText("2026-09-15  |  glm-5.3-flash  |  Console  https://shunde-poc.harness-agent.app/chat", {
    x: 0,
    y: 6.95,
    w: 13.3,
    h: 0.3,
    fontSize: 11,
    fontFace: FONT,
    color: C.midGray,
    align: "center",
    charSpacing: 0.5,
    margin: 0,
  });
})();

// ═══════════════════════════════════════════════════════
// SLIDE 2 – Agenda
// ═══════════════════════════════════════════════════════
(function slide2() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "目录", 2);

  const items = [
    { n: "01", t: "四助手总览", d: "Agent / Skill / MCP 对照，以及本轮代码升级" },
    { n: "02", t: "接入原则", d: "QwenPaw 不 fork，旁路挂载 Skill + MCP + Hook" },
    { n: "03", t: "Excel 问答", d: "9 工具护栏 → pandas 精算 → 写后自检" },
    { n: "04", t: "多模态文件", d: "MinerU 入库 · 四库端口 · RRF 重排 · 看图作答" },
    { n: "05", t: "运营埋点", d: "不进插件市场；本地安装后看「已安装插件」" },
    { n: "06", t: "L1 / L2 / L3", d: "skill列表摘要 → skill → mcp列表namespace前缀 → 详细mcp → 文件摘要 → 文件详情" },
    { n: "07", t: "相对 2.0.0", d: "缓存命中率、前缀一致性省 token、Files 可下载；旧版是黑盒" },
    { n: "08", t: "四助手任务分布", d: "每个助手一张图；优化方向与落地合同一致" },
  ];
  items.forEach((it, i) => {
    const col = i < 4 ? 0 : 1;
    const row = i < 4 ? i : i - 4;
    const x = 0.6 + col * 6.3;
    const y = 1.1 + row * 1.25;
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y,
      w: 5.95,
      h: 1.1,
      fill: { color: C.offWhite },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y,
      w: 0.08,
      h: 1.1,
      fill: { color: C.gold },
    });
    s.addText(it.n, {
      x: x + 0.25,
      y: y + 0.22,
      w: 0.7,
      h: 0.65,
      fontSize: 18,
      fontFace: FONT,
      bold: true,
      color: C.gold,
      margin: 0,
    });
    s.addText(it.t, {
      x: x + 1.05,
      y: y + 0.18,
      w: 4.6,
      h: 0.4,
      fontSize: 16,
      fontFace: FONT,
      bold: true,
      color: C.text,
      margin: 0,
    });
    s.addText(it.d, {
      x: x + 1.05,
      y: y + 0.58,
      w: 4.6,
      h: 0.35,
      fontSize: 12,
      fontFace: FONT,
      color: C.textLight,
      margin: 0,
    });
  });
})();

// ═══════════════════════════════════════════════════════
// SLIDE 3 – Overview table
// ═══════════════════════════════════════════════════════
(function slide3() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "四个助手：前端名称、Agent、Skill、MCP 一一对应", 3);

  const hdr = {
    fill: { color: C.navy },
    color: C.white,
    bold: true,
    fontSize: 12,
    fontFace: FONT,
    align: "center",
    valign: "middle",
  };
  const cell = { fontSize: 12, fontFace: FONT, color: C.text, valign: "middle" };
  const cellC = { ...cell, align: "center" };

  s.addTable(
    [
      [
        { text: "前端名称", options: hdr },
        { text: "Agent ID", options: hdr },
        { text: "Skill", options: hdr },
        { text: "MCP（工具数）", options: hdr },
        { text: "本轮要点", options: hdr },
      ],
      [
        { text: "Excel问答助手", options: { ...cell, bold: true } },
        { text: "excel-agent", options: cellC },
        { text: "excel-qa-bank", options: cellC },
        { text: "excel-guard ×9", options: cellC },
        { text: "检测损坏 / 识别编码 / 分块 / 描述结构 / 转 Markdown / 守卫写回 / 结构化读取 / OpenXML 校验 / 渲染成图", options: cell },
      ],
      [
        { text: "多模态文件助手", options: { ...cell, bold: true } },
        { text: "kb-agent", options: cellC },
        { text: "kb-qa-bank", options: cellC },
        { text: "kb-qa ×6", options: cellC },
        { text: "索引表格元数据 / 看图作答 / RRF 重排", options: cell },
      ],
      [
        { text: "运营助手", options: { ...cell, bold: true } },
        { text: "ops-agent", options: cellC },
        { text: "ops-assistant", options: cellC },
        { text: "ops-data ×3", options: cellC },
        { text: "列出埋点 / 汇总调用量 / 最近事件 · 无数据不编造", options: cell },
      ],
      [
        { text: "报告可视化助手", options: { ...cell, bold: true } },
        { text: "report-agent", options: cellC },
        { text: "report-visualizer", options: cellC },
        { text: "report-visualizer ×7", options: cellC },
        { text: "交叉表 + 柱/折/饼/散点/热力图 + 生成 docx", options: cell },
      ],
    ],
    {
      x: 0.6,
      y: 1.05,
      w: 12.1,
      colW: [2.15, 1.85, 2.2, 2.05, 3.85],
      border: { pt: 0.5, color: C.lightGray },
      rowH: [0.48, 0.72, 0.72, 0.72, 0.72],
    }
  );

  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6,
    y: 4.7,
    w: 12.1,
    h: 1.95,
    fill: { color: C.offWhite },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6,
    y: 4.7,
    w: 0.08,
    h: 1.95,
    fill: { color: C.gold },
  });
  s.addText("模型与策略", {
    x: 0.9,
    y: 4.85,
    w: 11.5,
    h: 0.35,
    fontSize: 14,
    fontFace: FONT,
    bold: true,
    color: C.text,
    margin: 0,
  });
  s.addText(
    [
      { text: "对话模型：Volcengine Ark / glm-5.3-flash（演示口径，不是行方最终 Qwen3.6）", options: { breakLine: true } },
      { text: "MCP 策略：allow（演示不必每次点批准）  ·  路径沙箱：POC_WORKSPACE，越界拒绝", options: { breakLine: true } },
      { text: "红线：不改 QwenPaw/src  ·  密钥只放 ~/.qwenpaw.secret（mode 600），不进 git", options: {} },
    ],
    {
      x: 0.9,
      y: 5.25,
      w: 11.5,
      h: 1.2,
      fontSize: 13,
      fontFace: FONT,
      color: C.text,
      margin: 0,
    }
  );
  addSourceNote(s, "来源：docs/前端四助手交接文档.md 与 poc/*/server.py 最新工具清单");
})();

// ═══════════════════════════════════════════════════════
// SLIDE 4 – Bypass principle
// ═══════════════════════════════════════════════════════
(function slide4() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "接入原则：官方内核不动，四个助手全部旁路挂载", 4);

  const cards = [
    { t: "宿主", v: "QwenPaw 2.2.2b1", d: "当前宿主，git submodule，不 fork。相对旧版 2.0.0 多了 Files 查看/下载与 cache_read_tokens。" },
    { t: "Skill", v: "skill_paths", d: "poc/skills 登记进 ~/.qwenpaw/config.json，下发到对应智能体，每助手只启用 1 个 Skill。" },
    { t: "MCP", v: "stdio FastMCP", d: "poc/config/mcp-*.json 导入 Console。25 个工具（Excel 9 + KB 6 + 运营 3 + 报告 7）。" },
    { t: "Hook / 健康", v: "官方插件 API", d: "poc-ops-telemetry 注册 6 个 Hook；poc-health 挂 /api/poc/health。均不改内核。" },
  ];
  cards.forEach((c, i) => {
    const x = 0.6 + (i % 2) * 6.3;
    const y = 1.05 + Math.floor(i / 2) * 2.55;
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y,
      w: 6.05,
      h: 2.35,
      fill: { color: C.offWhite },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y,
      w: 0.08,
      h: 2.35,
      fill: { color: i === 0 ? C.gold : C.navy },
    });
    s.addText(c.t, {
      x: x + 0.3,
      y: y + 0.22,
      w: 5.5,
      h: 0.3,
      fontSize: 12,
      fontFace: FONT,
      color: C.gold,
      bold: true,
      margin: 0,
    });
    s.addText(c.v, {
      x: x + 0.3,
      y: y + 0.55,
      w: 5.5,
      h: 0.45,
      fontSize: 20,
      fontFace: FONT,
      bold: true,
      color: C.text,
      margin: 0,
    });
    s.addText(c.d, {
      x: x + 0.3,
      y: y + 1.15,
      w: 5.5,
      h: 0.95,
      fontSize: 13,
      fontFace: FONT,
      color: C.textLight,
      margin: 0,
    });
  });
  addSourceNote(s, "红线 2：git diff QwenPaw/ 必须为空。旁路永远在 poc/。");
})();

// ═══════════════════════════════════════════════════════
// SLIDE 5 – Latest upgrades
// ═══════════════════════════════════════════════════════
(function slide5() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "本轮代码升级：Excel 读面压缩 + 知识库多模态闭环", 5);

  const left = [
    { h: "Excel · excel-guard 现为 9 工具", b: "护栏 5 个 + 守卫写回 edit_workbook、结构化读取 inspect_workbook、OpenXML 校验 validate_workbook、渲染成图 render_workbook。" },
    { h: "结构压缩再精算", b: "表头投票、合并区、公式别名；禁止整表转 markdown 让模型猜数。写后 audit_workbook：#REF! 等 must_fix，硬编码进 review。" },
    { h: "黄金回归 10/10", b: "干净明细 / 多级合并表头 / 未缓存公式列 / GBK CSV。基线按 skill 流程执行 10/10。" },
  ];
  const right = [
    { h: "KB · kb-qa 4→6 工具", b: "新增 ingest_spreadsheet（只索引表头/样例，定位文件）、analyze_page（页 PNG 看图作答）。" },
    { h: "检索升级", b: "BM25 + 文本向量 + 图像向量 → RRF；多模态问才并入图像路。可选 qwen3.7-text-rerank 对 top16 重排。" },
    { h: "四库端口可降级", b: "ES 19200 / MySQL 13306 接通则活写；GALASYBASE 无镜像，图库走 graph.json。未接通不假装写入行方集群。" },
  ];

  function col(items, x) {
    items.forEach((it, i) => {
      const y = 1.05 + i * 1.85;
      s.addShape(pres.shapes.RECTANGLE, {
        x,
        y,
        w: 6.05,
        h: 1.7,
        fill: { color: C.offWhite },
      });
      s.addShape(pres.shapes.RECTANGLE, {
        x,
        y,
        w: 0.08,
        h: 1.7,
        fill: { color: C.gold },
      });
      s.addText(it.h, {
        x: x + 0.3,
        y: y + 0.18,
        w: 5.55,
        h: 0.4,
        fontSize: 15,
        fontFace: FONT,
        bold: true,
        color: C.text,
        margin: 0,
      });
      s.addText(it.b, {
        x: x + 0.3,
        y: y + 0.62,
        w: 5.55,
        h: 0.9,
        fontSize: 13,
        fontFace: FONT,
        color: C.textLight,
        margin: 0,
      });
    });
  }
  col(left, 0.6);
  col(right, 6.85);
  addSourceNote(s, "来源：poc/excel_guard_mcp/readers.py、poc/kb_mcp/{server,retrieve,vision,spreadsheet}.py、poc/evals");
})();

// ═══════════════════════════════════════════════════════
// SLIDES 6–9 – Four architecture diagrams
// ═══════════════════════════════════════════════════════
addArchSlide(
  "Excel问答助手：护栏通过后，数字只来自 pandas / openpyxl",
  "excel-agent.png",
  6,
  "excel-guard ×9：检测损坏表 · 识别编码 · 超大表分块 · 描述表结构 · 表转 Markdown · 守卫写回 · 结构化读取 · OpenXML 校验 · 渲染成图"
);

addArchSlide(
  "多模态文件助手：解析入库 → 四库 → 混合检索 → 看图作答",
  "kb-agent.png",
  7,
  "kb-qa：解析文档 · 入库文档 · 索引表格元数据 · 检索知识 · 知识问答 · 看图作答"
);

addArchSlide(
  "运营助手：只观察、只读 JSONL，没有埋点就说暂无埋点",
  "ops-agent.png",
  8,
  "ops-data：列出埋点文件 · 汇总调用量 · 最近事件  ·  四类：调用量 / Token / 工具成败 / 耗时"
);

addArchSlide(
  "埋点形态：插件装进去，Runtime 相位里跑，落盘是 JSONL",
  "hook-plugin-runtime.png",
  9,
  "poc-ops-telemetry 一个插件注册 6 HookBase；市场看不到，已安装 Tab 才有"
);

// ═══════════════════════════════════════════════════════
// SLIDE 10 – Why Hook is not in Plugin Market
// ═══════════════════════════════════════════════════════
(function slideMarket() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "插件市场看不到 6 Hook：市场是远程目录，本插件是本地旁路", 10);

  const tabs = [
    { t: "插件市场", v: "看不到", d: "拉的是 AgentScope 平台 /plugins/market/search。只列出已发布到 platform.agentscope.io 的插件。POC 没发布，所以搜不到。" },
    { t: "官方插件", v: "看不到", d: "拉的是官方 CDN 清单。poc-ops-telemetry 不在下载站，同样不会出现。" },
    { t: "已安装插件", v: "装完才有", d: "本地 ~/.qwenpaw/plugins。qwenpaw plugin install 或「安装插件」拖入文件夹后，出现在这个 Tab，类型 Hook。" },
  ];
  tabs.forEach((c, i) => {
    const x = 0.55 + i * 4.2;
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y: 0.95,
      w: 4.0,
      h: 2.85,
      fill: { color: C.offWhite },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y: 0.95,
      w: 0.08,
      h: 2.85,
      fill: { color: i === 2 ? C.gold : C.navy },
    });
    s.addText("设置 → 插件管理 → " + c.t, {
      x: x + 0.25,
      y: 1.1,
      w: 3.55,
      h: 0.32,
      fontSize: 12,
      fontFace: FONT,
      color: C.gold,
      bold: true,
      margin: 0,
    });
    s.addText(c.v, {
      x: x + 0.25,
      y: 1.48,
      w: 3.55,
      h: 0.45,
      fontSize: 22,
      fontFace: FONT,
      bold: true,
      color: i === 2 ? C.green : C.red,
      margin: 0,
    });
    s.addText(c.d, {
      x: x + 0.25,
      y: 2.05,
      w: 3.55,
      h: 1.55,
      fontSize: 13,
      fontFace: FONT,
      color: C.textLight,
      margin: 0,
    });
  });

  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.55,
    y: 4.0,
    w: 12.2,
    h: 2.7,
    fill: { color: C.offWhite },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.55,
    y: 4.0,
    w: 0.08,
    h: 2.7,
    fill: { color: C.gold },
  });
  s.addText("怎么装到「已安装插件」", {
    x: 0.85,
    y: 4.15,
    w: 11.6,
    h: 0.35,
    fontSize: 16,
    fontFace: FONT,
    bold: true,
    color: C.text,
    margin: 0,
  });
  s.addText(
    [
      { text: "1. 停掉 QwenPaw（官方要求：装插件时内核必须离线）。", options: { breakLine: true } },
      { text: "2. 命令行：qwenpaw plugin install <仓库>/poc/plugins/ops-telemetry", options: { breakLine: true } },
      { text: "   或 Console「安装插件」把该文件夹拖进去（不要只在插件市场里搜）。", options: { breakLine: true } },
      { text: "3. 重启后打开 设置 → 插件管理 → 已安装插件，应看到「运营埋点 Hook（6 Hook / 5 Phase）」。", options: { breakLine: true } },
      { text: "市场里的分类「生命周期 Hook」是别人发布到平台的插件，不是本仓库这 6 个埋点。", options: {} },
    ],
    {
      x: 0.85,
      y: 4.55,
      w: 11.6,
      h: 2.0,
      fontSize: 13,
      fontFace: FONT,
      color: C.text,
      margin: 0,
    }
  );
  addSourceNote(s, "来源：console PluginManager 三个 Tab  ·  GET /api/plugins/market/search  ·  docs/HOOK交接文档.md §7.1");
})();

addArchSlide(
  "现场实录：问 token 走内核账本，问失败率没有独立字段",
  "ops-two-paths.png",
  11,
  "2026-09-15 Console：「我的token」有 30 天数字；「看下失败率」对不上任何账本字段"
);

// ═══════════════════════════════════════════════════════
// SLIDE 11 – Charts from live token answer
// ═══════════════════════════════════════════════════════
(function slide11() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "「我的token」答出来的数字：内核 30 天账本，不是 JSONL", 12);

  const kpis = [
    { v: "935,384", l: "30 天 Token", s: "Prompt 912,678 + Completion 22,706" },
    { v: "50 次", l: "模型调用", s: "9/14 占 49 次，今天 1 次" },
    { v: "glm-5.3-flash", l: "全部来自该模型", s: "内核按 provider:model 记账" },
  ];
  kpis.forEach((k, i) => {
    const x = 0.55 + i * 4.2;
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y: 0.95,
      w: 4.0,
      h: 1.45,
      fill: { color: C.offWhite },
    });
    s.addText(k.v, {
      x,
      y: 1.05,
      w: 4.0,
      h: 0.5,
      fontSize: 22,
      fontFace: FONT,
      bold: true,
      color: C.navy,
      align: "center",
      margin: 0,
    });
    s.addText(k.l, {
      x,
      y: 1.52,
      w: 4.0,
      h: 0.32,
      fontSize: 13,
      fontFace: FONT,
      bold: true,
      color: C.text,
      align: "center",
      margin: 0,
    });
    s.addText(k.s, {
      x,
      y: 1.84,
      w: 4.0,
      h: 0.35,
      fontSize: 11,
      fontFace: FONT,
      color: C.textLight,
      align: "center",
      margin: 0,
    });
  });

  s.addChart(pres.charts.BAR, [{
    name: "Token",
    labels: ["9月14日", "9月15日"],
    values: [924034, 11350],
  }], {
    x: 0.45,
    y: 2.55,
    w: 6.4,
    h: 4.2,
    barDir: "col",
    chartColors: ["C5A55A", "1E2A3A"],
    chartArea: { fill: { color: "FFFFFF" } },
    showTitle: true,
    title: "按日 Token（内核账本）",
    titleColor: "1F2937",
    titleFontSize: 12,
    titleFontFace: FONT,
    showLegend: false,
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelColor: "1F2937",
    dataLabelFontSize: 10,
    catAxisLabelColor: "6B7280",
    valAxisLabelColor: "6B7280",
    valGridLine: { color: "E8EAED", size: 0.5 },
    catGridLine: { style: "none" },
  });

  s.addChart(pres.charts.PIE, [{
    name: "构成",
    labels: ["输入 Prompt", "输出 Completion"],
    values: [912678, 22706],
  }], {
    x: 6.9,
    y: 2.55,
    w: 5.9,
    h: 4.2,
    chartColors: ["1E2A3A", "C5A55A"],
    chartArea: { fill: { color: "FFFFFF" } },
    showTitle: true,
    title: "输入 / 输出构成",
    titleColor: "1F2937",
    titleFontSize: 12,
    titleFontFace: FONT,
    showPercent: true,
    showLegend: true,
    legendPos: "b",
  });
  addSourceNote(s, "现场 10:21「我的token」· token_usage.json · 不是 ops.jsonl。9/15 只占 1.2%，柱状图几乎看不见是数据形状，不是缺图。");
})();

// ═══════════════════════════════════════════════════════
// SLIDE 12 – Why failure rate is empty + what to ask
// ═══════════════════════════════════════════════════════
(function slide12() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "为什么「失败率」没有：四条原因，演示请改问法", 13);

  const reasons = [
    { n: "1", t: "内核没有失败率字段", d: "TokenUsageManager 只记 prompt / completion / call_count。问完 token 再问失败率，模型还在同一本账上，翻不到这一页。" },
    { n: "2", t: "JSONL 几乎不写 error", d: "PRE_EXECUTE 一律记 status=ok（开始调用）。真正的 error 只在 ON_ERROR 未捕获异常时写。工具返回失败、用户看见的报错，大多不会落成失败率。" },
    { n: "3", t: "Skill 触发词不含「失败率」", d: "ops-assistant 触发的是「调用量 / token 用量 / 哪个工具失败最多」。光说「看下失败率」不一定走到 ops-data。" },
    { n: "4", t: "无样本禁止编造", d: "summarize_calls 可以按 status 计数。JSONL 里没有 error 行时，正确回答是「暂无失败埋点」，不能编一个百分比。" },
  ];
  reasons.forEach((r, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.55 + col * 6.35;
    const y = 1.0 + row * 2.7;
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y,
      w: 6.15,
      h: 2.5,
      fill: { color: C.offWhite },
    });
    s.addShape(pres.shapes.OVAL, {
      x: x + 0.22,
      y: y + 0.28,
      w: 0.48,
      h: 0.48,
      fill: { color: C.navy },
    });
    s.addText(r.n, {
      x: x + 0.22,
      y: y + 0.34,
      w: 0.48,
      h: 0.38,
      fontSize: 14,
      fontFace: FONT,
      bold: true,
      color: C.gold,
      align: "center",
      margin: 0,
    });
    s.addText(r.t, {
      x: x + 0.85,
      y: y + 0.32,
      w: 5.05,
      h: 0.4,
      fontSize: 16,
      fontFace: FONT,
      bold: true,
      color: C.text,
      margin: 0,
    });
    s.addText(r.d, {
      x: x + 0.28,
      y: y + 0.95,
      w: 5.6,
      h: 1.3,
      fontSize: 13,
      fontFace: FONT,
      color: C.textLight,
      margin: 0,
    });
  });
})();

// ═══════════════════════════════════════════════════════
// SLIDE 13 – What you can ask
// ═══════════════════════════════════════════════════════
(function slide13() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "演示可以问什么：问对账本才有数字", 14);

  const hdr = {
    fill: { color: C.navy },
    color: C.white,
    bold: true,
    fontSize: 12,
    fontFace: FONT,
    align: "center",
    valign: "middle",
  };
  const ok = { fontSize: 12, fontFace: FONT, color: C.text, valign: "middle" };
  const okC = { ...ok, align: "center" };

  s.addTable(
    [
      [
        { text: "问法", options: hdr },
        { text: "走哪本账", options: hdr },
        { text: "现场预期", options: hdr },
      ],
      [
        { text: "我的 token  /  token 用量", options: { ...ok, bold: true } },
        { text: "内核 token_usage.json", options: okC },
        { text: "有。30 天、按日、输入/输出、模型名", options: ok },
      ],
      [
        { text: "今天调用量怎么样", options: { ...ok, bold: true } },
        { text: "JSONL call_volume", options: okC },
        { text: "有文件才有数；没有就说暂无埋点", options: ok },
      ],
      [
        { text: "哪个工具用得最多", options: { ...ok, bold: true } },
        { text: "JSONL tool_outcome + summarize_calls", options: okC },
        { text: "按 tool 计次，多数是 status=ok 的「开始调用」", options: ok },
      ],
      [
        { text: "最近一次失败的工具是什么", options: { ...ok, bold: true } },
        { text: "JSONL tool_outcome status=error", options: okC },
        { text: "仅当 ON_ERROR 写过才有；没有就说暂无", options: ok },
      ],
      [
        { text: "看下失败率", options: { ...ok, bold: true, color: C.red } },
        { text: "两本账都没有现成字段", options: okC },
        { text: "不要问。内核无此列，JSONL 也几乎无 error", options: ok },
      ],
      [
        { text: "转化率 / 用户反馈 / 营业日", options: { ...ok, bold: true, color: C.red } },
        { text: "未实现", options: okC },
        { text: "不要问。不进 MySQL/ES，禁止编造", options: ok },
      ],
    ],
    {
      x: 0.5,
      y: 1.0,
      w: 12.3,
      colW: [3.6, 3.5, 5.2],
      border: { pt: 0.5, color: C.lightGray },
      rowH: [0.42, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7],
    }
  );
  addSourceNote(s, "切到运营助手 ops-agent。token 类问题即使用默认助手也可能答出（内核账本）。失败率必须先有 JSONL error 行。");
})();

addArchSlide(
  "报告可视化助手：透视 → 五类图 PNG → python-docx 组装",
  "report-agent.png",
  15,
  "report-visualizer：交叉表 · 柱状图 · 折线图 · 饼图 · 散点图 · 热力图 · 生成 docx　输出锁在工作区"
);

// ═══════════════════════════════════════════════════════
// SLIDE 16 – 21 MCP tools with Chinese names
// ═══════════════════════════════════════════════════════
(function slideToolsZh() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "25 个 MCP 工具：中文名对照（演示时用中文说）", 16);

  const hdr = {
    fill: { color: C.navy },
    color: C.white,
    bold: true,
    fontSize: 11,
    fontFace: FONT,
    align: "center",
    valign: "middle",
  };
  const cell = { fontSize: 11, fontFace: FONT, color: C.text, valign: "middle" };
  const name = { ...cell, bold: true };

  function toolTable(title, x, rows) {
    s.addText(title, {
      x,
      y: 0.88,
      w: 6.0,
      h: 0.32,
      fontSize: 14,
      fontFace: FONT,
      bold: true,
      color: C.navy,
      margin: 0,
    });
    const data = [
      [
        { text: "中文名", options: hdr },
        { text: "工具 ID", options: hdr },
      ],
      ...rows.map((r) => [
        { text: r[0], options: name },
        { text: r[1], options: cell },
      ]),
    ];
    s.addTable(data, {
      x,
      y: 1.22,
      w: 6.0,
      colW: [2.4, 3.6],
      border: { pt: 0.4, color: C.lightGray },
      rowH: 0.32,
    });
  }

  toolTable("Excel问答  excel-guard（9）", 0.5, [
    ["检测损坏表", "detect_corrupt_workbook"],
    ["识别编码", "detect_encoding"],
    ["超大表分块", "chunk_large_workbook"],
    ["描述表结构", "describe_workbook"],
    ["表转 Markdown", "sheet_to_markdown"],
    ["守卫写回", "edit_workbook"],
    ["结构化读取", "inspect_workbook"],
    ["OpenXML 校验", "validate_workbook"],
    ["渲染成图", "render_workbook"],
  ]);

  toolTable("多模态文件  kb-qa（6）", 6.8, [
    ["解析文档", "parse_document"],
    ["入库文档", "ingest_document"],
    ["索引表格元数据", "ingest_spreadsheet"],
    ["检索知识", "search_knowledge"],
    ["知识问答", "answer_knowledge"],
    ["看图作答", "analyze_page"],
  ]);

  addSourceNote(s, "下页继续：运营 3 工具、报告 7 工具。stdio 合计 9+6+3+7=25。preflight / audit 是 python 内护栏，不是 MCP。");
})();

(function slideToolsZh2() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "运营 3 工具 + 报告 7 工具：中文名对照", 17);

  const hdr = {
    fill: { color: C.navy },
    color: C.white,
    bold: true,
    fontSize: 11,
    fontFace: FONT,
    align: "center",
    valign: "middle",
  };
  const cell = { fontSize: 12, fontFace: FONT, color: C.text, valign: "middle" };
  const name = { ...cell, bold: true };

  function toolTable(title, x, y, rows) {
    s.addText(title, {
      x,
      y,
      w: 6.0,
      h: 0.32,
      fontSize: 14,
      fontFace: FONT,
      bold: true,
      color: C.navy,
      margin: 0,
    });
    const data = [
      [
        { text: "中文名", options: hdr },
        { text: "工具 ID", options: hdr },
      ],
      ...rows.map((r) => [
        { text: r[0], options: name },
        { text: r[1], options: cell },
      ]),
    ];
    s.addTable(data, {
      x,
      y: y + 0.34,
      w: 6.0,
      colW: [2.4, 3.6],
      border: { pt: 0.4, color: C.lightGray },
      rowH: 0.32,
    });
  }

  toolTable("运营助手  ops-data（3）", 0.5, 0.88, [
    ["列出埋点文件", "list_telemetry_files_tool"],
    ["汇总调用量", "summarize_calls_tool"],
    ["最近事件", "recent_events_tool"],
  ]);

  toolTable("报告可视化  report-visualizer（7）", 6.8, 0.88, [
    ["交叉表", "pivot_table_tool"],
    ["柱状图", "render_bar_tool"],
    ["折线图", "render_line_tool"],
    ["饼图", "render_pie_tool"],
    ["散点图", "render_scatter_tool"],
    ["热力图", "render_heatmap_tool"],
    ["生成 docx 报告", "render_docx_report_tool"],
  ]);

  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5,
    y: 4.15,
    w: 12.3,
    h: 2.55,
    fill: { color: C.offWhite },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5,
    y: 4.15,
    w: 0.08,
    h: 2.55,
    fill: { color: C.gold },
  });
  s.addText("运营写侧不是 MCP 工具，是 6 个 Hook", {
    x: 0.8,
    y: 4.28,
    w: 11.8,
    h: 0.35,
    fontSize: 16,
    fontFace: FONT,
    bold: true,
    color: C.text,
    margin: 0,
  });
  s.addText(
    [
      { text: "调用量开始  poc_call_volume_start  ·  PRE_DISPATCH", options: { breakLine: true } },
      { text: "调用量结束  poc_call_volume_end  ·  POST_DISPATCH（同时写耗时）", options: { breakLine: true } },
      { text: "会话身份  poc_identity  ·  PRE_AGENT_BUILD", options: { breakLine: true } },
      { text: "Token 用量  poc_token_usage  ·  POST_RESPONSE", options: { breakLine: true } },
      { text: "工具开始  poc_tool_outcome  ·  PRE_EXECUTE（status=ok 表示开始调用）", options: { breakLine: true } },
      { text: "工具异常  poc_tool_error  ·  ON_ERROR", options: {} },
    ],
    {
      x: 0.8,
      y: 4.68,
      w: 11.8,
      h: 1.9,
      fontSize: 13,
      fontFace: FONT,
      color: C.textLight,
      margin: 0,
    }
  );
  addSourceNote(s, "Hook 装的是 poc-ops-telemetry 插件，不是 MCP。市场 Tab 看不到；已安装 Tab 才能看到。");
})();

// ═══════════════════════════════════════════════════════
// SLIDE 10 – Collaboration
// ═══════════════════════════════════════════════════════
(function slide10() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "四助手怎么协作：检索定位文件，代码负责算数字", 18);

  const steps = [
    { n: "1", t: "多文件问「哪张表」", d: "先调「索引表格元数据」ingest_spreadsheet：只索引文件名 / sheet / 表头 / 样例行，不把每一行灌进向量库。" },
    { n: "2", t: "「检索知识」路由", d: "search_knowledge 语义命中后拿到路径与 sheet。命中块只用来 locate，不当合计结果。" },
    { n: "3", t: "交回 Excel 精算", d: "「描述表结构」describe_workbook → pandas / openpyxl 精算或写回。筛选、合计、写回必须以代码为准。" },
    { n: "4", t: "图里数字走「看图作答」", d: "命中表格/图片块后调 analyze_page 读页面 PNG；未配视觉模型如实降级，不编造。" },
  ];
  steps.forEach((st, i) => {
    const y = 1.05 + i * 1.35;
    s.addShape(pres.shapes.OVAL, {
      x: 0.7,
      y: y + 0.25,
      w: 0.7,
      h: 0.7,
      fill: { color: C.navy },
    });
    s.addText(st.n, {
      x: 0.7,
      y: y + 0.35,
      w: 0.7,
      h: 0.5,
      fontSize: 20,
      fontFace: FONT,
      bold: true,
      color: C.gold,
      align: "center",
      margin: 0,
    });
    if (i < 3) {
      s.addShape(pres.shapes.RECTANGLE, {
        x: 1.02,
        y: y + 0.95,
        w: 0.06,
        h: 0.65,
        fill: { color: C.lightGray },
      });
    }
    s.addShape(pres.shapes.RECTANGLE, {
      x: 1.7,
      y,
      w: 11.0,
      h: 1.2,
      fill: { color: C.offWhite },
    });
    s.addText(st.t, {
      x: 1.95,
      y: y + 0.15,
      w: 10.5,
      h: 0.35,
      fontSize: 16,
      fontFace: FONT,
      bold: true,
      color: C.text,
      margin: 0,
    });
    s.addText(st.d, {
      x: 1.95,
      y: y + 0.55,
      w: 10.5,
      h: 0.5,
      fontSize: 13,
      fontFace: FONT,
      color: C.textLight,
      margin: 0,
    });
  });
})();

// ═══════════════════════════════════════════════════════
// SLIDE 11 – Eval and middleware
// ═══════════════════════════════════════════════════════
(function slide11() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "评测闸门与中间件：能量化的不靠主观判断", 19);

  const kpis = [
    { v: "10/10", l: "Excel 黄金集", s: "scripts/excel_qa_eval.py" },
    { v: "9 条", l: "KB Golden QA", s: "text / table / image 分组" },
    { v: "25", l: "stdio 工具齐全", s: "9 + 6 + 3 + 7" },
    { v: "双端口", l: "ES + MySQL", s: "19200 / 13306，不占 9200/3306" },
  ];
  kpis.forEach((k, i) => {
    const x = 0.6 + i * 3.15;
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y: 1.05,
      w: 3.0,
      h: 1.7,
      fill: { color: C.offWhite },
    });
    s.addText(k.v, {
      x,
      y: 1.18,
      w: 3.0,
      h: 0.6,
      fontSize: 26,
      fontFace: FONT,
      bold: true,
      color: C.navy,
      align: "center",
      margin: 0,
    });
    s.addText(k.l, {
      x,
      y: 1.78,
      w: 3.0,
      h: 0.35,
      fontSize: 14,
      fontFace: FONT,
      bold: true,
      color: C.text,
      align: "center",
      margin: 0,
    });
    s.addText(k.s, {
      x,
      y: 2.15,
      w: 3.0,
      h: 0.4,
      fontSize: 11,
      fontFace: FONT,
      color: C.textLight,
      align: "center",
      margin: 0,
    });
  });

  const rows = [
    ["层", "活路", "未接通时"],
    ["向量", "Elasticsearch 8.17 :19200", "本地 vectors.json + 哈希向量（单测不打外网）"],
    ["关系", "MySQL 8 :13306 / poc_kb", "sqlite meta.sqlite"],
    ["图", "GALASYBASE 无官方镜像", "graph.json，答案不得写成已写入 Galaxybase"],
    ["解析", "MinerU :18000 或 CLI", "pypdf；空页 OCR；无 tesseract 说明原因不填假字"],
    ["看图", "POC_VISION_MODEL + 页 PNG", "error_type=config/network，降级为切块文字并声明未核对"],
  ];
  const hdrOpts = {
    fill: { color: C.navy },
    color: C.white,
    bold: true,
    fontSize: 12,
    fontFace: FONT,
    align: "center",
    valign: "middle",
  };
  const cellOpts = { fontSize: 12, fontFace: FONT, color: C.text, valign: "middle" };
  s.addTable(
    rows.map((r, ri) =>
      r.map((txt, ci) => ({
        text: txt,
        options: ri === 0 ? hdrOpts : ci === 0 ? { ...cellOpts, bold: true, align: "center" } : cellOpts,
      }))
    ),
    {
      x: 0.6,
      y: 3.0,
      w: 12.1,
      colW: [1.6, 4.4, 6.1],
      border: { pt: 0.5, color: C.lightGray },
      rowH: [0.42, 0.5, 0.5, 0.5, 0.5, 0.55],
    }
  );
  addSourceNote(s, "docker-compose.middleware.yml 绑定 127.0.0.1；密钥 ~/.qwenpaw.secret/middleware.env");
})();

// ═══════════════════════════════════════════════════════
// SLIDE 12 – Demo entry
// ═══════════════════════════════════════════════════════
(function slide12() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "演示入口：Console 下拉四个中文助手，按场景提问", 20);

  const demos = [
    { t: "Excel问答", q: "这个损坏表.xlsx 是不是坏了  /  乱码表示例.csv 是什么编码  /  超大表示例.xlsx 要不要分块" },
    { t: "多模态文件", q: "逾期90天认定标准  /  表格里的经营贷款利率  /  柱状图数值（走「看图作答」analyze_page）" },
    { t: "运营助手", q: "我的 token（内核账本）  /  今天调用量怎么样  /  哪个工具用得最多  /  不要问「失败率」" },
    { t: "报告可视化", q: "用分行业务.json 生成交叉表 + 五类图 docx，标题「顺德农商行 2025Q3 零售业务报告」" },
  ];
  demos.forEach((d, i) => {
    const y = 1.05 + i * 1.25;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.6,
      y,
      w: 12.1,
      h: 1.12,
      fill: { color: C.offWhite },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.6,
      y,
      w: 0.08,
      h: 1.12,
      fill: { color: C.gold },
    });
    s.addText(d.t, {
      x: 0.95,
      y: y + 0.12,
      w: 11.5,
      h: 0.32,
      fontSize: 15,
      fontFace: FONT,
      bold: true,
      color: C.text,
      margin: 0,
    });
    s.addText(d.q, {
      x: 0.95,
      y: y + 0.5,
      w: 11.5,
      h: 0.48,
      fontSize: 13,
      fontFace: FONT,
      color: C.textLight,
      margin: 0,
    });
  });
  addSourceNote(s, "本机 http://127.0.0.1:5173/  ·  公网 https://shunde-poc.harness-agent.app/chat");
})();

addArchSlide(
  "L1 / L2 / L3：skill列表摘要 → skill → mcp列表namespace前缀 → 详细mcp → 文件摘要 → 文件详情",
  "l123-chain.png",
  21,
  "降低完成时间、提高准确率与效率；前缀一致性提高缓存命中率，省 token，提高 ROI"
);

addArchSlide(
  "前缀一致性提高缓存命中率，从而省 token、提高 ROI",
  "prefix-cache-roi.png",
  22,
  "L1 skill列表摘要每轮相同；详细mcp / 文件摘要 / 文件详情后置。cache_read_tokens 记账，不编造命中百分比。"
);

addArchSlide(
  "新版本比 2.0.0 好：有缓存命中率，Files 可查看、操作、生成、下载；旧版是黑盒",
  "files-vs-blackbox.png",
  23,
  "2.2.2b1 Console Files；2.0.0 没有 Files 页，只能看聊天窗口。"
);

addArchSlide(
  "Excel问答任务分布：skill列表摘要 → excel_guard__ → 文件摘要 → 文件详情",
  "excel-task-map.png",
  24,
  "检测损坏表 / 识别编码 / 描述表结构（摘要）→ 表转 Markdown、inspect（详情）→ pandas"
);

addArchSlide(
  "多模态文件任务分布：skill列表摘要 → kb_qa__ → 文件摘要 → 文件详情",
  "kb-task-map.png",
  25,
  "解析文档 / 检索知识（摘要）→ 看图作答 analyze_page（详情）"
);

addArchSlide(
  "运营助手任务分布：skill列表摘要 → ops_data__ → 文件摘要 → 文件详情",
  "ops-task-map.png",
  26,
  "列出埋点文件（摘要）→ 最近事件（详情）；无文件则暂无埋点"
);

addArchSlide(
  "报告可视化任务分布：skill列表摘要 → report_visualizer__ → 文件摘要 → 文件详情",
  "report-task-map.png",
  27,
  "交叉表（摘要）→ 生成 Word 报告（详情）；Files 页可下载 docx"
);

// ═══════════════════════════════════════════════════════
// SLIDE 28 – optimization directions
// ═══════════════════════════════════════════════════════
(function slideOpt() {
  const s = pres.addSlide();
  s.background = { color: C.white };
  addContentHeader(s, "四个助手的优化方向（已落到 SKILL.md / MCP namespace）", 28);

  const opts = [
    { t: "Excel问答", d: "L1 只留触发词。L2 给 excel_guard__ mcp列表。L3 先 describe 文件摘要，再 markdown/inspect 文件详情，最后 pandas。禁止整表进第一轮。" },
    { t: "多模态文件", d: "L1 短目录。L2 kb_qa__ 六工具列表。L3 先 parse/search 文件摘要，精确数字再 analyze_page 文件详情。表格合计仍交 Excel。" },
    { t: "运营", d: "L1 短目录。L2 ops_data__ 三工具。L3 先 list_telemetry_files 文件摘要，再 recent_events 文件详情。无 JSONL 不编造。" },
    { t: "报告可视化", d: "L1 短目录。L2 report_visualizer__ 七工具。L3 先交叉表文件摘要，再 render_docx 文件详情。产物走 Files 查看/下载。" },
  ];
  opts.forEach((o, i) => {
    const y = 1.0 + i * 1.35;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y, w: 12.2, h: 1.22, fill: { color: C.offWhite } });
    s.addText(o.t, {
      x: 0.8, y: y + 0.1, w: 11.7, h: 0.32,
      fontSize: 16, fontFace: FONT, bold: true, color: C.navy, margin: 0,
    });
    s.addText(o.d, {
      x: 0.8, y: y + 0.48, w: 11.7, h: 0.62,
      fontSize: 13, fontFace: FONT, color: C.textLight, margin: 0,
    });
  });
  addSourceNote(s, "落地：poc/skills/*/SKILL.md 渐进加载合同 + poc/config/mcp-*.json namespace 字段。");
})();

// ═══════════════════════════════════════════════════════
// SLIDE 29 – Closing
// ═══════════════════════════════════════════════════════
(function slide13() {
  const s = pres.addSlide();
  s.background = { color: C.navyDark };
  goldBar(s);

  s.addText("一句话", {
    x: 0.8,
    y: 1.4,
    w: 11.5,
    h: 0.35,
    fontSize: 14,
    fontFace: FONT,
    color: C.gold,
    charSpacing: 2,
    margin: 0,
  });
  s.addText("L1/L2/L3 渐进加载 + 2.2.2b1 Files/缓存命中率：比 2.0.0 黑盒更省 token、更高 ROI。", {
    x: 0.8,
    y: 1.9,
    w: 11.7,
    h: 1.3,
    fontSize: 26,
    fontFace: FONT,
    bold: true,
    color: C.white,
    margin: 0,
  });

  const closes = [
    { t: "Excel", d: "excel_guard__ 先摘要后详情" },
    { t: "知识库", d: "kb_qa__ 先检索再看图" },
    { t: "运营", d: "ops_data__ 先列文件再事件" },
    { t: "报告", d: "docx 可在 Files 下载" },
  ];
  closes.forEach((c, i) => {
    const x = 0.8 + i * 3.05;
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y: 3.6,
      w: 2.9,
      h: 1.5,
      fill: { color: C.blueGray },
    });
    s.addText(c.t, {
      x,
      y: 3.8,
      w: 2.9,
      h: 0.45,
      fontSize: 16,
      fontFace: FONT,
      bold: true,
      color: C.gold,
      align: "center",
      margin: 0,
    });
    s.addText(c.d, {
      x: x + 0.1,
      y: 4.3,
      w: 2.7,
      h: 0.55,
      fontSize: 13,
      fontFace: FONT,
      color: C.white,
      align: "center",
      margin: 0,
    });
  });

  s.addText("顺德农商行 POC  |  2026-09-15  |  宿主 2.2.2b1 vs 2.0.0 黑盒  |  旁路 poc/", {
    x: 0,
    y: 6.9,
    w: 13.3,
    h: 0.3,
    fontSize: 12,
    fontFace: FONT,
    color: C.midGray,
    align: "center",
    margin: 0,
  });
})();

pres.writeFile({ fileName: path.join(__dirname, "顺德POC四助手架构.pptx") })
  .then(() => console.log("wrote 顺德POC四助手架构.pptx"))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });

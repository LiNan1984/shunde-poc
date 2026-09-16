# vps-mem-watch — 顺德 VPS 内存监控

监控 `root@72.60.193.189` 的内存水位和关键进程，内存膨胀时立即提醒用户。支持两种模式：**一次性体检**和**后台持续监控**。

## 硬性规则

1. **密码绝不写入任何文件**（包括本 skill、脚本、临时文件）。密码只来自用户在当前会话中提供的内容（如 `/goal` 参数或对话原文）；用户没提供就先问。
2. SSH 必须用 ControlMaster 复用（`-o ControlMaster=auto -o ControlPath=/tmp/.ssh-cm-%r@%h -o ControlPersist=600`）。新建连接频繁会触发服务器限流。
3. 用 `sshpass` 传密码时固定加 `-o PubkeyAuthentication=no -o PreferredAuthentications=password`，否则先试公钥浪费认证次数导致 Permission denied。
4. 监控循环每 60s 一轮即可（远端 SSH，别更快）。

## 服务器背景（解读监控结果时用）

- 4 核 / 15Gi 内存 / swap 2G（**swap 常年 100% 占满是常态**，不构成告警）
- 内存大户：shunde-poc 的 qwenpaw（~600MB 常态）、resume-es 容器（~1GB）、shunde-poc-es 容器（~1GB）、hermes 系列（~1GB）、hiclaw-manager、kube-apiserver
- **历史事故模式**：`kb_ingest_one.py`（知识库 PDF 入库）解析大文件时 RSS 无上限增长，实测冲到 5GB（2026-09-15，CMF 报告）。它是主要盯防对象
- 结论基线：available ≥ 5GB 健康；< 2GB 危险（会 OOM 杀进程，最可能砸中 ES 或 shunde-poc）

## 模式一：一次性体检（默认）

用户说"看下服务器内存 / 体检 / 现在状态"时执行。密码变量从会话取：

```bash
PW='<从会话取>'
sshpass -p "$PW" ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no \
  -o PreferredAuthentications=password \
  -o ControlMaster=auto -o ControlPath=/tmp/.ssh-cm-%r@72.60.193.189 -o ControlPersist=600 \
  root@72.60.193.189 'bash -s' <<'REMOTE'
echo "== 内存 =="
free -h
echo "== swap =="
free -m | awk '/^Swap:/{printf "%dMB used / %dMB\n", $3, $2}'
echo "== 内存 TOP 8 进程 =="
ps aux --sort=-rss | awk 'NR<=9 && $6/1024>=50 {printf "%8.0fMB  %s %s %s\n", $6/1024, $1, $11, $12}'
echo "== kb_ingest 检查 =="
ps aux | grep -E "kb_ingest|ingest_one" | grep -v grep | awk '{printf "⚠️ 入库任务运行中: PID %s, RSS %.0fMB\n", $2, $6/1024}' || true
REMOTE
```

解读时给出：available、谁在吃内存、有没有入库任务在膨胀，并与上面"基线"对照，明确说**健康 / 需注意 / 危险**。

## 模式二：后台持续监控

用户说"盯着内存 / 持续监控 / 膨胀了告诉我"时，用 **Monitor 工具**（不是 cron）起一个后台 watch。命令模板（阈值默认：available < 1800MB 或单个进程 RSS > 3000MB，可按用户要求调）：

```bash
PW='<从会话取>'
REMOTE='
    avail=$(free -m | awk "/^Mem:/{print \$7}")
    top_rss=$(ps aux --sort=-rss | awk "NR==2{printf \"%.0f\", \$6/1024}")
    top_cmd=$(ps aux --sort=-rss | awk "NR==2{print \$11, \$12}")
    [ "$avail" -lt 1800 ] && echo "ALERT 可用内存不足: ${avail}MB（阈值1800MB），最大进程 $top_cmd ${top_rss}MB"
    [ "$top_rss" -gt 3000 ] && echo "ALERT 单进程膨胀: $top_cmd 占 ${top_rss}MB（阈值3000MB），当前可用 ${avail}MB"
'
while true; do
  out=""
  for attempt in 1 2; do
    out=$(sshpass -p "$PW" ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no -o PreferredAuthentications=password -o ControlMaster=auto -o ControlPath=/tmp/.ssh-cm-%r@72.60.193.189 -o ControlPersist=600 root@72.60.193.189 "$REMOTE" 2>/dev/null) && break
    out=""
    [ "$attempt" -eq 1 ] && sleep 10
  done
  if [ -z "$out" ] && ! sshpass -p "$PW" ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no -o PreferredAuthentications=password -o ControlPath=/tmp/.ssh-cm-%r@72.60.193.189 root@72.60.193.189 true 2>/dev/null; then
    out="ALERT SSH 连接失败（已重试，服务器不可达或限流）"
  fi
  [ -n "$out" ] && echo "$out"
  sleep 60
done
```

Monitor 参数：

- `description`: "顺德VPS内存告警(available<1800MB或单进程>3000MB)"
- `timeout_ms`: 按用户预期的盯守时长给（如盯到某任务跑完给 3600000）；没说就用 `persistent: true`，并告诉用户用 /tasks 或让我停
- 事件到达时：立即向用户转述告警内容；如果用户可能已离开（告警距上次交互较久），同时用 **PushNotification** 推送（内容含 MB 数和进程名，<200 字符）

### 监控循环的覆盖性要求（勿省略）

- **SSH 选项必须内联写出，绝不能用 `$SSHOPTS`/`$CM` 变量展开**：本机 shell 是 zsh，默认不做单词拆分，`ssh $SSHOPTS` 会把整串选项当成一个参数报 "keyword xxx extra arguments"（2026-09-15 踩过，导致监控全程误报 SSH 失败）
- **告警必须带状态记忆（`PREV` 变量），只在状态变化时输出**：进入告警报一次、恢复时报"恢复: …"、持续告警中不重复刷屏（2026-09-15 踩过：qmd 膨胀期间每 60s 复报同一条，刷了十几条）。远端脚本统一输出 `STATE=ALERT|<msg>` 或 `STATE=OK|<msg>`，本地循环比对 PREV 决定是否输出
- SSH 失败必须重试后再报（脚本已含：重试 1 次间隔 10s，重试和探活都失败才发 SSH 告警）——不能静默，也不能单次失败就报
- 告警只在跨阈值瞬间报一次是理想，但脚本每 60s 重复报同一条也可接受；若用户嫌吵，加状态记忆只报变化（`prev` 变量比对）

## 模式三：停止监控

用户说"别盯了/停止监控"时：对之前起的 Monitor 用 TaskStop 停掉，并确认。不要主动清理 ControlMaster socket（10 分钟自动过期）。

## 告警后的处置建议（向用户汇报时按需给出）

- 入库任务膨胀：等它跑完通常自愈（实测跑完回落），但可用内存 < 1.5GB 时建议问用户是否杀任务（杀 PID 前必须用户确认）
- 危险水位：候选止血手段——`docker stop resume-es`（省 1GB）、杀 kb_ingest、`pm2 stop` 不活跃任务；**都先列出来让用户选，不擅自杀**

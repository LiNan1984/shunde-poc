# P4 部署优化方案预研（/health + 镜像精简）

**日期：** 2026-03-22  
**基于：** QwenPaw v2.0.0 deploy/Dockerfile

---

## 现状确认

### 1. /health 端点
- **现状：** 无 `/health` 端点
- **已有：**
  - `GET /api/version` → `{"version": "x.x.x"}`（无需鉴权）
  - `GET /api/doctor/runtime` → Python 环境信息（需鉴权）
- **位置：** `QwenPaw/src/qwenpaw/app/_app.py` 第 858-872 行
- **POC 验收要求：** `GET /health` 返回 200

### 2. 镜像体积
Dockerfile 当前包含（全部在一层 runtime 镜像中）：

| 组件 | 用途 | POC 是否必需 |
|------|------|-------------|
| Node.js slim 基础镜像 | 运行时（不止构建） | ❓ 可能仅需 Python |
| XFCE4 + xvfb + dbus | 桌面环境（coding 模式浏览器） | ⚠️ POC 演示可能需要 |
| Chromium + 依赖库 | Playwright 浏览器自动化 | ⚠️ 视演示场景 |
| build-essential + libssl-dev | 编译依赖 | ❌ 运行时不需要 |
| vim + git + curl | 工具 | ❌ 可裁剪 |
| supervisor | 进程管理 | ⚠️ 多进程需要 |
| 全量 Python 包 | QwenPaw 全部功能 | ⚠️ 可按需裁剪 |

**估计体积：** 1.5GB ~ 2GB+（Node base ~300MB + XFCE ~200MB + Chromium ~300MB + Python deps ~500MB + 其他）

---

## 方案

### 方案 A：旁路补丁（推荐，不 fork 内核）
原则：沿用 HANDOFF 的「不改 QwenPaw 内核」策略。

#### /health 端点
通过插件机制或启动时挂载路由：
- 方案 A1：使用 QwenPaw 的 plugin 系统注入路由（优先）
- 方案 A2：启动前 patch `_app.py`（shell 脚本 sed 注入）
- 方案 A3：在容器入口用 sidecar / nginx 反代增加 `/health`

```python
# 概念：health 插件
from fastapi import FastAPI

@app.get("/health")
def health_check():
    return {"status": "ok"}
```

#### 镜像精简
- 构建 multi-stage：保留 console-builder，将 Python 运行时迁移到 `python:slim`
- 移除 XFCE（POC 若不需要桌面模式）
- 用 `--no-install-recommends` 替代 `apt-get install -y`
- 仅保留 POC 必需的 Python 依赖组
- 目标：< 500MB

### 方案 B：fork 修改
- 直接修改 `_app.py` 加 `/health`
- 重写 Dockerfile
- 风险：后续 QwenPaw 升级需 rebase

---

## 下一步

1. 确认 POC 演示是否需要 Coding Mode / 浏览器自动化（决定 Chromium 去留）
2. 确认是否用 plugin 系统（先读 plugin 文档）
3. 制作 POC 专用 Dockerfile（poc/deploy/Dockerfile.poc）
4. 本地构建测试体积

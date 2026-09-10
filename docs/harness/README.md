# HARNESS 三方案讲义

为评委准备的"可讲清"讲义集合，对应交接清单任务 F：场景 ⑥ HARNESS（压缩 / 记忆 / 沙箱方案阐述）。

| 讲义 | 一句话要点 |
|------|----------|
| [01-context-compression.md](01-context-compression.md) | Doom-loop 截断 + Reme 记忆压缩 + POC 工具层 chunk/流式采样三层联动。 |
| [02-long-term-memory.md](02-long-term-memory.md) | BaseMemoryManager 抽象 + Dummy/ReMe/ADBPG/AgentMD 四种后端；任务 C 将启用 ADBPG。 |
| [03-sandbox.md](03-sandbox.md) | 宿主 OS sandbox + POC 旁路（`O_NOFOLLOW`+openat+`POC_WORKSPACE=/` 拒绝）的双层防御；带攻击回归测试。 |

## 写作原则

- **每个技术断言都引用 QwenPaw v2.0.0 源码**（`QwenPaw/<相对路径>:<行号>`）或 POC 代码路径。
- **演示剧本写命令**，不用"打开 GUI 点 XX"模糊话术（GUI 步骤单独标"待人工"）。
- **不写本机绝对路径**，配置一律 `<REPO_ROOT>` 占位符。
- **不复述 QwenPaw 源码细节**——只讲机制和调参锚点，避免讲义过期。
- **不写虚构数据**：所有 fixture 路径、阈值都从代码实测得到。

## 与交接清单的对应

详见 [`../AI待办交接清单.md`](../AI待办交接清单.md) 第三节任务 F。本目录是任务 F 的最终交付。
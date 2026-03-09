# Prosona Agent 文档

本目录为 Prosona Agent 的架构与协议说明。

## Quick Start

```python
from agentickit.prosonaagent.agent import (
    create_handler_registry,
    create_middleware_registry,
    create_prosona_agent,
)
from agentickit.prosonaagent.aom import (
    RootMiddleware, ProjectMiddleware, ActivityMiddleware, SCOMiddleware,
)

# 1. 创建 Handler 注册表（注册业务 Handler）
handler_registry = create_handler_registry(
    task_handlers=[DrillGuideHandler(), DrillDeductionHandler(), ...],
)

# 2. 创建 Middleware 注册表（注册 AOM 四层 Middleware）
middleware_registry = create_middleware_registry(
    root_middleware=RootMiddleware,
    task_middlewares=[ProjectMiddleware, ActivityMiddleware, SCOMiddleware],
)

# 3. 创建 Agent（返回 compiled graph 与 root middleware）
graph, middleware = create_prosona_agent(
    system_prompt=SYSTEM_PROMPT,
    middleware_registry=middleware_registry,
    handler_registry=handler_registry,
)
```

## Key Concepts

| 概念 | 说明 |
|------|------|
| **TaskMiddleware** | 机制中枢。管理任务生命周期（abefore / aafter / ainterrupt / arecover）、子 Graph 缓存、内置工具（start_task / end_task / recover_task）。每层 Middleware（Root / Project / Activity / SCO）继承 TaskMiddleware 并注册到 MiddlewareRegistry。 |
| **TaskHandler** | 业务逻辑扩展点。按 task name 注册到 HandlerRegistry，提供生命周期钩子（abefore / aafter / aafter_task 等）、自定义 tools 和 state_schema。 |
| **HandlerRegistry** | `name → TaskHandler` 映射。初始化时自动注册 `__root__` 和 `general` 默认 Handler。查找回退顺序：name → task_group_name → general。 |
| **MiddlewareRegistry** | `task_group_name → Middleware class` 映射。用于子 Graph 构建时按 task_group_name 取 Middleware 类。 |
| **TaskState** | 框架级状态 TypedDict。核心字段：`id`、`name`、`status`、`params`、`sub_tasks`、`result`（结果 Dict）、`mode`（start/recover）。 |
| **result** | `Dict[str, Any]`，任务结束时的结果数据，可含 `summary` / `reason` / `next_intent` 等字段。替代旧的 `summary` 和 `interrupt_reason`。 |

## Handler 编写示例

下面以一个简单的业务 Handler（例如 `drill-guide`）为例，展示**最常用的写法模式**。

```python
from typing import Any, Dict, List

from agentickit.prosonaagent.core import TaskHandler, TaskState


class DrillGuideState(TaskState):
    """可选：为该 Handler 定义专属状态（在基础 TaskState 上扩展字段）"""

    # 这里可以扩展自己的字段，例如：
    current_step: int | None = None


class DrillGuideHandler(TaskHandler[DrillGuideState]):
    # 1. Handler 名称：用于 HandlerRegistry 查找与路由
    name = "drill-guide"

    # 2. 绑定专属 state_schema（不需要时可省略，默认 TaskState）
    state_schema = DrillGuideState

    # 3. 可选：声明需要的技能/工具
    skills = ["drill_guide_skill"]
    tools: List[Any] = []  # 也可以在这里挂自定义 tools

    async def abefore(
        self,
        state: DrillGuideState,
        runtime,
    ) -> Dict[str, Any] | None:
        """任务启动时执行（如：生成开场话术、初始化步骤）"""
        messages = [
            {
                "role": "assistant",
                "content": "好的，我们开始进行本次练习讲解。",
            }
        ]
        # 只返回“增量字段”，由框架自动与原 state merge
        return {
            "messages": messages,
            "current_step": 1,
        }

    async def aafter(
        self,
        state: DrillGuideState,
        runtime,
    ) -> Dict[str, Any] | None:
        """任务正常结束时执行，可根据 result 做收尾"""
        result = state.get("result") or {}
        summary = result.get("summary") or "本次练习已结束。"

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"总结一下：{summary}",
                }
            ]
        }
```

将 Handler 注册到 `HandlerRegistry`：

```python
from agentickit.prosonaagent.agent import create_handler_registry

from .handlers import DrillGuideHandler


handler_registry = create_handler_registry(
    task_handlers=[
        DrillGuideHandler(),
        # 这里可以继续添加其他业务 Handler
    ],
    # 可选：root_handler=CustomRootHandler(),
)
```

> **注意**：
> - Handler 的所有生命周期方法签名统一为 `(state, runtime)`（子任务相关为 `(state, runtime, ...)`），并且**只需要返回“增量字段”**，由框架负责与原始 state merge。
> - 当前任务的业务参数通过 `state.get("params")` 获取，结束结果通过 `state.get("result")` 获取。
> - 子任务结果通过 `aafter_task` / `ainterrupt_task` 的 `sub_state.get("result")` 读取，父任务可以在此进行编排。

## AOM 四层架构

| 层级 | Middleware | task_group_name | sub_task_group_name | 职责 |
|------|-----------|----------------|--------------------|----|
| Level 0 | RootMiddleware | `__root__` | `project` | 会话级：提取 projectId，注入 start_task("project") |
| Level 1 | ProjectMiddleware | `project` | `activity` | 项目级：加载 project/modules/activities，注入项目上下文 |
| Level 2 | ActivityMiddleware | `activity` | `sco` | 活动级：加载 activity/sco_list，发送 activity-lifecycle |
| Level 3 | SCOMiddleware | `sco` | — | SCO 级：加载 SCO 内容/历史，调用 start_sco/end_sco，发送 sco-lifecycle。`allow_sub_tasks=False` |

## 文档索引

| 文档 | 说明 |
|------|------|
| [architecture_agent_mechanism.md](./architecture_agent_mechanism.md) | Agent 机制总览：MiddlewareRegistry/HandlerRegistry、TaskMiddleware、TaskState 设计、SubGraph Cache、生命周期与内置工具、AOM 四层扩展。 |
| [protocol_a2a_biz_data.md](./protocol_a2a_biz_data.md) | A2A 业务数据消息协议：Activity 生命周期（§1）、SCO 生命周期（§2）、Activity 介绍（§3）、SCO 内容展示（§4）。 |

代码结构入口：`agentickit/prosonaagent/`，其中 `core/` 为框架层（`core/handler/`、`core/middleware/`、`core/tools/`），`aom/` 为 AOM 业务适配层（`aom/handler/`、`aom/middlewares/`、`aom/tools/`），`utils/` 为工具函数。

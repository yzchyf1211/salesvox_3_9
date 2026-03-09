# ACE（Agentic Context Engineering）引入方案

> 暂存，后续优化时参考。

## 背景

ACE 是 Stanford/Berkeley/SambaNova 2025 年提出的框架（arXiv:2510.04618），核心理念是将 Agent 的 context（system prompt、task instructions、agent memory）视为**可演化的 Playbook**——通过 Generator → Reflector → Curator 三阶段管道，以增量 delta 更新而非全量重写来优化 context，防止 brevity bias 和 context collapse。

## 当前 Prosona Agent 已有的 Context Engineering 能力

| 能力 | 现有实现 |
|------|---------|
| 分层上下文组装 | AOM 四层 middleware 逐层注入 project/activity/SCO context |
| Task Prompt 加载 | `_load_task_prompt` 按 task_name 加载 TASK.md |
| Skill System Prompt | `ModelEnhanceMiddleware` 在每次 model call 时注入 skill 概览（名称+描述+使用指引） |
| Skill Context 注入 | `abefore` 中注入 skill 完整内容（body），由 `_create_skills` 合并 middleware + handler skills |
| 可压缩 Message | `_compressible_message` + `COMPRESSIBLE_KEY` 标记 |
| 动态工具集 | handler.tools 按任务类型注册不同工具 |

## 引入方向

### 方向 1: Task Prompt 演化（Offline ACE）

当前 TASK.md 是静态文件。引入 ACE 后：

```
TaskMiddleware._load_task_prompt(task_name)
  └── 原来: 读取静态 TASK.md
  └── 演化: 读取 Playbook（结构化、带 evidence counter 的策略集）
```

Playbook 格式示例：
```markdown
## STRATEGIES
[str-001] helpful=12 harmful=0 :: "当用户偏离剧本时，先确认意图再引导回主线"
[str-002] helpful=8 harmful=2 :: "演绎开场应先设定场景，再引入角色"
```

在 TaskHandler 上新增 lifecycle hook `areflect(state, runtime, trajectory)`，由 Middleware 在 `aafter` 后调用。

### 方向 2: Context Compaction（Online ACE）

当前 `_compressible_message` 只是标记，没有实际压缩逻辑。引入 ACE 的增量压缩：

```python
class ContextCurator:
    """Manages context window via delta updates."""

    def compact(self, messages, budget) -> List[AnyMessage]:
        """Preserve high-signal tokens, summarize low-signal ones."""

    def update_playbook(self, trajectory, feedback) -> PlaybookDelta:
        """Generate incremental playbook updates from execution feedback."""
```

可作为 `awrap_model_call` 的一环，在每次模型调用前做 context compaction。

### 方向 3: Handler 级 Memory（Structured Note-Taking）

在 TaskHandler 上引入 persistent memory，跨 session 学习：

```python
class TaskHandler:
    async def aget_playbook(self, state, runtime) -> str:
        """Load evolved playbook for this task type."""

    async def areflect(self, state, runtime, result) -> PlaybookDelta:
        """Reflect on execution and propose playbook updates."""
```

## 建议引入路径

**Phase 1（最小切入）**：在 `TaskMiddleware.abefore` 中，在 `_load_task_prompt` 之后，增加 Playbook 注入点。Handler 可选实现 `aget_playbook()` 返回动态策略，与静态 TASK.md 拼接。不改变现有接口。

**Phase 2（反思闭环）**：在 `TaskMiddleware.aafter` 之后，增加可选的 `areflect` 调用。Reflector 分析执行轨迹（messages），Curator 更新 Playbook。Playbook 持久化到外部存储。

**Phase 3（Context Compaction）**：在 `awrap_model_call` 中引入 context budget 管理，用 ACE 的 delta-update 机制替代简单的消息截断。

## 参考

- [ACE Paper (arXiv:2510.04618)](https://arxiv.org/abs/2510.04618)
- [ACE GitHub](https://github.com/ace-agent/ace)
- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Manus: Context Engineering for AI Agents](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)

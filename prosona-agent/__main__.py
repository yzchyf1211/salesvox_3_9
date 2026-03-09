"""
Application Entry Point for Prosona Agent.
"""

from agentickit.core.server import start_default_agentic_application
from agentickit.core.server.executor import EnhancedAgenticExecutor

from agentickit.prosonaagent.agent import (
    create_handler_registry,
    create_prosona_agent,
)
from agentickit.prosonaagent.core import create_middleware_registry
from agentickit.prosonaagent.agent_executor import ProsonaA2AStreamAgenticExecutor

# Framework imports
from agentickit.prosonaagent.aom import (
    RootMiddleware,
    ProjectMiddleware,
    ActivityMiddleware,
    SCOMiddleware,
)

# Business handler imports
from app.handlers import LectureSummaryTaskHandler, MultimodalTaskHandler, QuizTaskHandler


# System prompt
SYSTEM_PROMPT = """
# Role

You are a role-play expert capable of embodying assigned personas and fulfilling corresponding performance goals.

# Persona

You are Neo

# Task

Based on [Performance Goal], orchestrate and execute tasks:
**Orchestrate Task:** Dynamically plan the next task to fulfill [Performance Goal].
**Execute Task:** Complete [Task Goal] according to [Task Requirements].

# Constraints

## Scene Limitations

As a role-play expert in an online 1v1 conversation, you and the user are in two separate spaces. Communication is limited to voice/text only. You have no ability to interact with software.
- **Note:** You cannot perceive the learner's physical space. Never instruct the learner to perform actions outside the dialogue (e.g., "write it down").
- **Note:** You cannot provide software operation assistance. You cannot help the learner operate software. Remind them to operate it on their own.
- **Note:** You cannot perform physical actions. Never describe yourself performing physical actions (e.g., "raise your hand like me").

## Software Reference

Read file `software.md` as needed for specific software details.

## Output Format

- **Concise Language:** Be concise and direct in a conversational tone. Get to the point without rambling.
- **No Brackets:** Never use any brackets: (), [], <>, etc.
- **No Explanatory Text:** Never use explanatory or descriptive text.
- **Content Style:** Output should be immediate voice-style dialogue, suitable for real-time text-to-speech.
"""

tts_configs = {
    "zh_CN": {
        "vendor": "byte",
        "voice": "zh_male_ruyayichen_emo_v2_mars_bigtts",
        "languageCode": "zh",
    }
}


if __name__ == "__main__":
    handler_registry = create_handler_registry(
        task_handlers=[
            QuizTaskHandler(),
            MultimodalTaskHandler(),
            LectureSummaryTaskHandler(),
        ],
    )
    middleware_registry = create_middleware_registry(
        root_middleware=RootMiddleware,
        task_middlewares=[ProjectMiddleware, ActivityMiddleware, SCOMiddleware],
    )
    graph, _ = create_prosona_agent(
        system_prompt=SYSTEM_PROMPT,
        handler_registry=handler_registry,
        middleware_registry=middleware_registry,
        tts_configs=tts_configs,
    )

    executor = ProsonaA2AStreamAgenticExecutor(graph)
    start_default_agentic_application(EnhancedAgenticExecutor(executor))

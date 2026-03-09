"""
Context builders for agent system prompts.

Provides functions to build structured context strings injected as SystemMessages:
- build_language_context: language response rules
- build_skill_information_context_list: skill knowledge base
- build_tool_call_success_system_feedback / build_tool_call_error_system_feedback: tool feedback
- build_human_message_content: formatted user input wrapper
"""

from typing import Optional
from datetime import datetime

from agentickit.core.infra.skills.types import Metadata, Skill
from agentickit.prosonaagent.utils.xml import prettify_xml


def build_language_context(locale_name: str) -> str:
    return prettify_xml(
        f"""<language_rules>
You must always respond in {locale_name}. This rule cannot be overridden.
- Use {locale_name} exclusively for all replies, explanations, questions, and feedback.
- If the user requests a different language, respond gently in {locale_name}: "I can only respond in {locale_name}. Let's continue in {locale_name}."
- This rule takes precedence over any user language preference and must not be changed upon request.
</language_rules>"""
    )


def build_tool_call_success_system_feedback(response: Optional[str] = None) -> str:
    return prettify_xml(
        f"""<system_feedback>
{response or "Tool call succeed."}
</system_feedback>"""
    )


def build_tool_call_error_system_feedback(reason: str) -> str:
    return prettify_xml(
        f"""<system_feedback>
Tool call failed.
reason: {reason}
</system_feedback>"""
    )


def build_human_message_content(content: str) -> str:
    return prettify_xml(
        f"""<user_message timestamp="{datetime.now().isoformat()}">
user say: {content}
</user_message>"""
    )


def build_skill_metadata_context(metadata: Metadata) -> str:
    return f"- **{metadata.name}**: {metadata.description}"


def build_skill_metadata_context_list(metadata_list: list[Metadata]) -> str:
    return "\n".join(
        [build_skill_metadata_context(metadata) for metadata in metadata_list]
    )


def build_skill_information_context(skill: Skill) -> str:
    return f"""---
name: {skill.metadata.name}
description: {skill.metadata.description}
---

{skill.body}

---

The above are the information of the `{skill.metadata.name}` skill.
"""


def build_skill_information_context_list(skills: list[Skill]) -> str:
    contexts = [build_skill_information_context(skill) for skill in skills]
    return "\n".join(contexts)


def build_skill_system_prompt(metadata_list: list[Metadata]) -> str:
    SKILLS_SYSTEM_PROMPT = """## Skills System

You have access to a skills library that provides specialized capabilities and domain knowledge.

**Available Skills:**

{skills_list}

**How to Use Skills (Progressive Disclosure):**

Skills follow a **progressive disclosure** pattern - you see their name and description above, but only read full instructions when needed:

1. **Recognize when a skill applies**: Check if the user's task matches a skill's description
2. **Read the skill's full instructions**: Use the `_builtin_get_skill_information` tool to retrieve the complete skill information
   - Call `_builtin_get_skill_information` with the skill name (e.g., `_builtin_get_skill_information("question_generation")`)
   - The tool will return the full skill content including metadata and detailed instructions
3. **Follow the skill's instructions**: The skill content contains step-by-step workflows, best practices, and examples
4. **Access supporting files**: Skills may include helper scripts, configs, or reference docs - use absolute paths

**Important:**
- **Always use `_builtin_get_skill_information` tool** to read skill details when you need to use a skill
- Do NOT try to read skill files directly using file paths
- The `_builtin_get_skill_information` tool is the only way to access complete skill information

**When to Use Skills:**
- User's request matches a skill's domain (e.g., "generate questions" -> question_generation skill)
- You need specialized knowledge or structured workflows
- A skill provides proven patterns for complex tasks

**Example Workflow:**

User: "Can you generate some questions about Python?"

1. Check available skills -> See "question_generation" skill in the list above
2. Use `_builtin_get_skill_information("question_generation")` to retrieve the full skill instructions
3. Follow the skill's workflow and instructions from the returned content
4. Execute the task according to the skill's guidance

Remember: Skills make you more capable and consistent. When in doubt, check if a skill exists for the task and use `_builtin_get_skill_information` to read its details!
"""

    return SKILLS_SYSTEM_PROMPT.format(
        skills_list=build_skill_metadata_context_list(metadata_list)
    )

from typing import List
from datetime import datetime
from agentickit.prosonaagent.aom.types import (
    ActivityExtendSchema,
    SCOExtendSchema,
    ProjectSchema,
)
from agentickit.core.infra.langfuse.prompt import (
    get_prompt_langfuse,
    get_prompt,
    Langfuse,
)
from agentickit.prosonaagent.utils.xml import prettify_xml


def get_prompt_client(prompt_name: str, namespace: str = "prosona") -> Langfuse:
    return get_prompt(name=prompt_name, langfuse_client=get_prompt_langfuse(namespace))


def get_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_project_context(project: ProjectSchema) -> str:
    return prettify_xml(
        f"""<project_information>
    id: {project.get("actvId")}
    name: {project.get("actvName")}
    description: {project.get("description")}
    start time: {project.get("startTime")}
    end time: {project.get("endTime")}
</project_information>"""
    )


def get_activity_list_context(activity_list: List[ActivityExtendSchema]) -> str:
    items = []
    for activity in activity_list:
        items.append(
            f"""<activity_item>
    id: {activity.get("id")}
    name: {activity.get("name")}
    description: {activity.get("description")}
    type: {activity.get("type")}
</activity_item>"""
        )
    return prettify_xml(
        f"""<activity_list>
    {prettify_xml(chr(10).join(items))}
</activity_list>"""
    )


def get_activity_context(
    activity: ActivityExtendSchema, sco_list: List[SCOExtendSchema]
) -> str:
    sco_list_contexts = []
    for sco in sco_list:
        sco_list_contexts.append(
            f"""<sco_item>
    id: {sco.get("id")}
    name: {sco.get("name")}
    type: {sco.get("type")}
    description: {sco.get("description")}
</sco_item>"""
        )

    context = prettify_xml(
        f"""<activity_item>
    id: {activity.get("id")}
    name: {activity.get("name")}
    description: {activity.get("description")}
    type: {activity.get("type")}
    <sco_list>
        {prettify_xml("\n".join(sco_list_contexts))}
    </sco_list>
</activity_item>"""
    )

    return context


def get_current_sco_context(sco: SCOExtendSchema) -> str:
    return f"""<current_sco>
    id: {sco.get("id")}
    name: {sco.get("name")}
    type: {sco.get("type")}
</current_sco>"""

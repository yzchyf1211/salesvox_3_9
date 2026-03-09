from agentickit.core.infra.config.loader import get_config
from agentickit.core.infra.langfuse.prompt import get_prompt, get_prompt_langfuse


def get_task_prompt(
    name: str,
) -> str:
    """Fetch and compile a TASK.md prompt for a task using prompts.tasks.locations config.

    Config shape example in application.toml:

        [[prompts.tasks.locations]]
        id = "prosona"
        namespace = "prosona"
        path = "tasks"
        tasks = ["root", "project", "activity", "sco"]

    Resolution rules:
    - namespace/path are looked up from prompts.tasks.locations
      by matching `name` in the `tasks` list and `id` in prompts.tasks.location_ids.
    - namespace is required; if missing, an error is raised.
    - path defaults to "tasks" if omitted or empty.
    """

    location_ids = get_config("prompts.tasks.location_ids", default=[])
    locations = get_config("prompts.tasks.locations", default=[])

    if not isinstance(locations, list):
        locations = [locations] if locations else []

    namespace = None
    path = None

    for location_id in location_ids or []:
        for loc in locations:
            if not isinstance(loc, dict):
                continue
            if loc.get("id") != location_id:
                continue
            tasks = loc.get("tasks", [])
            if name in tasks:
                namespace = loc.get("namespace", namespace)
                path = loc.get("path", path)
                break

    if namespace is None:
        raise ValueError(
            f"Cannot determine namespace for task '{name}'; "
            "check prompts.tasks.locations.namespace"
        )

    # Default path fallback if config omitted it or left empty.
    if not path:
        path = "tasks"

    base_path = path.rstrip("/")
    client = get_prompt_langfuse(namespace)
    prompt = get_prompt(name=f"{base_path}/{name}/TASK.md", langfuse_client=client)
    return prompt.compile()


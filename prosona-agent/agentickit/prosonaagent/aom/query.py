from typing import Optional

from agentickit.prosonaagent.aom.state import ProjectTaskState
from agentickit.prosonaagent.aom.types import ActivityExtendSchema, SCOExtendSchema


def get_activity_by_activity_id(
    state: ProjectTaskState, activity_id: str
) -> Optional[ActivityExtendSchema]:
    activity_list = state.get("activity_list", [])
    for activity in activity_list:
        if activity.get("id") == activity_id:
            return activity


def get_next_activity_by_activity_id(
    state: ProjectTaskState, activity_id: str
) -> Optional[ActivityExtendSchema]:
    activity_list = state.get("activity_list", [])
    for index, activity in enumerate(activity_list):
        if activity.get("id") == activity_id and index != len(activity_list) - 1:
            return activity_list[index + 1]


def get_sco_by_sco_id(
    state: ProjectTaskState, sco_id: str
) -> Optional[SCOExtendSchema]:
    sco_list = state.get("sco_list", [])
    for sco in sco_list:
        if sco.get("id") == sco_id:
            return sco


def get_next_sco_by_sco_id(
    state: ProjectTaskState, sco_id: str
) -> Optional[SCOExtendSchema]:
    sco_list = state.get("sco_list", [])
    for index, sco in enumerate(sco_list):
        if sco.get("id") == sco_id:
            if index != len(sco_list) - 1:
                return sco_list[index + 1]

"""
AOM State Definitions (AOM Adapter).

This module provides AOM-specific state definitions that extend
the core TaskState with Activity Object Model fields.

State hierarchy:
- RootTaskState (Level 0): project_id only
- ProjectTaskState (Level 1): project-level data (modules, activities)
- ActivityTaskState (Level 2): activity-level data
- SCOTaskState (Level 3): SCO-level data
"""

from typing import Optional, List, TypeVar

from agentickit.prosonaagent.core.middleware.task_state import TaskState
from agentickit.prosonaagent.aom.types import (
    ProjectModuleSchema,
    ActivityExtendSchema,
    SCOExtendSchema,
    SCOSegmentSchema,
)


class RootTaskState(TaskState):
    """
    Root state definition (Level 0).

    Contains only the project_id, set by RootMiddleware.
    """

    project_id: Optional[str]  # Project ID


RootTaskStateT = TypeVar("RootTaskStateT", bound=RootTaskState)


class ProjectTaskState(RootTaskState):
    """
    Project state definition (Level 1).

    Contains project-level information loaded by ProjectMiddleware.
    """

    module_list: List[ProjectModuleSchema]  # All modules in the project
    activity_list: List[ActivityExtendSchema]  # All activities info


ProjectTaskStateT = TypeVar("ProjectTaskStateT", bound=ProjectTaskState)


class ActivityTaskState(ProjectTaskState):
    """
    Activity task state definition.

    Contains activity-level information for activity orchestration.
    """

    # Current activity information
    activity: ActivityExtendSchema  # Current activity
    sco_list: List[SCOExtendSchema]  # SCOs in current activity


ActivityTaskStateT = TypeVar("ActivityTaskStateT", bound=ActivityTaskState)


class SCOTaskState(ActivityTaskState):
    """
    SCO task state definition.

    Contains SCO-level information for individual learning object execution.
    """

    # Current SCO information
    sco: SCOExtendSchema  # Current SCO
    sco_segment_list: List[SCOSegmentSchema]  # Segments of current SCO
    order: int  # Learning attempt number (1st, 2nd, etc.)


SCOTaskStateT = TypeVar("SCOTaskStateT", bound=SCOTaskState)

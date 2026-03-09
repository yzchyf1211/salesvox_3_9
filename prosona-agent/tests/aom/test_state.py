"""Tests for AOM state hierarchy."""

from agentickit.prosonaagent.core.middleware.task_middleware import TaskState
from agentickit.prosonaagent.aom.state import (
    RootTaskState,
    ProjectTaskState,
    ActivityTaskState,
    SCOTaskState,
)


class TestStateHierarchy:
    """TypedDict doesn't support issubclass(); verify via __orig_bases__."""

    def test_root_extends_task_state(self):
        assert TaskState in RootTaskState.__orig_bases__

    def test_project_extends_root(self):
        assert RootTaskState in ProjectTaskState.__orig_bases__

    def test_activity_extends_project(self):
        assert ProjectTaskState in ActivityTaskState.__orig_bases__

    def test_sco_extends_activity(self):
        assert ActivityTaskState in SCOTaskState.__orig_bases__

    def test_full_chain(self):
        """SCOTaskState -> ActivityTaskState -> ProjectTaskState -> RootTaskState -> TaskState via __orig_bases__ chain."""
        def get_ancestors(cls):
            ancestors = set()
            for base in getattr(cls, "__orig_bases__", ()):
                if isinstance(base, type):
                    ancestors.add(base)
                    ancestors.update(get_ancestors(base))
            return ancestors

        chain = get_ancestors(SCOTaskState)
        assert ActivityTaskState in chain
        assert ProjectTaskState in chain
        assert RootTaskState in chain
        assert TaskState in chain


class TestStateFields:
    def test_root_has_project_id(self):
        annotations = RootTaskState.__annotations__
        assert "project_id" in annotations

    def test_project_has_module_and_activity_lists(self):
        annotations = ProjectTaskState.__annotations__
        assert "module_list" in annotations
        assert "activity_list" in annotations

    def test_activity_has_activity_and_sco_list(self):
        annotations = ActivityTaskState.__annotations__
        assert "activity" in annotations
        assert "sco_list" in annotations

    def test_sco_has_sco_and_segments_and_order(self):
        annotations = SCOTaskState.__annotations__
        assert "sco" in annotations
        assert "sco_segment_list" in annotations
        assert "order" in annotations

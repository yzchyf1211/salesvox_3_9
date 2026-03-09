"""
Review workflow 状态定义

最小化的 ReviewState，仅包含 review graph 各节点实际使用的字段。
（从 aitutor-magic-agent ReviewState 精简迁移）
"""

from typing import Dict, List, Optional, Any

from typing_extensions import TypedDict

from langchain_core.messages import AnyMessage

from app.schema.learning_review_schema import ActivityReviewData


class ReviewState(TypedDict, total=False):
    context_id: str
    current_activity: Optional[Dict[str, Any]]
    current_activity_review: Optional[ActivityReviewData]
    messages: List[AnyMessage]
    activity_sco_list: Dict[str, List[Dict[str, Any]]]
    history_qa_sessions: Optional[Dict[str, Any]]
    user_profile: Optional[Dict[str, Any]]
    project_id: Optional[str]
    project_info: Optional[Dict[str, Any]]
    personal_profile_context: Optional[Any]

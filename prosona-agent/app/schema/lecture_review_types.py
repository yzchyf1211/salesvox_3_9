"""
授课报告数据模型

定义授课报告的返回类型
（从 aitutor-magic-agent 直接迁移）
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class LectureReviewModel(BaseModel):
    """授课报告模型"""

    activity_id: str = Field(..., description="活动ID")
    activity_name: str = Field(..., description="活动名称")
    completion_status: int = Field(
        default=0, description="完成状态：0-未开始，1-进行中，2-已完成"
    )

    learning_duration_minutes: float = Field(
        default=0.0, description="学习时长（分钟）"
    )
    learning_duration_formatted: str = Field(
        default="", description="格式化的学习时长"
    )
    start_time: Optional[str] = Field(
        default=None, description="开始时间（ISO格式字符串）"
    )
    end_time: Optional[str] = Field(
        default=None, description="结束时间（ISO格式字符串）"
    )

    interaction_count: int = Field(default=0, description="有效互动次数")

    highlights: List[Dict] = Field(default_factory=list, description="精彩时刻列表")
    learning_suggestions: List[Dict] = Field(
        default_factory=list, description="学习建议列表"
    )
    summary: List[str] = Field(default_factory=list, description="学习总结列表")

    artifact_id: Optional[str] = None
    report_name: Optional[str] = None
    report_title: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

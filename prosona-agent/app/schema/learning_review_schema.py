"""
学习回顾数据模型
（从 aitutor-magic-agent 直接迁移）
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ActivityReviewData(BaseModel):
    """活动回顾数据模型"""

    activity_id: str = Field(..., description="活动ID")
    activity_name: str = Field(..., description="活动名称")
    completion_status: int = Field(
        default=0, description="完成状态：0-未开始，1-进行中，2-已完成"
    )

    learning_duration_minutes: float = Field(
        default=0.0, description="学习时长（分钟）"
    )
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")

    interaction_count: int = Field(default=0, description="有效互动次数")

    highlights: List[Dict] = Field(default_factory=list, description="精彩时刻列表")
    learning_suggestions: List[Dict] = Field(
        default_factory=list, description="学习建议列表"
    )
    summary: List[str] = Field(default_factory=list, description="学习总结列表")

    ai_voice_script: Dict[str, str] = Field(
        default_factory=dict, description="AI老师口播稿"
    )

    review_generation_in_progress: bool = Field(
        default=False, description="回顾是否正在生成中"
    )
    review_generation_completed: bool = Field(
        default=False, description="回顾是否生成完成"
    )

    review_interaction_results: Dict[str, Any] = Field(
        default_factory=dict, description="互动分析结果"
    )
    review_highlights_results: Dict[str, List[str]] = Field(
        default_factory=dict, description="精彩时刻结果"
    )
    review_suggestions_results: Dict[str, List[str]] = Field(
        default_factory=dict, description="学习建议结果"
    )
    review_voice_script_results: Dict[str, Dict[str, str]] = Field(
        default_factory=dict, description="口播稿结果"
    )
    review_duration_results: Dict[str, Any] = Field(
        default_factory=dict, description="时长计算结果"
    )
    review_summary_results: Dict[str, List[str]] = Field(
        default_factory=dict, description="学习总结结果"
    )
    review_score_results: Dict[str, Any] = Field(
        default_factory=dict, description="分数结果"
    )
    review_score_wight_results: Dict[str, Any] = Field(
        default_factory=dict, description="分数权重结果"
    )
    review_overall_summary_results: Dict[str, str] = Field(
        default_factory=dict, description="总体总结结果"
    )
    review_overall_feedback_results: Dict[str, str] = Field(
        default_factory=dict, description="总体反馈结果"
    )

    artifact_id: Optional[str] = None
    report_name: Optional[str] = None
    report_title: Optional[str] = None

    def start_generation(self):
        self.review_generation_in_progress = True
        self.review_generation_completed = False

    def finish_generation(self):
        self.review_generation_in_progress = False
        self.review_generation_completed = True

    def get_formatted_duration(self) -> str:
        if self.learning_duration_minutes < 1:
            return "不足1分钟"
        elif self.learning_duration_minutes < 60:
            return f"{int(self.learning_duration_minutes)}分钟"
        else:
            hours = int(self.learning_duration_minutes / 60)
            minutes = int(self.learning_duration_minutes % 60)
            if minutes > 0:
                return f"{hours}小时{minutes}分钟"
            return f"{hours}小时"

    class Config:
        arbitrary_types_allowed = True

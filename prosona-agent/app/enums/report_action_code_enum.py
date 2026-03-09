from dataclasses import dataclass
from enum import Enum
from typing import List, Dict


@dataclass(frozen=True)
class ReportCodePair:
    """指标代码和动作代码的配对"""
    indicator_code: str
    action_code: str
    description: str


class ReportActionCodeEnum(Enum):
    """报告动作代码枚举，包含indicatorCode和actionCode的对应关系"""
    
    # 学习进展相关
    DRILL_ACHIEVE_PTG = ReportCodePair("goal_achievement", "drill_achieve_ptg", "对练目标达成")
    
    # 评估结果相关 - 授课
    LECTURE_ERROR = ReportCodePair("error_behavior", "lecture_error", "授课错误行为")
    LECTURE_GUIDE = ReportCodePair("error_correction", "lecture_guide", "授课错误修正行为")
    LECTURE_QUIZ_SCORE = ReportCodePair("dimension_evaluation", "lecture_quiz_score", "授课评分项评估结果")
    LECTURE_KNG_STUDY = ReportCodePair("knowledge_mastery", "lecture_kng_study", "知识点掌握情况(授课)")
    LECTURE_SCORE = ReportCodePair("activity_evaluation", "lecture_score", "授课Activity评估结果")
    LECTURE_HIGHLIGHT_CARD = ReportCodePair("highlight_card", "lecture_highlight_card", "授课高光时刻卡片")
    
    # 评估结果相关 - 对练
    DRILL_ERROR_BEHAVIOR = ReportCodePair("error_behavior", "drill_error_behavior", "对练错误行为")
    DRILL_ERROR_CORRECTION = ReportCodePair("error_correction", "drill_error_correction", "对练错误修正行为")
    DRILL_DIM_SCORE = ReportCodePair("dimension_evaluation", "drill_dim_score", "对练评分项评估结果")
    DRILL_KNG_MASTER = ReportCodePair("knowledge_mastery", "drill_kng_mastery", "知识点掌握情况(对练)")
    DRILL_SCORE = ReportCodePair("activity_evaluation", "drill_score", "对练Activity评估结果")
    DRILL_HIGHLIGHT_CARD = ReportCodePair("highlight_card", "drill_highlight_card", "对练高光时刻卡片")
    
    # 学员行为相关
    TUTOR_LECTURE_QUIZ = ReportCodePair("interaction_frequency", "tutor_lecture_quiz", "交互频率-授课问答练习互动")
    TUTOR_LECTURE_ALL_QUIZ = ReportCodePair("interaction_frequency", "tutor_lecture_all_quiz", "演绎中的互动--问答题（所有）")
    TUTOR_QA_EXPLORE = ReportCodePair("active_exploration", "tutor_qa_explore", "主动探索-Q&A主动探索")
    TUTOR_QA_LINK = ReportCodePair("knowledge_connection", "tutor_qa_link", "认知连接-Q&A提及其他章节互动")
    TUTOR_LECTURE_SHARE = ReportCodePair("work_practice", "tutor_lecture_share", "实践应用-授课分享工作经验")
    TUTOR_QA_SHARE = ReportCodePair("work_practice", "tutor_qa_share", "实践应用-Q&A分享工作经验")
    TUTOR_LECTURE_ANSWER = ReportCodePair("answer_behavior", "tutor_lecture_answer", "作答行为-授课答题对话")
    TUTOR_DRILL_ANSWER = ReportCodePair("answer_behavior", "tutor_drill_answer", "作答行为-对练答题对话")
    TUTOR_SCO_SCORE = ReportCodePair("activity_sco_result", "tutor_sco_score", "授课sco结果")

    @property
    def indicator_code(self) -> str:
        """获取指标代码"""
        return self.value.indicator_code
    
    @property
    def action_code(self) -> str:
        """获取动作代码"""
        return self.value.action_code
    
    @property
    def description(self) -> str:
        """获取描述"""
        return self.value.description
    
    def __str__(self) -> str:
        """返回动作代码，保证向后兼容性"""
        return self.action_code
    
    @classmethod
    def get_all_indicator_codes(cls) -> List[str]:
        """获取所有指标代码列表（去重）"""
        return list(set(item.indicator_code for item in cls))
    
    @classmethod
    def get_all_action_codes(cls) -> List[str]:
        """获取所有动作代码列表"""
        return [item.action_code for item in cls]
    
    @classmethod
    def get_actions_by_indicator(cls, indicator_code: str) -> List['ReportActionCodeEnum']:
        """根据指标代码获取对应的动作枚举列表"""
        return [item for item in cls if item.indicator_code == indicator_code]
    
    @classmethod
    def get_action_codes_by_indicator(cls, indicator_code: str) -> List[str]:
        """根据指标代码获取对应的动作代码列表"""
        return [item.action_code for item in cls if item.indicator_code == indicator_code]
    
    @classmethod
    def get_by_action_code(cls, action_code: str) -> 'ReportActionCodeEnum':
        """根据动作代码获取对应的枚举项"""
        for item in cls:
            if item.action_code == action_code:
                return item
        raise ValueError(f"未找到动作代码 {action_code}")
    
    @classmethod
    def get_indicator_by_action_code(cls, action_code: str) -> str:
        """根据动作代码获取对应的指标代码"""
        return cls.get_by_action_code(action_code).indicator_code
    
    @classmethod
    def get_indicator_action_mapping(cls) -> Dict[str, List[str]]:
        """获取指标代码到动作代码列表的映射字典"""
        mapping = {}
        for indicator in cls.get_all_indicator_codes():
            mapping[indicator] = cls.get_action_codes_by_indicator(indicator)
        return mapping
    
    @classmethod
    def get_all_pairs(cls) -> List[tuple[str, str]]:
        """获取所有(指标代码, 动作代码)配对列表"""
        return [(item.indicator_code, item.action_code) for item in cls]

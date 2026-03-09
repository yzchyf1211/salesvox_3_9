from typing import TypedDict, List, Optional, Union, Literal, Any, Dict


class PainPointSchema(TypedDict):
    """痛点数据模型"""

    symptom: str
    problem: str
    impact: str
    outcome: str


class LearnerPainPointSchema(TypedDict):
    """学员痛点数据模型"""

    symptom: str
    problem: str
    impact: str


class TutorProfileSchema(TypedDict):
    """导师个人资料数据模型"""

    background: str
    name: str
    communication_style: str
    position: str
    title: str


class TutorInfoSchema(TypedDict):
    """导师信息数据模型"""

    profile: TutorProfileSchema
    id: str


class ProjectPrinciplesSchema(TypedDict):
    """课程原则数据模型（对应学员理解的课程原则）"""

    framework: str
    philosophy: str
    benefit: str


class ProjectModuleSchema(TypedDict):
    """课程模块数据模型（对应学员理解的课程模块）"""

    moduleDescription: str
    moduleName: str


class ProjectArchitectureSchema(TypedDict):
    """课程架构数据模型（对应学员理解的课程架构）"""

    painPoints: List[PainPointSchema]
    tutors: TutorInfoSchema
    concept: str
    principles: ProjectPrinciplesSchema
    modules: List[ProjectModuleSchema]


class LearnerProfileSchema(TypedDict):
    """学员画像数据模型"""

    painPoints: List[LearnerPainPointSchema]
    targetAudience: str


class CustomDataSchema(TypedDict):
    """自定义数据模型"""

    duration: int
    courseArchitecture: ProjectArchitectureSchema
    learningObjectives: List[str]
    competencyGoals: List[str]
    learnerProfile: LearnerProfileSchema


class ProjectExtensionSchema(TypedDict):
    """活动扩展数据模型"""

    enableMultiShiftTasks: int
    custom: CustomDataSchema
    skinId: str


class ProjectSchema(TypedDict):
    """活动信息API响应模型"""

    actvId: str
    actvName: str
    description: str
    status: int
    startTime: str
    endTime: str
    createTime: str
    createUserId: str
    createUserName: Optional[str] = None
    sourceType: int
    ext: ProjectExtensionSchema


class ActivitySchema(TypedDict):
    """活动内容字典类型"""

    refId: str  # 小节id
    refRegId: str  # actv_aitutor: 授课 actv_drill: 演练
    itemType: int  # 0: 小节 1: 模块
    name: str
    description: str
    ext: str


class ActivityExtendSchema(TypedDict):
    """活动扩展数据模型"""

    id: str
    name: str
    type: str
    description: str
    module_name: str


class SCOSchema(TypedDict):
    """SCO实体数据模型"""

    id: Optional[Union[str, int]]
    itemId: Optional[Union[str, int]]
    parentId: Optional[Union[str, int]]
    refRegId: Optional[str]
    refId: Optional[str]
    itemType: Optional[int]
    scoName: Optional[str]
    scoType: Optional[int]
    status: Optional[int]
    description: Optional[str]
    content: Optional[dict]
    narration: Optional[str]
    ext: Optional[dict]
    items: Optional[List[dict]]


class SCOExtendSchema(TypedDict):
    """SCO扩展数据模型"""

    id: str
    name: str
    type: str
    description: str
    content: Optional[dict]
    blueprint: str
    rule: str
    activity_id: str


class SCOSegmentSchema(TypedDict):
    """SCO内容数据模型"""

    id: str
    scoId: str
    itemType: int
    name: str
    fileId: str
    bgImgUrl: str
    richText: str
    startMills: int
    endMills: int
    contentUrl: str
    script: str
    description: str
    startTime: str
    endTime: str


class AOMCardRecordData(TypedDict):
    """记录内容数据模型"""

    sco_id: str
    order: int  # 第几次学习


class AOMCardReportData(TypedDict):
    """报告内容数据模型"""

    artifact_id: str


class _AOMCardBase(TypedDict):
    """Required card fields."""

    id: str
    name: str
    type: Literal["content", "record", "report"]
    data: dict | AOMCardRecordData | AOMCardReportData


class AOMCard(_AOMCardBase, total=False):
    """Card data model. Required fields are in _AOMCardBase; optional fields are here."""

    description: str    # Card content description for agent context understanding
    ext: Dict[str, Any] # Business extension fields, included as-is in the display message


class SCOChatHistoryStoreSchema(TypedDict):
    """SCO聊天历史数据模型"""

    role: Literal["assistant", "user"]
    name: Optional[str]
    avatar: Optional[str]
    type: Literal["text", "content", "record", "report"]
    text: Optional[str]
    card: Optional[AOMCard]


class SCOChatHistorySchema(TypedDict):
    """SCO聊天历史数据模型"""

    role: Literal["assistant", "user"]
    name: Optional[str]
    avatar: Optional[str]
    type: Literal["text", "content", "record", "report"]
    content: Optional[str | List["SCOChatHistorySchema"] | dict[str, Any]]


ALL_CONTENT_TYPES = ["text", "content", "record", "report"]


class SCOHistoryExtendSchema(TypedDict):
    """SCO历史数据模型"""

    id: str
    order: int
    chat_history: List[SCOChatHistorySchema]

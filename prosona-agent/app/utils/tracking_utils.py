import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from agentickit.core.context.agentic_context_manager import context_saver
from agentickit.core.infra.config.loader import get_config
from app.infra.base_client import BaseAPIClient
from app.schema.tracking_schema import TrackingReportDto, TrackingReportDataDto
from app.enums.report_action_code_enum import ReportActionCodeEnum

logger = logging.getLogger(__name__)

API_BASE_URL = get_config("api.api_base_url")
API_SOURCE = get_config("api.api_source")


class TrackingReportUtils(BaseAPIClient):
    """行为数据上报工具类"""
    
    DEFAULT_TRACKING_ENDPOINT = "/aitutor/facade/tracking/report"
    
    def __init__(self, state=None, token: str = None):
        base_url = API_BASE_URL
        source = API_SOURCE
        if not token:
            token = ""  # 初始化token变量
            try:
                context_id = state.get('context_id') if state else None
                logger.info("👤 TrackingReportUtils init - context_id: %s, state is None: %s", context_id, state is None)
                if context_id:
                    agentic_context = context_saver.load(context_id)
                    logger.info("👤 agentic_context loaded, is None: %s", agentic_context is None)
                    if agentic_context is not None:
                        request_header = agentic_context.get("request_header", {})
                        token = request_header.get("token", "")
                        logger.info("👤 token loaded successfully")
                    else:
                        logger.warning("⚠️ agentic_context is None for context_id: %s", context_id)
            except Exception as e:
                logger.warning(f"⚠️ 用户上下文加载失败: {e}", exc_info=True)
        
        logger.info("👤  base_url: %s, token: %s, source: %s", base_url, token, source)
        super().__init__(base_url, token, source)
        
    def create_tracking_data(
        self,
        data_id: Optional[str] = None,
        data_name: Optional[str] = None,
        text_val: Optional[str] = None,
        text_val1: Optional[str] = None,
        text_val2: Optional[str] = None,
        text_val3: Optional[str] = None,
        int_val: Optional[int] = None,
        int_val1: Optional[int] = None,
        decimal_val: Optional[float] = None,
        decimal_val1: Optional[float] = None,
        enum_val: Optional[str] = None,
        enum_val1: Optional[str] = None,
        id_val: Optional[str] = None,
        id_val1: Optional[str] = None
    ) -> TrackingReportDataDto:
        """
        创建埋点数据项
        
        Args:
            data_id: 数据id或者key(<=50字符)
            data_name: 数据名称(最大长度200，超过会截断)
            text_val: 长文本数据
            text_val1: 长文本数据1
            text_val2: 长文本数据2
            text_val3: 长文本数据3
            int_val: int值
            int_val1: int值1
            decimal_val: decimal值
            decimal_val1: decimal值1
            enum_val: 枚举值
            enum_val1: 枚举值1
            id_val: key or id(<=50字符)
            id_val1: key or id(<=50字符)
            
        Returns:
            TrackingReportDataDto: 埋点数据项
        """
        # 数据名称长度限制处理
        if data_name and len(data_name) > 200:
            data_name = data_name[:200]
            logger.warning(f"数据名称超过200字符，已截断: {data_name}")
        
        # dataId和idVal长度限制检查
        for field_name, field_value in [("data_id", data_id), ("id_val", id_val), ("id_val1", id_val1)]:
            if field_value and len(field_value) > 50:
                logger.warning(f"{field_name}超过50字符: {field_value}")
        
        return TrackingReportDataDto(
            dataId=data_id,
            dataName=data_name,
            textVal=text_val,
            textVal1=text_val1,
            textVal2=text_val2,
            textVal3=text_val3,
            intVal=int_val,
            intVal1=int_val1,
            decimalVal=decimal_val,
            decimalVal1=decimal_val1,
            enumVal=enum_val,
            enumVal1=enum_val1,
            idVal=id_val,
            idVal1=id_val1
        )
    
    def create_tracking_report(
        self,
        project_id: str,
        action_code: str,
        org_id: Optional[str] = None,
        actv_id: Optional[str] = None,
        item_id: Optional[str] = None,
        round_id: Optional[str] = None,
        user_id: Optional[str] = None,
        report_time: Optional[str] = None,
        data_list: Optional[List[TrackingReportDataDto]] = None,
        context_id: Optional[str] = None
    ) -> TrackingReportDto:
        """
        创建埋点上报请求数据
        
        Args:
            project_id: 项目id（必填）
            action_code: 埋点code（必填）
            org_id: 机构id
            actv_id: 活动id
            item_id: 对练：演练id，授课：scoId
            round_id: 轮次，如：单次演练id，一次作答的id
            user_id: 用户id
            report_time: 上报时间，如果为空则使用当前时间
            data_list: 埋点数据列表
            
        Returns:
            TrackingReportDto: 埋点上报请求数据
        """
        if not report_time:
            report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return TrackingReportDto(
            orgId=org_id,
            projectId=project_id,
            actvId=actv_id,
            itemId=item_id,
            roundId=round_id,
            userId=user_id,
            actionCode=action_code,
            reportTime=report_time,
            dataList=data_list or [],
            contextId=context_id
        )
    
    def report_tracking(
        self,
        tracking_data: TrackingReportDto
    ) -> None:
        """
        发送埋点数据上报
        
        Args:
            tracking_data: 埋点上报数据
            
        Returns:
            TrackingReportResponse: 上报响应结果
        """
        try:
            # 将数据转换为字典
            request_data = tracking_data.model_dump(exclude_none=True)
            
            logger.info(f"发送埋点数据上报: {tracking_data.actionCode}")
            logger.debug(f"上报数据: {request_data}")
            
            # 使用BaseAPIClient的统一请求方法
            response_data = self._make_request(
                method="POST",
                endpoint=self.DEFAULT_TRACKING_ENDPOINT,
                payload=request_data
            )
            
            logger.info(f"埋点数据上报成功: {response_data}")
        except Exception as e:
            logger.error(f"埋点数据上报失败: {str(e)}")

    def report_tutor_qa_explore(
        self,
        project_id: str,
        round_id: str,
        behavior_description: Optional[str] = None,
        conversation_record: Optional[str] = None,
        org_id: Optional[str] = None,
        actv_id: Optional[str] = None,
        item_id: Optional[str] = None,
        user_id: Optional[str] = None,
        context_id: Optional[str] = None
    ) -> None:
        """
        上报导师问答探索行为（tutor_qa_explore）
        
        指标: active_exploration
        行为代码: tutor_qa_explore
        
        Args:
            project_id: 项目id
            round_id: 学习id
            behavior_description: 行为描述
            conversation_record: 对话记录
            org_id: 机构id
            actv_id: 活动id
            item_id: scoId等
            user_id: 用户id
            
        Returns:
            None: 上报响应结果
        """
        # 创建数据项
        data_list = []
        if behavior_description or conversation_record:
            data_item = self.create_tracking_data(
                text_val=behavior_description,
                text_val1=conversation_record
            )
            data_list.append(data_item)
        
        # 创建上报请求
        tracking_report = self.create_tracking_report(
            project_id=project_id,
            action_code=ReportActionCodeEnum.TUTOR_QA_EXPLORE.action_code,
            org_id=org_id,
            actv_id=actv_id,
            item_id=item_id,
            round_id=round_id,
            user_id=user_id,
            data_list=data_list,
            context_id=context_id
        )
        
        return self.report_tracking(tracking_report)

    def report_custom_action(
        self,
        project_id: str,
        action_code: str,
        data_items: Optional[List[Dict[str, Any]]] = None,
        org_id: Optional[str] = None,
        actv_id: Optional[str] = None,
        item_id: Optional[str] = None,
        round_id: Optional[str] = None,
        user_id: Optional[str] = None,
        context_id: Optional[str] = None
    ) -> None:
        """
        上报自定义行为数据
        
        Args:
            project_id: 项目id
            action_code: 行为代码
            data_items: 数据项列表，每个元素为字典，包含TrackingReportDataDto的字段
            org_id: 机构id
            actv_id: 活动id
            item_id: scoId等
            round_id: 轮次id
            user_id: 用户id
            
        Returns:
            None: 上报响应结果
        """
        # 创建数据项列表
        data_list = []
        if data_items:
            for item_data in data_items:
                data_item = self.create_tracking_data(**item_data)
                data_list.append(data_item)
        
        # 创建上报请求
        tracking_report = self.create_tracking_report(
            project_id=project_id,
            action_code=action_code,
            org_id=org_id,
            actv_id=actv_id,
            item_id=item_id,
            round_id=round_id,
            user_id=user_id,
            data_list=data_list,
            context_id=context_id
        )
        
        return self.report_tracking(tracking_report)

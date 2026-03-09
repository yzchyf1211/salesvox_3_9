from typing import List, Optional
from pydantic import BaseModel


class TrackingReportDataDto(BaseModel):
    """埋点上报数据项"""
    decimalVal: Optional[float] = None
    decimalVal1: Optional[float] = None
    intVal: Optional[int] = None
    intVal1: Optional[int] = None
    enumVal: Optional[str] = None
    enumVal1: Optional[str] = None
    dataId: Optional[str] = None
    dataName: Optional[str] = None
    idVal: Optional[str] = None
    idVal1: Optional[str] = None
    textVal: Optional[str] = None
    textVal1: Optional[str] = None
    textVal2: Optional[str] = None
    textVal3: Optional[str] = None


class TrackingReportDto(BaseModel):
    """埋点上报请求数据模型"""
    orgId: Optional[str] = None
    projectId: str
    actvId: Optional[str] = None
    itemId: Optional[str] = None
    roundId: Optional[str] = None
    userId: Optional[str] = None
    actionCode: str
    reportTime: Optional[str] = None
    contextId: Optional[str] = None
    dataList: Optional[List[TrackingReportDataDto]] = None

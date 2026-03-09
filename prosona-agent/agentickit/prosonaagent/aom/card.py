from typing import Optional
from agentickit.prosonaagent.aom.types import (
    AOMCard,
    AOMCardRecordData,
    AOMCardReportData,
)


def build_content_card(
    id: str, name: str, content: dict, description: Optional[str] = None
) -> AOMCard:
    return AOMCard(
        id=id,
        name=name,
        type="content",
        data=content,
        description=description,
    )


def build_record_card(
    id: str, name: str, sco_id: str, sco_order: int, description: Optional[str] = None
) -> AOMCard:
    return AOMCard(
        id=id,
        name=name,
        type="record",
        data=AOMCardRecordData(sco_id=sco_id, order=sco_order),
        description=description,
    )


def build_report_card(
    id: str, name: str, artifact_id: str, description: Optional[str] = None
) -> AOMCard:
    return AOMCard(
        id=id,
        name=name,
        type="report",
        data=AOMCardReportData(artifact_id=artifact_id),
        description=description,
    )

"""
产物服务工具
（从 aitutor-magic-agent artifact_utils.py + artifact_client.py 合并迁移）
"""

import json
import logging

from pydantic import BaseModel

from agentickit.core.infra.config.loader import get_config
from app.infra.base_client import BaseAPIClient

logger = logging.getLogger(__name__)

ARTIFACT_API_BASE_URL = get_config("artifact.api_url")
ARTIFACT_APP_KEY = get_config("artifact.app_key")
ARTIFACT_SECRET_KEY = get_config("artifact.secret_key")


class ArtifactCreateResp(BaseModel):
    id: str
    version: int


class ArtifactAPIClient(BaseAPIClient):
    """产物 API 客户端"""

    def createArtifact(
        self, name: str, type: str, sub_type: str, content: str
    ) -> ArtifactCreateResp:
        post_data = {
            "name": name,
            "type": type,
            "sub_type": sub_type,
            "content": content,
        }
        endpoint = "artifacts"
        return ArtifactCreateResp(
            **self._make_request(
                "POST",
                endpoint,
                post_data,
                ext_headers={
                    "appKey": ARTIFACT_APP_KEY,
                    "secretKey": ARTIFACT_SECRET_KEY,
                },
            )
        )


class ArtifactService:
    def __init__(self, token: str, source: str = "501", timeout: int = 30):
        self.api_client = ArtifactAPIClient(
            ARTIFACT_API_BASE_URL, token, source, timeout
        )

    def create_report(self, content, name: str) -> str:
        if hasattr(content, "model_dump"):
            content_dict = content.model_dump()
            content_json = json.dumps(content_dict)
        else:
            content_json = json.dumps(content)
        return self.api_client.createArtifact(
            name=name, type="biz", sub_type="project", content=content_json
        ).id

    def close(self):
        if self.api_client:
            self.api_client.__exit__(None, None, None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

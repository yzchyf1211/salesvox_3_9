import requests
import logging
from abc import ABC
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from agentickit.core.exception import AgenticException

logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    """API客户端基类，提供通用的HTTP请求功能"""

    def __init__(
        self, base_url: str, token: str, source: str = "501", timeout: int = 30
    ):
        """
        初始化API客户端基类

        Args:
            base_url: API基础URL
            token: 认证令牌
            source: 请求来源标识，默认"501"
            timeout: 请求超时时间，默认30秒
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.source = source
        self.timeout = timeout

        # 设置会话和重试策略
        self.session = self._setup_session()

    def _setup_session(self) -> requests.Session:
        """设置HTTP会话和重试策略"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,  # 总重试次数
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
            allowed_methods=["HEAD", "GET", "POST"],  # 允许重试的HTTP方法
            backoff_factor=1,  # 重试间隔倍数
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_headers(self) -> Dict[str, str]:
        """获取标准请求头"""
        return {
            "Accept": "*/*",
            "token": self.token,
            "source": self.source,
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate, br",
            "User-Agent": "AI-Tutor-Agent-Service/1.0.0",
            "Connection": "keep-alive",
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict] = None,
        ext_headers: Optional[Dict] = {},
        **kwargs,
    ) -> Dict[str, Any]:
        """
        执行HTTP请求的通用方法

        Args:
            method: HTTP方法 (GET, POST, etc.)
            endpoint: API端点路径
            payload: 请求体数据
            **kwargs: 额外的requests参数

        Returns:
            Dict[str, Any]: 响应的JSON数据

        Raises:
            AgenticException: 请求失败时的业务异常
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        headers.update(ext_headers)

        try:
            logger.info(f"[base_client] 正在请求API: {method} {url}")

            response = self.session.request(
                method=method,
                url=url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )

            # 检查HTTP状态码
            response.raise_for_status()

            # 解析响应数据
            # 检查响应内容是否为空
            if not response.text.strip():
                logger.info(f"[base_client] API请求成功（空响应）: {method} {url}")
                return None

            response = response.json()
            logger.info(f"[base_client] API请求成功: {method} {url}")
            return response

        except requests.exceptions.Timeout:
            logger.error(
                f"[base_client] 请求超时: {method} {url}, timeout={self.timeout}s"
            )
            raise AgenticException(
                "apis.aitutor.request_timeout", url, self.timeout
            )
        except requests.exceptions.ConnectionError:
            logger.error(f"[base_client] 连接错误: {method} {url}")
            raise AgenticException("apis.aitutor.connection_error", url)
        except requests.exceptions.HTTPError as e:
            logger.error(
                f"[base_client] HTTP错误: {method} {url}, status_code={e.response.status_code}"
            )
            raise AgenticException(
                "apis.aitutor.http_error", url, e.response.status_code
            )
        except ValueError as e:
            logger.error(
                f"[base_client] 响应数据格式错误: {method} {url}, error={e}",
                exc_info=True,
            )
            raise AgenticException(
                "apis.aitutor.response_format_error", url, str(e)
            )
        except Exception as e:
            logger.error(
                f"[base_client] 未知错误: {method} {url}, error={e}", exc_info=True
            )
            raise AgenticException(
                "apis.aitutor.unknown_error", url, str(e)
            )

    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            bool: API服务是否可用
        """
        try:
            # 简单的连接测试，不进行实际的API调用
            response = self.session.head(self.base_url, timeout=5)  # 短超时时间
            return response.status_code < 500
        except Exception as e:
            logger.warning(f"[base_client] API健康检查失败: {e}", exc_info=True)
            return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()

"""
API 认证中间件
"""
import os
from typing import Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from loguru import logger


class APIKeyAuth:
    """API Key 认证中间件"""

    def __init__(self, require_auth: bool = True):
        """
        初始化认证中间件

        Args:
            require_auth: 是否启用认证（可通过环境变量控制）
        """
        self.require_auth = require_auth and os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
        self.api_keys = self._load_api_keys()

    def _load_api_keys(self) -> set:
        """从环境变量加载 API Key"""
        api_key_str = os.getenv("API_KEYS", "")
        if api_key_str:
            return set(k.strip() for k in api_key_str.split(",") if k.strip())
        return set()

    async def __call__(self, request: Request, call_next: Callable):
        """中间件处理逻辑"""
        # 如果未启用认证，直接放行
        if not self.require_auth:
            return await call_next(request)

        # 健康检查端点不需要认证
        if request.url.path in ["/", "/api/v1/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # 检查 API Key
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            logger.warning(f"Unauthorized access attempt to {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "API Key is required. Please provide X-API-Key header."}
            )

        if api_key not in self.api_keys:
            logger.warning(f"Invalid API Key attempt to {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid API Key."}
            )

        # 记录认证成功的请求
        logger.debug(f"Authenticated request to {request.url.path}")

        return await call_next(request)


# 创建全局实例
auth_middleware = APIKeyAuth()

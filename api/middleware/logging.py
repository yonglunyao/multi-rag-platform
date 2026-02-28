"""
结构化日志中间件
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from loguru import logger
import json


class StructuredLogging:
    """结构化日志中间件"""

    def __init__(self):
        """初始化日志中间件"""
        self.enabled = True

    def _generate_request_id(self) -> str:
        """生成唯一请求 ID"""
        return str(uuid.uuid4())[:8]

    async def __call__(self, request: Request, call_next: Callable):
        """中间件处理逻辑"""
        # 生成请求 ID
        request_id = self._generate_request_id()
        request.state.request_id = request_id

        # 记录请求开始时间
        start_time = time.time()

        # 提取请求信息
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # 记录请求开始
        logger.info(
            json.dumps({
                "event": "request_start",
                "request_id": request_id,
                "method": method,
                "path": path,
                "client_ip": client_ip,
                "user_agent": user_agent,
            })
        )

        # 处理请求
        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求完成
            logger.info(
                json.dumps({
                    "event": "request_complete",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time * 1000, 2),
                })
            )

            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"

            return response

        except Exception as e:
            # 计算处理时间
            process_time = time.time() - start_time

            # 记录错误
            logger.error(
                json.dumps({
                    "event": "request_error",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "process_time_ms": round(process_time * 1000, 2),
                })
            )
            raise


# 创建全局实例
structured_logging = StructuredLogging()

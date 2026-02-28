"""
速率限制中间件
"""
import os
from typing import Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from loguru import logger
import time
from collections import defaultdict


class RateLimiter:
    """简单的速率限制器"""

    def __init__(self):
        """初始化速率限制器"""
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
        self.requests_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
        self.requests_per_hour = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))

        # 存储 IP 地址的请求历史 {ip: [(timestamp, count), ...]}
        self.minute_history = defaultdict(list)
        self.hour_history = defaultdict(list)

        # 清理过期记录的间隔（秒）
        self.cleanup_interval = 300
        self.last_cleanup = time.time()

    def _cleanup_old_records(self):
        """清理过期的请求记录"""
        now = time.time()

        # 每 5 分钟清理一次
        if now - self.last_cleanup < self.cleanup_interval:
            return

        self.last_cleanup = now

        # 清理超过 1 分钟的记录
        for ip in list(self.minute_history.keys()):
            self.minute_history[ip] = [
                ts for ts in self.minute_history[ip]
                if now - ts < 60
            ]
            if not self.minute_history[ip]:
                del self.minute_history[ip]

        # 清理超过 1 小时的记录
        for ip in list(self.hour_history.keys()):
            self.hour_history[ip] = [
                ts for ts in self.hour_history[ip]
                if now - ts < 3600
            ]
            if not self.hour_history[ip]:
                del self.hour_history[ip]

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP 地址"""
        # 尝试从 X-Forwarded-For 获取
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # 尝试从 X-Real-IP 获取
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 使用客户端地址
        if request.client:
            return request.client.host

        return "unknown"

    def _check_rate_limit(self, ip: str) -> tuple[bool, str | None]:
        """检查是否超过速率限制"""
        if not self.enabled:
            return True, None

        now = time.time()
        self._cleanup_old_records()

        # 检查每分钟限制
        recent_minute = [ts for ts in self.minute_history[ip] if now - ts < 60]
        if len(recent_minute) >= self.requests_per_minute:
            return False, f"Rate limit exceeded: {self.requests_per_minute} requests per minute"

        # 检查每小时限制
        recent_hour = [ts for ts in self.hour_history[ip] if now - ts < 3600]
        if len(recent_hour) >= self.requests_per_hour:
            return False, f"Rate limit exceeded: {self.requests_per_hour} requests per hour"

        # 记录本次请求
        self.minute_history[ip].append(now)
        self.hour_history[ip].append(now)

        return True, None

    async def __call__(self, request: Request, call_next: Callable):
        """中间件处理逻辑"""
        # 健康检查和文档端点不限流
        if request.url.path in ["/", "/api/v1/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # 获取客户端 IP
        ip = self._get_client_ip(request)

        # 检查速率限制
        allowed, error_msg = self._check_rate_limit(ip)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {ip}: {error_msg}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": error_msg,
                    "retry_after": 60
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                }
            )

        # 添加速率限制响应头
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.requests_per_minute - len(self.minute_history[ip]))
        )

        return response


# 创建全局实例
rate_limiter = RateLimiter()

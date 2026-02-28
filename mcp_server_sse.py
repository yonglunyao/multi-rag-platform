"""
Multi-Library RAG MCP Server - SSE 远程模式
支持通过 HTTP/SSE 远程调用，兼容 Windows MCP 客户端

支持多资料库查询和管理
"""
from typing import Any, Optional
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
import httpx
from loguru import logger
import uvicorn

# RAG 服务配置
RAG_API_BASE_URL = "http://localhost:8001/api/v1"
RAG_TIMEOUT = 60.0

# 创建 MCP 服务器
app_mcp = Server("multilib-rag-server")

# 查询工具定义
QUERY_TOOL = Tool(
    name="rag_query",
    description="""
查询 RAG 资料库，获取技术文档信息。

适用场景：
- 查询特定功能的 API 接口和用法
- 查询权限要求和申请方式
- 查询组件的使用方法
- 查询 Kit 的功能说明
- 查询最佳实践和常见问题

输入参数：
- query: 查询问题，支持中文自然语言
- library_id: 资料库 ID（可选，不指定则使用默认资料库）
- context_length: 返回相关文档数量（默认5，最多10）

示例查询：
- "长时任务需要什么权限"
- "如何使用 UIAbility 创建页面"
- "剪贴板 API 用法"
""",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "查询问题，支持中文自然语言"
            },
            "library_id": {
                "type": "string",
                "description": "资料库 ID（可选，不指定则使用默认资料库）"
            },
            "context_length": {
                "type": "number",
                "description": "返回相关文档数量，默认5，最多10",
                "default": 5,
                "minimum": 1,
                "maximum": 10
            }
        },
        "required": ["query"]
    }
)

# 列出资料库工具
LIST_LIBRARIES_TOOL = Tool(
    name="list_libraries",
    description="""
列出所有可用的资料库，包括启用/禁用状态。

输入参数：无
""",
    inputSchema={
        "type": "object",
        "properties": {},
    }
)

# 获取资料库统计工具
LIBRARY_STATS_TOOL = Tool(
    name="get_library_stats",
    description="""
获取指定资料库的统计信息。

输入参数：
- library_id: 资料库 ID
""",
    inputSchema={
        "type": "object",
        "properties": {
            "library_id": {
                "type": "string",
                "description": "资料库 ID"
            }
        },
        "required": ["library_id"]
    }
)


async def query_rag_api(query: str, context_length: int = 5, library_id: Optional[str] = None) -> dict[str, Any]:
    """调用 RAG API 查询"""
    try:
        url = f"{RAG_API_BASE_URL}/query"
        if library_id:
            url += f"?library_id={library_id}"

        async with httpx.AsyncClient(timeout=RAG_TIMEOUT) as client:
            response = await client.post(
                url,
                json={
                    "query": query,
                    "context_length": context_length,
                    "temperature": 0.3
                }
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"RAG API error: {e}")
        return {
            "error": f"RAG 服务调用失败: {str(e)}",
            "answer": "抱歉，文档服务暂时不可用，请稍后重试。"
        }


async def list_libraries_api() -> dict[str, Any]:
    """调用 RAG API 列出资料库"""
    try:
        async with httpx.AsyncClient(timeout=RAG_TIMEOUT) as client:
            response = await client.get(f"{RAG_API_BASE_URL}/libraries")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"RAG API error: {e}")
        return {
            "error": f"RAG 服务调用失败: {str(e)}",
            "libraries": []
        }


async def get_library_stats_api(library_id: str) -> dict[str, Any]:
    """调用 RAG API 获取资料库统计"""
    try:
        async with httpx.AsyncClient(timeout=RAG_TIMEOUT) as client:
            response = await client.get(f"{RAG_API_BASE_URL}/libraries/{library_id}/stats")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"RAG API error: {e}")
        return {
            "error": f"RAG 服务调用失败: {str(e)}"
        }


@app_mcp.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用工具"""
    return [
        QUERY_TOOL,
        LIST_LIBRARIES_TOOL,
        LIBRARY_STATS_TOOL,
    ]


@app_mcp.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """调用工具"""
    if name == "rag_query":
        query = arguments.get("query", "")
        library_id = arguments.get("library_id")
        context_length = arguments.get("context_length", 5)

        if not query:
            return [TextContent(
                type="text",
                text="错误：查询问题不能为空"
            )]

        result = await query_rag_api(query, context_length, library_id)

        # 格式化输出
        if "error" in result:
            output = f"❌ {result['error']}"
        else:
            answer = result.get("answer", "")
            sources = result.get("sources", [])

            lib_info = f" [{library_id}]" if library_id else ""
            output = f"📚 RAG 文档查询结果{lib_info}\n\n"
            output += f"📝 回答：\n{answer}\n\n"

            if sources:
                output += f"📑 相关文档来源：\n"
                for i, source in enumerate(sources[:5], 1):
                    file = source.get("file", "Unknown")
                    relevance = source.get("relevance", 0)
                    kit = source.get("kit", "")
                    output += f"  {i}. {file}"
                    if kit:
                        output += f" ({kit})"
                    output += f" - 相关度: {relevance:.2f}\n"

        return [TextContent(type="text", text=output)]

    elif name == "list_libraries":
        result = await list_libraries_api()

        if "error" in result:
            output = f"❌ {result['error']}"
        else:
            libraries = result.get("libraries", [])
            output = f"📚 可用资料库列表 ({len(libraries)} 个)\n\n"

            for lib in libraries:
                status_icon = "✅" if lib.get("enabled") else "❌"
                output += f"{status_icon} **{lib.get('name')}** (`{lib.get('id')}`)\n"
                output += f"   - 类型: {lib.get('type')}\n"
                output += f"   - 状态: {lib.get('status')}\n"
                output += f"   - 文档数: {lib.get('document_count', 0)}\n"
                output += f"   - 块数: {lib.get('chunk_count', 0)}\n\n"

        return [TextContent(type="text", text=output)]

    elif name == "get_library_stats":
        library_id = arguments.get("library_id", "")

        if not library_id:
            return [TextContent(
                type="text",
                text="错误：资料库 ID 不能为空"
            )]

        result = await get_library_stats_api(library_id)

        if "error" in result:
            output = f"❌ {result['error']}"
        else:
            output = f"📊 资料库统计: **{result.get('name', library_id)}**\n\n"
            output += f"- ID: {result.get('library_id')}\n"
            output += f"- 类型: {result.get('type')}\n"
            output += f"- 状态: {result.get('status')}\n"
            output += f"- 文档数: {result.get('document_count', 0)}\n"
            output += f"- 块数: {result.get('chunk_count', 0)}\n"
            output += f"- 集合名: {result.get('collection_name')}\n"
            if result.get('last_indexed'):
                output += f"- 最后索引: {result.get('last_indexed')}\n"

        return [TextContent(type="text", text=output)]

    return [TextContent(
        type="text",
        text=f"未知工具: {name}"
    )]


# 创建 SSE 传输
sse_transport = SseServerTransport("/messages")


# SSE 端点处理
async def handle_sse(request: Request) -> Response:
    """处理 SSE 连接"""
    logger.info(f"New SSE connection from {request.client.host}")

    # 使用 SseServerTransport 处理 SSE 连接
    async with sse_transport.connect_sse(
        request.scope,
        request.receive,
        request._send,
    ) as (read_stream, write_stream):
        await app_mcp.run(
            read_stream,
            write_stream,
            app_mcp.create_initialization_options(),
        )

    return Response()


async def handle_messages(request: Request) -> Response:
    """处理 MCP 消息 POST 请求"""
    logger.info(f"POST /messages from {request.client.host}")

    # 使用 SseServerTransport 处理消息
    await sse_transport.handle_post_message(
        request.scope,
        request.receive,
        request._send,
    )

    return Response()


async def health_check(request: Request) -> Response:
    """健康检查"""
    return Response(
        content='{"status": "healthy", "service": "harmonyos-rag-mcp", "version": "1.0.0"}',
        status_code=200,
        media_type="application/json"
    )


# Starlette 应用
starlette_app = Starlette(
    debug=True,
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
        Route("/health", endpoint=health_check),
    ],
)

# 添加 CORS 中间件
starlette_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    # MCP SSE 服务器配置
    MCP_HOST = "0.0.0.0"
    MCP_PORT = 8002

    logger.info(f"Starting MCP SSE server on {MCP_HOST}:{MCP_PORT}")
    logger.info(f"SSE endpoint: http://{MCP_HOST}:{MCP_PORT}/sse")
    logger.info(f"Messages endpoint: http://{MCP_HOST}:{MCP_PORT}/messages")
    logger.info(f"Health check: http://{MCP_HOST}:{MCP_PORT}/health")

    uvicorn.run(
        starlette_app,
        host=MCP_HOST,
        port=MCP_PORT,
        log_level="info",
        access_log=True  # 启用访问日志
    )

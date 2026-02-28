"""
HarmonyOS 文档 RAG 服务 - FastAPI 主应用

支持多资料库管理
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from api.routes import query, agent, documents, libraries
from api.schemas import HealthResponse
from api.middleware import auth_middleware, rate_limiter, structured_logging
from core.vector_store import get_vector_store
from core.library_manager import get_library_manager
from core.permission_index import get_permission_index


# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting Multi-Library RAG service...")

    # 初始化资料库管理器
    try:
        lib_manager = get_library_manager()
        config = lib_manager.load_config()
        logger.info(f"Library manager loaded: {len(config.libraries)} libraries")
        enabled_libs = config.get_enabled_libraries()
        logger.info(f"Enabled libraries: {[lib.id for lib in enabled_libs]}")
    except Exception as e:
        logger.warning(f"Library manager initialization warning: {e}")

    # 初始化向量数据库
    try:
        vector_store = get_vector_store()
        collections = vector_store.list_collections()
        logger.info(f"Vector store loaded: {len(collections)} collections")
        for col in collections:
            stats = vector_store.get_stats(col)
            logger.info(f"  Collection '{col}': {stats['document_count']} documents")
    except Exception as e:
        logger.warning(f"Vector store initialization warning: {e}")

    # 初始化权限索引（仅 HarmonyOS）
    try:
        perm_index = get_permission_index()
        docs_root = os.getenv('DOCS_ROOT', '/home/mind/workspace/harmonyos/docs/zh-cn/application-dev')

        # 尝试加载已保存的索引
        index_path = '/home/mind/workspace/harmony-docs-rag/data/permission_index.json'
        if os.path.exists(index_path):
            perm_index.load(index_path)
            logger.info(f"Permission index loaded from {index_path}")
        else:
            # 构建新索引
            logger.info("Building permission index...")
            perm_index.build(docs_root)
            # 保存索引
            os.makedirs(os.path.dirname(index_path), exist_ok=True)
            perm_index.save(index_path)
            logger.info(f"Permission index saved to {index_path}")
    except Exception as e:
        logger.warning(f"Permission index initialization warning: {e}")

    yield

    logger.info("Shutting down Multi-Library RAG service...")


# 创建 FastAPI 应用
app = FastAPI(
    title="HarmonyOS 文档 RAG 服务",
    description="基于 HarmonyOS 应用开发文档的 RAG 检索服务",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加结构化日志中间件（第一个，记录所有请求）
app.middleware("http")(structured_logging)

# 添加 API Key 认证中间件（在所有路由之前）
app.middleware("http")(auth_middleware)

# 添加速率限制中间件
app.middleware("http")(rate_limiter)

# 注册路由
app.include_router(libraries.router)  # 资料库管理路由
app.include_router(query.router)
app.include_router(agent.router)
app.include_router(documents.router)


@app.get("/", tags=["root"])
async def root():
    """根路径"""
    return {
        "message": "Multi-Library RAG 服务",
        "version": "2.0.0",
        "docs": "/docs",
        "features": [
            "多资料库管理",
            "HarmonyOS 文档检索",
            "MCP SSE 接口",
        ]
    }


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """健康检查"""
    try:
        vector_store = get_vector_store()
        stats = vector_store.get_stats()

        # 检查 Ollama
        import httpx
        llm_status = "unknown"
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/tags")
                llm_status = "available" if response.status_code == 200 else "unavailable"
        except:
            llm_status = "unavailable"

        return HealthResponse(
            status="healthy",
            version="1.0.0",
            document_count=stats['document_count'],
            llm_status=llm_status,
        )

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthResponse(
            status="unhealthy",
            version="1.0.0",
            document_count=0,
            llm_status="error",
        )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=True,
    )

"""
文档管理接口：文档统计、索引管理等
"""
import os
import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from loguru import logger

from api.schemas import DocumentStatsResponse, HealthResponse
from core.vector_store import get_vector_store
from core.generator import Generator


# 全局索引状态
_index_status = {
    "is_running": False,
    "last_update": None,
    "last_error": None,
    "progress": 0,
}

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("/stats", response_model=DocumentStatsResponse)
async def get_document_stats():
    """
    获取文档统计信息
    """
    try:
        vector_store = get_vector_store()
        stats = vector_store.get_stats()

        # 获取分类统计（简化版）
        categories = {}

        return DocumentStatsResponse(
            total_documents=stats['document_count'],
            collection_name=stats['collection_name'],
            categories=categories,
        )

    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex")
async def reindex_documents(background_tasks: BackgroundTasks, incremental: bool = False):
    """
    重建文档索引

    Args:
        incremental: 是否增量更新（仅处理新增/修改的文件）
    """
    global _index_status

    try:
        if _index_status["is_running"]:
            return {
                'message': 'Indexing is already in progress',
                'status': _index_status,
            }

        docs_root = os.getenv('DOCS_SOURCE_PATH')

        if not docs_root:
            raise HTTPException(status_code=400, detail="DOCS_SOURCE_PATH not configured")

        # 更新状态
        _index_status["is_running"] = True
        _index_status["last_error"] = None
        _index_status["progress"] = 0

        # 添加后台任务
        background_tasks.add_task(_run_reindex, docs_root=docs_root, incremental=incremental)

        return {
            'message': f'{"Incremental" if incremental else "Full"} reindexing started',
            'docs_root': docs_root,
        }

    except Exception as e:
        _index_status["is_running"] = False
        _index_status["last_error"] = str(e)
        logger.error(f"Reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_reindex(docs_root: str, incremental: bool = False):
    """执行索引重建"""
    global _index_status

    try:
        from scripts.ingest import ingest_documents
        from core.document_parser import HarmonyDocParser
        from core.embedder import Embedder

        if incremental:
            # 增量更新逻辑：只处理新文件
            parser = HarmonyDocParser(docs_root)
            vector_store = get_vector_store()

            # 获取已索引文件的集合
            existing_sources = set()
            try:
                collection = vector_store.collection
                if collection:
                    # 获取所有已存在的 source 元数据
                    results = collection.get(include=["metadatas"])
                    if results and results.get("metadatas"):
                        existing_sources = set(
                            m.get("source", "") for m in results["metadatas"]
                        )
            except Exception as e:
                logger.warning(f"Could not fetch existing sources: {e}")

            # 扫描新文件
            all_files = parser.scan_directory()
            new_files = [f for f in all_files if parser._get_relative_path(f) not in existing_sources]

            logger.info(f"Incremental update: {len(new_files)} new files found")

            if new_files:
                ingest_documents(
                    docs_root=docs_root,
                    max_files=len(new_files),
                    batch_size=50,
                )

            _index_status["progress"] = 100
        else:
            # 全量重建
            ingest_documents(docs_root=docs_root)
            _index_status["progress"] = 100

        _index_status["last_update"] = datetime.now().isoformat()
        _index_status["is_running"] = False

    except Exception as e:
        _index_status["is_running"] = False
        _index_status["last_error"] = str(e)
        logger.error(f"Reindex task error: {e}")


@router.get("/status")
async def get_index_status():
    """获取索引状态"""
    vector_store = get_vector_store()
    stats = vector_store.get_stats()

    return {
        **_index_status,
        "document_count": stats['document_count'],
        "collection_name": stats['collection_name'],
    }


@router.delete("/clear")
async def clear_index():
    """
    清空索引
    """
    try:
        vector_store = get_vector_store()
        vector_store.reset()

        return {'message': 'Index cleared successfully'}

    except Exception as e:
        logger.error(f"Clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

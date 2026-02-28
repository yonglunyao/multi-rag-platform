"""
资料库管理 API 路由

提供资料库的增删改查、索引、统计、导出等功能
"""
import asyncio
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse
from loguru import logger
from datetime import datetime

from core.library_manager import get_library_manager
from core.models import LibraryConfig, LibraryType, LibraryStatus
from core.parsers import get_parser
from core.embedder import Embedder
from core.vector_store import get_vector_store
from api.schemas import (
    LibraryListResponse,
    LibraryDetailResponse,
    LibraryCreateRequest,
    IndexResponse,
    StatsResponse,
    ExportRequest,
    ExportResponse,
    SetActiveRequest,
    MessageResponse,
)

router = APIRouter(prefix="/api/v1/libraries", tags=["libraries"])


def get_current_library_id(library_id: Optional[str]) -> str:
    """
    获取当前使用的资料库 ID

    Args:
        library_id: 指定的资料库 ID

    Returns:
        str: 资料库 ID
    """
    if library_id:
        return library_id

    manager = get_library_manager()
    active_id = manager.get_active_library_id()
    if active_id:
        return active_id

    # 使用配置中的默认资料库
    config = manager.get_config()
    return config.global_config.default_library


@router.get("", response_model=LibraryListResponse)
async def list_libraries(include_disabled: bool = False):
    """
    列出所有资料库

    Args:
        include_disabled: 是否包含禁用的资料库

    Returns:
        LibraryListResponse: 资料库列表
    """
    manager = get_library_manager()
    libraries = manager.list_libraries(include_disabled=include_disabled)

    return LibraryListResponse(
        libraries=[
            {
                "id": lib.id,
                "name": lib.name,
                "type": lib.type.value,
                "enabled": lib.enabled,
                "status": lib.status.value,
                "document_count": lib.document_count,
                "chunk_count": lib.chunk_count,
                "created_at": lib.created_at.isoformat() if lib.created_at else None,
            }
            for lib in libraries
        ]
    )


@router.get("/{library_id}", response_model=LibraryDetailResponse)
async def get_library(library_id: str):
    """
    获取资料库详情

    Args:
        library_id: 资料库 ID

    Returns:
        LibraryDetailResponse: 资料库详情
    """
    manager = get_library_manager()
    lib = manager.get_library(library_id)

    if lib is None:
        raise HTTPException(status_code=404, detail=f"资料库不存在: {library_id}")

    return LibraryDetailResponse(
        id=lib.id,
        name=lib.name,
        type=lib.type.value,
        enabled=lib.enabled,
        status=lib.status.value,
        source_path=lib.source_path,
        collection_name=lib.collection_name,
        embedding_model=lib.embedding_config.model_name,
        chunk_size=lib.chunking_config.chunk_size,
        chunk_overlap=lib.chunking_config.chunk_overlap,
        document_count=lib.document_count,
        chunk_count=lib.chunk_count,
        last_indexed=lib.last_indexed.isoformat() if lib.last_indexed else None,
        created_at=lib.created_at.isoformat() if lib.created_at else None,
    )


@router.post("", response_model=MessageResponse)
async def create_library(request: LibraryCreateRequest):
    """
    创建新资料库

    Args:
        request: 创建请求

    Returns:
        MessageResponse: 创建结果
    """
    manager = get_library_manager()

    # 检查 ID 是否已存在
    if manager.get_library(request.id):
        raise HTTPException(status_code=409, detail=f"资料库 ID 已存在: {request.id}")

    # 检查源路径是否存在
    source_path = Path(request.source_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"文档源路径不存在: {request.source_path}")

    # 创建资料库配置
    from core.models import EmbeddingConfig, ChunkingConfig

    config = LibraryConfig(
        id=request.id,
        name=request.name,
        type=LibraryType(request.type),
        source_path=request.source_path,
        enabled=request.enabled,
        embedding_config=EmbeddingConfig(
            model_name=request.embedding_model or "BAAI/bge-base-zh-v1.5",
            device="cpu",
        ),
        chunking_config=ChunkingConfig(
            chunk_size=request.chunk_size or 1200,
            chunk_overlap=request.chunk_overlap or 200,
        ),
    )

    # 添加到管理器
    if manager.create_library(config):
        return MessageResponse(message=f"资料库 {request.id} 创建成功")
    else:
        raise HTTPException(status_code=500, detail="创建资料库失败")


@router.delete("/{library_id}", response_model=MessageResponse)
async def delete_library(library_id: str):
    """
    删除资料库

    Args:
        library_id: 资料库 ID

    Returns:
        MessageResponse: 删除结果
    """
    manager = get_library_manager()

    if not manager.get_library(library_id):
        raise HTTPException(status_code=404, detail=f"资料库不存在: {library_id}")

    if manager.delete_library(library_id):
        return MessageResponse(message=f"资料库 {library_id} 已删除")
    else:
        raise HTTPException(status_code=500, detail="删除资料库失败")


@router.post("/{library_id}/index", response_model=IndexResponse)
async def index_library(library_id: str, background_tasks: BackgroundTasks, force: bool = False):
    """
    触发资料库索引

    Args:
        library_id: 资料库 ID
        background_tasks: 后台任务
        force: 是否强制重新索引

    Returns:
        IndexResponse: 索引任务信息
    """
    manager = get_library_manager()
    lib = manager.get_library(library_id)

    if lib is None:
        raise HTTPException(status_code=404, detail=f"资料库不存在: {library_id}")

    if not lib.enabled:
        raise HTTPException(status_code=400, detail=f"资料库未启用: {library_id}")

    # 检查是否已有索引在进行
    if manager.is_indexing():
        current = manager.get_current_indexing()
        raise HTTPException(
            status_code=409,
            detail=f"已有索引任务正在进行: {current}"
        )

    # 获取索引锁
    if not manager.acquire_index_lock(library_id):
        raise HTTPException(status_code=409, detail="无法获取索引锁，请稍后重试")

    # 创建后台任务
    task_id = f"index_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    background_tasks.add_task(run_index_task, library_id, force)

    return IndexResponse(
        library_id=library_id,
        status="indexing",
        message=f"索引任务已启动",
        task_id=task_id,
    )


async def run_index_task(library_id: str, force: bool = False):
    """
    执行索引任务（后台运行）

    Args:
        library_id: 资料库 ID
        force: 是否强制重新索引
    """
    manager = get_library_manager()
    lib = manager.get_library(library_id)

    if lib is None:
        manager.release_index_lock(library_id)
        return

    try:
        logger.info(f"[{library_id}] 开始索引任务")

        # 更新状态
        manager.update_library_status(library_id, LibraryStatus.INDEXING)

        # 获取解析器
        parser = get_parser(lib.type)

        # 扫描文档
        if lib.type == LibraryType.HARMONY_OS:
            files = parser.scan_directory(lib.source_path)
        else:
            files = parser.scan_directory(lib.source_path)

        logger.info(f"[{library_id}] 找到 {len(files)} 个文档文件")

        # 获取向量存储和嵌入器
        vector_store = get_vector_store()
        embedder = Embedder()

        # 处理每个文档
        all_texts = []
        all_embeddings = []
        all_metadatas = []
        all_ids = []
        doc_count = 0

        for i, file_path in enumerate(files):
            try:
                # 解析文档
                docs = parser.parse(file_path)
                for doc in docs:
                    # 分块
                    chunks = parser.chunk_text(doc.content, doc.metadata, doc.source)

                    for chunk in chunks:
                        all_texts.append(chunk.text)
                        all_metadatas.append(chunk.metadata)
                        all_ids.append(chunk.metadata.get('chunk_id', f"doc_{len(all_ids)}"))

                    doc_count += 1

                # 每 100 个文档处理一次
                if len(all_texts) >= 100:
                    # 生成嵌入
                    embeddings = embedder.embed_texts(all_texts)
                    all_embeddings.extend(embeddings)

                    # 添加到向量存储
                    if len(all_embeddings) == len(all_texts):
                        vector_store.add_texts(
                            texts=all_texts,
                            embeddings=all_embeddings,
                            metadatas=all_metadatas,
                            ids=all_ids,
                            collection_name=lib.collection_name,
                        )

                    logger.info(f"[{library_id}] 已处理 {doc_count}/{len(files)} 个文档")

                    # 清空
                    all_texts = []
                    all_embeddings = []
                    all_metadatas = []
                    all_ids = []

            except Exception as e:
                logger.error(f"[{library_id}] 处理文件 {file_path} 失败: {e}")

        # 处理剩余文档
        if all_texts:
            embeddings = embedder.embed_texts(all_texts)
            all_embeddings.extend(embeddings)

            if len(all_embeddings) == len(all_texts):
                vector_store.add_texts(
                    texts=all_texts,
                    embeddings=all_embeddings,
                    metadatas=all_metadatas,
                    ids=all_ids,
                    collection_name=lib.collection_name,
                )

        # 更新统计
        lib.document_count = doc_count
        lib.chunk_count = vector_store.count(collection_name=lib.collection_name)
        manager.update_library_status(library_id, LibraryStatus.READY)

        logger.info(f"[{library_id}] 索引完成: {doc_count} 个文档, {lib.chunk_count} 个块")

    except Exception as e:
        logger.error(f"[{library_id}] 索引失败: {e}")
        manager.update_library_status(library_id, LibraryStatus.ERROR)
    finally:
        manager.release_index_lock(library_id)


@router.get("/{library_id}/stats", response_model=StatsResponse)
async def get_library_stats(library_id: str):
    """
    获取资料库统计信息

    Args:
        library_id: 资料库 ID

    Returns:
        StatsResponse: 统计信息
    """
    manager = get_library_manager()
    stats = manager.get_library_stats(library_id)

    if stats is None:
        raise HTTPException(status_code=404, detail=f"资料库不存在: {library_id}")

    return StatsResponse(**stats)


@router.post("/{library_id}/export", response_model=ExportResponse)
async def export_library(library_id: str, request: ExportRequest):
    """
    导出资料库数据

    Args:
        library_id: 资料库 ID
        request: 导出请求

    Returns:
        ExportResponse: 导出结果
    """
    manager = get_library_manager()
    lib = manager.get_library(library_id)

    if lib is None:
        raise HTTPException(status_code=404, detail=f"资料库不存在: {library_id}")

    # 创建导出目录
    export_dir = Path(manager.get_config().global_config.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    # 导出文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{library_id}_{timestamp}.json"
    file_path = export_dir / filename

    # 导出数据
    try:
        from core.exporter import DataExporter
        exporter = DataExporter()

        exporter.export_library(
            library_id=library_id,
            output_path=str(file_path),
            format=request.format,
            include_embeddings=request.include_embeddings,
        )

        return ExportResponse(
            library_id=library_id,
            format=request.format,
            file_path=str(file_path),
            size_bytes=file_path.stat().st_size,
            download_url=f"/api/v1/exports/{filename}",
        )

    except Exception as e:
        logger.error(f"导出失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/active", response_model=dict)
async def get_active_library():
    """
    获取活动资料库

    Returns:
        dict: 活动资料库信息
    """
    manager = get_library_manager()
    active_id = manager.get_active_library_id()

    return {"active_library": active_id}


@router.post("/active", response_model=MessageResponse)
async def set_active_library(request: SetActiveRequest):
    """
    设置活动资料库

    Args:
        request: 设置请求

    Returns:
        MessageResponse: 设置结果
    """
    manager = get_library_manager()

    if manager.set_active_library(request.library_id):
        return MessageResponse(message=f"活动资料库已设置为 {request.library_id}")
    else:
        raise HTTPException(status_code=400, detail="设置失败，请检查资料库 ID")


@router.get("/exports/{filename}", response_class=FileResponse)
async def download_export(filename: str):
    """
    下载导出文件

    Args:
        filename: 文件名

    Returns:
        FileResponse: 文件响应
    """
    manager = get_library_manager()
    export_dir = Path(manager.get_config().global_config.export_dir)
    file_path = export_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/json",
    )

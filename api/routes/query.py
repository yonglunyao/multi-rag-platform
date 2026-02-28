"""
查询接口：处理用户查询并生成回答

支持多资料库查询
"""
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from api.schemas import QueryRequest, QueryResponse, SourceDocument
from core.retriever import get_retriever
from core.generator import Generator
from core.answer_validator import get_answer_validator
from core.library_manager import get_library_manager

router = APIRouter(prefix="/api/v1", tags=["query"])


def get_collection_name(library_id: Optional[str]) -> Optional[str]:
    """
    获取资料库对应的集合名称

    Args:
        library_id: 资料库 ID

    Returns:
        集合名称
    """
    from core.vector_store import get_vector_store

    vector_store = get_vector_store()

    # 优先级：指定的library_id > 活动资料库 > 默认harmony_docs
    if not library_id:
        # 使用活动资料库
        manager = get_library_manager()
        active_id = manager.get_active_library_id()
        if active_id:
            lib = manager.get_library(active_id)
            if lib:
                # 检查集合是否存在且有数据
                if vector_store.collection_exists(lib.collection_name):
                    count = vector_store.count(lib.collection_name)
                    if count > 0:
                        return lib.collection_name
        # 回退到默认集合
        if vector_store.collection_exists("harmony_docs"):
            return "harmony_docs"
        return None

    # 获取指定资料库
    manager = get_library_manager()
    lib = manager.get_library(library_id)
    if lib:
        # 检查集合是否存在且有数据
        if vector_store.collection_exists(lib.collection_name):
            count = vector_store.count(lib.collection_name)
            if count > 0:
                return lib.collection_name
        # 集合为空，回退到默认harmony_docs
        logger.warning(f"集合 {lib.collection_name} 为空，回退到默认集合")
        if vector_store.collection_exists("harmony_docs"):
            return "harmony_docs"

    return "harmony_docs"  # 最终回退到默认集合


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, library_id: Optional[str] = Query(None, description="资料库 ID")):
    """
    查询接口 - 根据用户问题生成基于文档的回答

    Args:
        request: 查询请求
        library_id: 资料库 ID（可选，不指定则使用默认资料库）

    Returns:
        包含回答和来源文档的响应
    """
    try:
        # 获取集合名称
        collection_name = get_collection_name(library_id)

        # 获取检索器
        retriever = get_retriever()

        # 使用智能检索：自动选择最佳检索策略
        results, meets_threshold, metadata = retriever.smart_retrieve(
            query=request.query,
            top_k=request.context_length,
            filter=request.filter,
            min_score=0.3,
            collection_name=collection_name,
        )

        logger.info(f"Query: {request.query}, method: {metadata.get('method')}, permissions: {metadata.get('permissions_found')}")

        # 检查置信度
        if not results:
            raise HTTPException(status_code=404, detail="未找到相关文档")

        if not meets_threshold:
            logger.warning(f"Low confidence for query: {request.query}")
            # 返回低置信度提示，但仍尝试生成回答
            answer = f"根据检索结果，未能找到与「{request.query}」高度相关的文档。建议您：\n1. 检查查询词是否准确\n2. 尝试使用更具体的技术术语（如权限名 ohos.permission.xxx、API名等）\n3. 提供更多上下文信息"

            sources = [
                SourceDocument(
                    file=r['metadata'].get('source', r['metadata'].get('filename', '')),
                    relevance=r['score'],
                    category=r['metadata'].get('category', ''),
                    kit=r['metadata'].get('kit', ''),
                )
                for r in results[:3]  # 只返回前3个低相关结果作为参考
            ]
            return QueryResponse(answer=answer, sources=sources)

        # 构建上下文
        context = "\n\n".join([
            f"[{r['metadata'].get('source', r['metadata'].get('filename', ''))}]\n{r['document']}"
            for r in results
        ])

        # 生成回答
        generator = Generator()
        answer = generator.generate(
            query=request.query,
            context=context,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        # 验证答案中的技术术语
        validator = get_answer_validator()
        validation = validator.validate_answer(answer, results)
        should_reject, reject_reason = validator.should_reject(validation, threshold=0.5)

        if should_reject:
            logger.warning(f"Answer validation failed for query: {request.query} - {reject_reason}")
            # 返回验证失败信息，但仍提供检索到的原始文档信息
            answer = f"注意：{reject_reason}\n\n以下是基于文档检索到的原始信息：\n\n{context[:1000]}..."

        # 格式化来源文档
        sources = [
            SourceDocument(
                file=r['metadata'].get('source', r['metadata'].get('filename', '')),
                relevance=r['score'],
                category=r['metadata'].get('category', ''),
                kit=r['metadata'].get('kit', ''),
            )
            for r in results
        ]

        return QueryResponse(answer=answer, sources=sources)

    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch_query")
async def batch_query(queries: list[str], library_id: Optional[str] = Query(None, description="资料库 ID")):
    """
    批量查询接口 - 用于 Agent 上下文填充

    Args:
        queries: 查询列表
        library_id: 资料库 ID（可选）

    Returns:
        批量查询结果
    """
    try:
        # 获取集合名称
        collection_name = get_collection_name(library_id)

        retriever = get_retriever()
        results = {}

        for query in queries:
            # 使用增强检索
            docs, meets_threshold = retriever.retrieve_with_expansion(
                query=query,
                top_k=3,
                min_score=0.2,  # 批量查询使用较低阈值
                collection_name=collection_name,
            )
            results[query] = {
                'documents': [
                    {
                        'document': r['document'][:500],  # 限制长度
                        'source': r['metadata'].get('source', r['metadata'].get('filename', '')),
                        'score': r['score'],
                    }
                    for r in docs
                ],
                'meets_threshold': meets_threshold
            }

        return {'results': results}

    except Exception as e:
        logger.error(f"Batch query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def query_stream(
    request: QueryRequest,
    library_id: Optional[str] = Query(None, description="资料库 ID")
):
    """
    流式查询接口 - 实时流式返回生成的回答

    Args:
        request: 查询请求
        library_id: 资料库 ID（可选）

    Returns:
        Server-Sent Events 流式响应
    """
    try:
        # 获取集合名称
        collection_name = get_collection_name(library_id)

        # 获取检索器
        retriever = get_retriever()

        # 使用增强检索：查询扩展 + 置信度阈值
        results, meets_threshold = retriever.retrieve_with_expansion(
            query=request.query,
            top_k=request.context_length,
            filter=request.filter,
            min_score=0.3,
            collection_name=collection_name,
        )

        if not results:
            raise HTTPException(status_code=404, detail="未找到相关文档")

        # 构建上下文
        context = "\n\n".join([
            f"[{r['metadata'].get('source', r['metadata'].get('filename', ''))}]\n{r['document']}"
            for r in results
        ])

        # 收集来源文档信息
        sources = [
            {
                "file": r['metadata'].get('source', r['metadata'].get('filename', '')),
                "relevance": r['score'],
                "category": r['metadata'].get('category', ''),
                "kit": r['metadata'].get('kit', ''),
            }
            for r in results
        ]

        # 创建生成器
        generator = Generator()

        async def stream_generator():
            """流式生成器"""
            try:
                # 首先发送来源信息和置信度（作为事件）
                yield f"event: sources\ndata: {json.dumps({'sources': sources, 'meets_threshold': meets_threshold})}\n\n"

                # 如果置信度不足，发送警告
                if not meets_threshold:
                    warning_msg = f"注意：检索置信度较低，未能找到与「{request.query}」高度相关的文档。"
                    yield f"event: warning\ndata: {json.dumps({'message': warning_msg})}\n\n"
                    yield "event: done\ndata: {}\n\n"
                    return

                # 然后流式生成回答
                full_answer = ""
                async for chunk in generator.generate_stream(
                    query=request.query,
                    context=context,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                ):
                    full_answer += chunk
                    # 发送文本块
                    yield f"event: chunk\ndata: {json.dumps({'text': chunk})}\n\n"

                # 验证答案
                validator = get_answer_validator()
                validation = validator.validate_answer(full_answer, results)
                should_reject, reject_reason = validator.should_reject(validation, threshold=0.5)

                if should_reject:
                    yield f"event: validation_warning\ndata: {json.dumps({'message': reject_reason})}\n\n"

                # 发送完成事件
                yield "event: done\ndata: {}\n\n"

            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

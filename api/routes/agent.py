"""
Agent 专用接口：为 AI Agent 提供知识库服务
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from loguru import logger

from api.schemas import (
    AgentSearchRequest,
    AgentSearchResponse,
    SearchResult,
    AgentContextRequest,
    AgentContextResponse,
    SourceDocument,
)
from core.retriever import get_retriever

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.post("/search", response_model=AgentSearchResponse)
async def agent_search(request: AgentSearchRequest):
    """
    Agent 知识检索 - 不生成回答，只返回相关文档片段

    适用于 Agent 需要自主处理信息的场景
    """
    try:
        retriever = get_retriever()

        results = retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
            filter=request.filter,
        )

        formatted_results = [
            SearchResult(
                id=r['id'],
                document=r['document'] if request.return_content else r['document'][:500],
                metadata=r['metadata'],
                score=r['score'],
            )
            for r in results
        ]

        return AgentSearchResponse(
            results=formatted_results,
            query=request.query,
            total=len(formatted_results),
        )

    except Exception as e:
        logger.error(f"Agent search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context", response_model=AgentContextResponse)
async def agent_context(request: AgentContextRequest):
    """
    Agent 上下文增强 - 为 Agent 提供相关文档上下文

    结合对话历史，提供更精准的上下文信息
    """
    try:
        retriever = get_retriever()

        # 基于当前查询检索
        results = retriever.retrieve(request.user_query, top_k=5)

        # 构建上下文（限制长度）
        context_parts = []
        current_length = 0
        sources = []

        for r in results:
            source = SourceDocument(
                file=r['metadata']['source'],
                relevance=r['score'],
                category=r['metadata'].get('category', ''),
                kit=r['metadata'].get('kit', ''),
            )
            sources.append(source)

            part = f"## {r['metadata']['source']}\n{r['document']}\n\n"

            if current_length + len(part) > request.max_tokens:
                remaining = request.max_tokens - current_length
                if remaining > 50:
                    context_parts.append(part[:remaining] + "...")
                break

            context_parts.append(part)
            current_length += len(part)

        context = ''.join(context_parts)

        return AgentContextResponse(context=context, sources=sources)

    except Exception as e:
        logger.error(f"Agent context error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_knowledge(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证知识 - 检查知识库中是否有相关信息

    返回相关度和文档数量，帮助 Agent 判断是否需要使用外部知识

    Body: {"query": "..."}
    """
    try:
        query = request.get("query", "")

        retriever = get_retriever()
        results = retriever.retrieve(query, top_k=3)

        if not results:
            return {
                'has_relevant': False,
                'confidence': 0.0,
                'document_count': 0,
            }

        # 计算平均相关度
        avg_score = sum(r['score'] for r in results) / len(results)

        return {
            'has_relevant': avg_score > 0.5,
            'confidence': avg_score,
            'document_count': len(results),
            'top_source': results[0]['metadata']['source'],
        }

    except Exception as e:
        logger.error(f"Validate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tools/search")
async def agent_tool_search(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool Calling 格式的搜索接口

    返回符合 OpenAI function calling 格式的响应

    Body: {"query": "...", "top_k": 5}
    """
    try:
        query = request.get("query", "")
        top_k = request.get("top_k", 5)

        retriever = get_retriever()
        results = retriever.retrieve(query, top_k=top_k)

        return {
            "tool": "harmony_docs_search",
            "query": query,
            "results": [
                {
                    "content": r['document'][:800],
                    "source": r['metadata']['source'],
                    "score": r['score'],
                    "metadata": {
                        "category": r['metadata'].get('category', ''),
                        "kit": r['metadata'].get('kit', ''),
                        "subsystem": r['metadata'].get('subsystem', ''),
                    }
                }
                for r in results
            ],
            "summary": f"Found {len(results)} relevant documents"
        }

    except Exception as e:
        logger.error(f"Tool search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch_search")
async def batch_agent_search(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    批量搜索 - 一次查询多个问题

    适用于 Agent 需要获取多个相关信息的场景

    Body: {"queries": ["...", "..."], "top_k": 3}
    """
    try:
        queries = request.get("queries", [])
        top_k = request.get("top_k", 3)

        retriever = get_retriever()
        results = {}

        for query in queries:
            docs = retriever.retrieve(query, top_k=top_k)
            results[query] = [
                {
                    'id': r['id'],
                    'content': r['document'][:500],
                    'source': r['metadata']['source'],
                    'score': r['score'],
                }
                for r in docs
            ]

        return {
            'queries': len(queries),
            'results': results,
        }

    except Exception as e:
        logger.error(f"Batch search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context_with_history")
async def agent_context_with_history(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    带对话历史的上下文增强

    分析对话历史，理解上下文，提供更精准的信息

    Body: {"user_query": "...", "conversation_history": [...], "max_tokens": 2000}
    """
    try:
        user_query = request.get("user_query", "")
        conversation_history = request.get("conversation_history")
        max_tokens = request.get("max_tokens", 2000)

        retriever = get_retriever()

        # 构建增强查询
        enhanced_query = user_query
        if conversation_history and len(conversation_history) > 0:
            # 获取最近几轮对话的关键词
            recent_context = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            context_keywords = []
            for turn in recent_context:
                if 'content' in turn:
                    context_keywords.append(turn['content'])

            # 简单的上下文增强：将历史关键词添加到查询中
            if context_keywords:
                enhanced_query = f"{user_query} (上下文: {' '.join(context_keywords[-2:])})"

        # 执行检索
        results = retriever.retrieve(enhanced_query, top_k=5)

        # 构建上下文
        context_parts = []
        sources = []

        for r in results:
            source = {
                'file': r['metadata']['source'],
                'relevance': r['score'],
                'category': r['metadata'].get('category', ''),
                'kit': r['metadata'].get('kit', ''),
            }
            sources.append(source)

            part = f"## {r['metadata']['source']}\n{r['document']}\n\n"

            if sum(len(p) for p in context_parts) + len(part) > max_tokens:
                break

            context_parts.append(part)

        return {
            'query': user_query,
            'enhanced_query': enhanced_query,
            'context': ''.join(context_parts),
            'sources': sources,
            'conversation_turns': len(conversation_history) if conversation_history else 0,
        }

    except Exception as e:
        logger.error(f"Context with history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

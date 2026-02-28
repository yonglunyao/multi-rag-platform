"""
检索器：结合向量搜索和关键词匹配的混合检索

支持资料库感知检索
"""
import re
from typing import List, Dict, Any, Optional
from loguru import logger

from core.embedder import Embedder
from core.vector_store import VectorStore
from core.query_expander import get_query_expander
from core.permission_index import get_permission_index


class Retriever:
    """文档检索器 - 支持资料库感知"""

    def __init__(
        self,
        embedder: Embedder = None,
        vector_store: VectorStore = None,
        top_k: int = 5,
        use_hybrid: bool = True,
    ):
        """
        初始化检索器

        Args:
            embedder: 嵌入模型
            vector_store: 向量数据库
            top_k: 返回结果数量
            use_hybrid: 是否使用混合检索
        """
        self.embedder = embedder or Embedder()
        self.vector_store = vector_store or VectorStore()
        self.top_k = top_k
        self.use_hybrid = use_hybrid

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        检索相关文档

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter: 元数据过滤条件
            collection_name: 集合名称（资料库 ID）

        Returns:
            检索结果列表
        """
        top_k = top_k or self.top_k

        # 生成查询向量
        query_embedding = self.embedder.embed_text(query)

        # 向量搜索
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter=filter,
            collection_name=collection_name,
        )

        # 混合检索（可选）
        if self.use_hybrid:
            results = self._hybrid_rerank(query, results)

        return results

    def _hybrid_rerank(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        使用关键词匹配重新排序

        Args:
            query: 原始查询
            vector_results: 向量搜索结果

        Returns:
            重新排序后的结果
        """
        # 提取查询关键词
        keywords = self._extract_keywords(query)

        for result in vector_results:
            # 计算关键词匹配分数
            keyword_score = self._keyword_match_score(
                keywords,
                result['document'] + ' ' + result['metadata'].get('kit', '')
            )

            # 混合分数：70% 向量相似度 + 30% 关键词匹配
            result['score'] = 0.7 * result['score'] + 0.3 * keyword_score

        # 按分数重新排序
        vector_results.sort(key=lambda x: x['score'], reverse=True)

        return vector_results

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词，包括技术术语"""
        keywords = set()

        # 1. 提取 HarmonyOS 技术术语（权限名、API名等）
        # 权限名：ohos.permission.*
        permission_pattern = r'ohos\.permission\.[a-zA-Z_]+'
        permissions = re.findall(permission_pattern, text)
        keywords.update(permissions)

        # API 名：@kit.Xxx.yyy
        api_pattern = r'@kit\.[a-zA-Z]+'
        apis = re.findall(api_pattern, text)
        keywords.update(apis)

        # 类名/接口名：UIAbility, AbilityContext 等
        class_pattern = r'\b[A-Z][a-zA-Z]+(?:Ability|Context|Manager|Kit|Service)\b'
        classes = re.findall(class_pattern, text)
        keywords.update(classes)

        # 2. 中文分词
        try:
            import jieba
            words = jieba.cut(text)
            # 过滤停用词和短词，保留有意义的关键词
            keywords.update([w for w in words if len(w) > 1])
        except:
            # 如果 jieba 不可用，使用简单的词边界分割
            words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
            keywords.update(words)

        return list(keywords)

    def _keyword_match_score(self, keywords: List[str], text: str) -> float:
        """
        计算关键词匹配分数，技术术语权重更高
        """
        if not keywords:
            return 0.0

        text_lower = text.lower()
        score = 0.0
        total_weight = 0.0

        for kw in keywords:
            weight = 1.0
            # 技术术语权重更高
            if kw.startswith('ohos.permission'):
                weight = 3.0
            elif kw.startswith('ohos.') or kw.startswith('@kit.'):
                weight = 2.0
            elif kw.endswith('Ability') or kw.endswith('Context') or kw.endswith('Kit'):
                weight = 1.5

            total_weight += weight
            if kw.lower() in text_lower:
                score += weight

        return min(score / total_weight, 1.0) if total_weight > 0 else 0.0

    def get_context(self, query: str, max_length: int = 2000) -> str:
        """
        获取查询的上下文文本

        Args:
            query: 查询文本
            max_length: 最大上下文长度

        Returns:
            上下文文本
        """
        results = self.retrieve(query)

        context_parts = []
        current_length = 0

        for result in results:
            doc_text = result['document']
            source = result['metadata'].get('source', 'Unknown')

            # 添加来源信息
            part = f"[{source}]\n{doc_text}\n\n"

            if current_length + len(part) > max_length:
                # 截断最后一个部分
                remaining = max_length - current_length
                if remaining > 50:
                    context_parts.append(part[:remaining] + "...")
                break

            context_parts.append(part)
            current_length += len(part)

        return ''.join(context_parts)

    def retrieve_with_expansion(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
        min_score: float = 0.3,
        collection_name: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], bool]:
        """
        增强检索：查询扩展 + 置信度阈值

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter: 元数据过滤条件
            min_score: 最低分数阈值
            collection_name: 集合名称（资料库 ID）

        Returns:
            (检索结果列表, 是否满足置信度要求)
        """
        # 查询扩展
        expander = get_query_expander()
        expanded_queries = expander.expand_query(query)

        logger.debug(f"Query expansion: '{query}' -> {expanded_queries}")

        # 对每个扩展查询进行检索
        all_results = {}

        for expanded_query in expanded_queries:
            query_embedding = self.embedder.embed_text(expanded_query)
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k or self.top_k,
                filter=filter,
                collection_name=collection_name,
            )

            for result in results:
                doc_id = result['id']
                if doc_id not in all_results or result['score'] > all_results[doc_id]['score']:
                    all_results[doc_id] = result

        # 按分数排序
        sorted_results = sorted(all_results.values(), key=lambda x: x['score'], reverse=True)

        # 取 top_k 结果
        top_k = top_k or self.top_k
        final_results = sorted_results[:top_k]

        # 检查置信度
        if final_results:
            max_score = final_results[0]['score']
            meets_threshold = max_score >= min_score

            if not meets_threshold:
                logger.warning(f"Low confidence query: '{query}' (max_score: {max_score:.3f} < {min_score})")

            return final_results, meets_threshold

        return final_results, False

    def retrieve_with_permission_filter(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        带权限过滤的检索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter: 元数据过滤条件
            collection_name: 集合名称（资料库 ID）

        Returns:
            (检索结果列表, 匹配的权限列表)
        """
        # 检索权限索引
        perm_index = get_permission_index()

        # 提取查询中的权限相关关键词
        query_lower = query.lower()
        mentioned_perms = perm_index.search_permissions(query_lower)

        logger.debug(f"Permission filter: found {len(mentioned_perms)} permissions in query: {mentioned_perms}")

        matched_sources = []
        if mentioned_perms:
            for perm in mentioned_perms:
                sources = perm_index.get_sources(perm)
                matched_sources.extend(sources)
                logger.debug(f"Permission {perm} found in: {sources}")

        # 如果没有找到权限相关文档，按正常检索
        if not matched_sources:
            results = self.retrieve(query, top_k=top_k, filter=filter, collection_name=collection_name)
            return results, []

        # 否则，检索并过滤
        all_results = self.retrieve(query, top_k=top_k * 2, filter=filter, collection_name=collection_name)

        # 过滤只保留匹配权限的文档
        filtered_results = [
            r for r in all_results
            if r['metadata'].get('source') in matched_sources
        ]

        return filtered_results[:top_k or self.top_k], mentioned_perms

    def smart_retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict[str, Any]] = None,
        min_score: float = 0.3,
        collection_name: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], bool, Dict[str, Any]]:
        """
        智能检索：自动选择最佳检索策略

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter: 元数据过滤条件
            min_score: 最低分数阈值
            collection_name: 集合名称（资料库 ID）

        Returns:
            (检索结果列表, 是否满足置信度要求, 检索元数据)
        """
        metadata = {
            'method': 'standard',
            'permissions_found': [],
            'expansion_count': 0,
        }

        # 检查是否是权限相关查询
        permission_keywords = ['权限', 'permission', '申请', '声明']
        is_permission_query = any(kw in query.lower() for kw in permission_keywords)

        if is_permission_query:
            # 使用查询扩展获取权限名
            expander = get_query_expander()
            expanded_queries = expander.expand_query(query)
            metadata['expansion_count'] = len(expanded_queries)

            # 提取扩展查询中的权限名
            permissions_mentioned = []
            for q in expanded_queries:
                perm_match = re.search(r'ohos\.permission\.[a-zA-Z0-9_]+', q)
                if perm_match:
                    perm = perm_match.group(0)
                    if perm not in permissions_mentioned:
                        permissions_mentioned.append(perm)

            logger.info(f"Permission query detected, permissions mentioned in expansion: {permissions_mentioned}")

            if permissions_mentioned:
                metadata['method'] = 'permission_direct'
                metadata['permissions_found'] = permissions_mentioned

                # 从权限索引获取相关文档
                perm_index = get_permission_index()
                matched_sources = set()
                for perm in permissions_mentioned:
                    sources = perm_index.get_sources(perm)
                    matched_sources.update(sources)
                    logger.info(f"Permission {perm} found in {len(sources)} documents")

                if matched_sources and collection_name:
                    # 获取指定集合
                    collection = self.vector_store.get_collection(collection_name)

                    # 直接获取这些文档的chunks
                    all_chunks = []
                    for source in list(matched_sources)[:50]:  # 限制防止过多
                        # 获取该来源的所有文档（不限制数量）
                        chunks = collection.get(
                            where={"source": source},
                            limit=100  # ChromaDB v0.6.0+ uses limit instead of n_results
                        )
                        for i, (doc, met, doc_id) in enumerate(zip(chunks['documents'], chunks['metadatas'], chunks['ids'])):
                            all_chunks.append({
                                'id': doc_id,
                                'document': doc,
                                'metadata': met,
                                'score': 1.0,  # 权限匹配给满分
                            })

                    # 如果权限文档不足，补充向量搜索结果
                    if len(all_chunks) < top_k * 2:
                        vec_results, _ = self.retrieve_with_expansion(
                            query=query,
                            top_k=top_k * 2,
                            filter=filter,
                            min_score=0.2,
                            collection_name=collection_name,
                        )
                        for r in vec_results:
                            if r['id'] not in [c['id'] for c in all_chunks]:
                                all_chunks.append(r)

                    # 按分数排序（权限匹配的优先）
                    all_chunks.sort(key=lambda x: x['score'], reverse=True)
                    final_results = all_chunks[:top_k or self.top_k]

                    meets_threshold = final_results[0]['score'] >= min_score if final_results else False
                    return final_results, meets_threshold, metadata

        # 使用增强检索（查询扩展 + 置信度阈值）
        results, meets_threshold = self.retrieve_with_expansion(
            query=query,
            top_k=top_k,
            filter=filter,
            min_score=min_score,
            collection_name=collection_name,
        )

        expander = get_query_expander()
        expanded_queries = expander.expand_query(query)
        metadata['expansion_count'] = len(expanded_queries)

        return results, meets_threshold, metadata


# 单例模式
_retriever_instance = None


def get_retriever() -> Retriever:
    """获取检索器单例"""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    return _retriever_instance

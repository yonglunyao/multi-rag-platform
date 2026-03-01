"""
重排序器：使用 Cross-Encoder 重新排序检索结果

支持 BGE-Reranker、Cohere Reranker 和 LLM 辅助重排序
"""
import re
import time
import json
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger


class BaseReranker:
    """重排序器基类"""

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        重排序文档

        Args:
            query: 查询文本
            documents: 检索结果列表
            top_k: 返回结果数量

        Returns:
            重排序后的文档列表
        """
        raise NotImplementedError


class NoOpReranker(BaseReranker):
    """无操作重排序器（默认，用于性能优先场景）"""

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """返回原样文档"""
        return documents[:top_k] if top_k else documents


class ScoreBoostReranker(BaseReranker):
    """分数提升重排序器 - 基于关键词匹配提升分数"""

    def __init__(self, boost_factor: float = 1.2):
        """
        初始化分数提升重排序器

        Args:
            boost_factor: 匹配关键词时的提升倍数
        """
        self.boost_factor = boost_factor

        # 关键词匹配规则
        self.keyword_patterns = {
            # 权限名匹配优先级最高
            'permission': [
                r'ohos\.permission\.\w+',
                r'权限',
                r'permission',
            ],
            # API名匹配
            'api': [
                r'@\w+\.\w+\.\w+',  # @ohos.xxx
                r'\w+\.\w+\(',       # function(
            ],
            # Kit名匹配
            'kit': [
                r'\w+Kit',
                r'\w+套件',
            ],
            # 特殊术语
            'technical': [
                r'UIAbility',
                r'ServiceAbility',
                r'BackgroundTask',
                r'MDM',
                r'BYOD',
                r'Wi-Fi',
            ],
        }

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """基于关键词匹配提升分数"""
        results = []
        query_lower = query.lower()

        # 首先计算所有文档的boost
        doc_boosts = []
        for doc in documents:
            boost = self._calculate_boost(query_lower, doc)
            doc_boosts.append((doc, boost))

        # 找到最大boost值用于归一化
        max_boost = max(boost for _, boost in doc_boosts) if doc_boosts else 1.0

        # 重新计算分数，使用加法而不是乘法
        for doc, boost in doc_boosts:
            reranked_doc = doc.copy()
            original_score = doc.get('score', 0)

            # 使用加法bonus：标题匹配好的文档获得额外分数
            # 归一化boost到0-0.3范围，避免过度影响
            normalized_boost = (boost - 1.0) / (max_boost - 1.0) if max_boost > 1.0 else 0
            title_bonus = normalized_boost * 0.3  # 最高加0.3分

            reranked_doc['score'] = min(original_score + title_bonus, 1.0)
            reranked_doc['original_score'] = original_score
            reranked_doc['title_bonus'] = title_bonus
            reranked_doc['boost'] = boost

            results.append(reranked_doc)

        # 按新分数排序
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[:top_k] if top_k else results

    def _calculate_boost(self, query_lower: str, doc: Dict[str, Any]) -> float:
        """计算提升因子"""
        boost = 1.0

        # 在文档内容中搜索
        content = doc.get('document', '').lower()
        metadata_str = str(doc.get('metadata', {})).lower()

        # 从标题获取额外权重 - 改进版：计算标题匹配度
        title = doc.get('metadata', {}).get('title', '').lower()
        if title:
            # 提取查询中的关键词（去除常见停用词）
            query_terms = set(query_lower.split())
            stop_words = {'的', '了', '是', '在', '和', '与', '或', '和', 'the', 'a', 'an', 'of', 'for'}
            query_keywords = query_terms - stop_words

            # 计算标题中包含的关键词数量
            title_keyword_matches = sum(1 for term in query_keywords if term in title)

            # 根据标题匹配度给予不同的提升
            if title_keyword_matches >= len(query_keywords):
                # 标题包含所有查询关键词 - 最高优先级
                boost *= 3.0
            elif title_keyword_matches >= len(query_keywords) * 0.7:
                # 标题包含70%以上查询关键词
                boost *= 2.0
            elif title_keyword_matches > 0:
                # 标题包含部分关键词
                boost *= 1.5

        # 检查各种关键词模式 - 仅用于内容匹配，降低权重
        for category, patterns in self.keyword_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    # 在内容中匹配 - 降低权重避免过度偏向长文档
                    if re.search(pattern, content):
                        boost *= (1.05 if category in ['permission', 'api'] else 1.02)
                    # 在元数据中匹配
                    if re.search(pattern, metadata_str):
                        boost *= (1.03 if category in ['permission', 'api'] else 1.01)

        return boost


class BM25Reranker(BaseReranker):
    """BM25重排序器 - 基于关键词匹配度"""

    def __init__(self, k1: float = 1.5, k3: float = 0.75):
        """
        初始化BM25重排序器

        Args:
            k1: 词频饱和参数
            k3: 文档长度归一化参数
        """
        self.k1 = k1
        self.k3 = k3
        self.avg_doc_length = 500  # 假设平均文档长度

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """使用BM25算法重排序"""
        import jieba

        # 分词
        query_terms = set(jieba.lcut(query.lower()))

        results = []
        for doc in documents:
            reranked_doc = doc.copy()
            content = doc.get('document', '')
            metadata = doc.get('metadata', {})

            # 从标题和内容计算BM25分数
            text_content = metadata.get('title', '') + ' ' + content
            terms = jieba.lcut(text_content.lower())
            doc_length = len(terms)

            # 计算BM25分数
            bm25_score = 0.0
            for term in query_terms:
                # 词频
                tf = terms.count(term)
                if tf == 0:
                    continue

                # IDF (简化版，使用log)
                idf = 1.0

                # BM25公式简化版
                num = tf * (self.k1 + 1)
                denom = tf + self.k1
                bm25_score += idf * (num / denom)

            # 文档长度归一化
            if doc_length > 0:
                bm25_score /= (1 + self.k3 * (doc_length / self.avg_doc_length))

            # 结合原始分数
            original_score = doc.get('score', 0)
            reranked_doc['score'] = 0.7 * original_score + 0.3 * min(bm25_score / 10, 1.0)
            reranked_doc['original_score'] = original_score
            reranked_doc['bm25_score'] = bm25_score

            results.append(reranked_doc)

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k] if top_k else results


class CrossEncoderReranker(BaseReranker):
    """Cross-Encoder 重排序器 - 最高精度

    使用 BGE-Reranker 模型进行深度语义重排序
    精度最高，但需要加载额外的模型
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        """
        初始化 Cross-Encoder 重排序器

        Args:
            model_name: 重排序模型名称
                - BAAI/bge-reranker-v2-m3: 多语言，轻量级（推荐）
                - BAAI/bge-reranker-large: 中英文，高精度
        """
        self.model_name = model_name
        self._model = None
        self._load_model()

    def _load_model(self):
        """懒加载模型"""
        if self._model is None:
            try:
                from FlagEmbedding import FlagReranker
                self._model = FlagReranker(
                    self.model_name,
                    device='cpu',
                    use_fp16=False
                )
                logger.info(f"Loaded Cross-Encoder reranker: {self.model_name}")
            except ImportError:
                logger.warning("FlagEmbedding not installed, falling back to BM25")
                # 降级到 BM25
                self._model = "fallback"
            except Exception as e:
                logger.warning(f"Failed to load Cross-Encoder: {e}, falling back to BM25")
                self._model = "fallback"

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """使用 Cross-Encoder 模型重排序"""
        # 如果模型加载失败，使用 BM25 降级
        if self._model == "fallback":
            return BM25Reranker().rerank(query, documents, top_k)

        # 准备查询-文档对
        pairs = [[query, doc.get('document', '')[:512]] for doc in documents]  # 限制长度

        # 计算相关性分数
        scores = self._model.compute_score(pairs, normalize=True)

        # 更新分数
        for doc, score in zip(documents, scores):
            reranked_doc = doc.copy()
            # Cross-Encoder 分数范围 [0, 1]，直接替换原始分数
            reranked_doc['score'] = float(score)
            reranked_doc['original_score'] = doc.get('score', 0)
            reranked_doc['cross_encoder_score'] = float(score)
            results.append(reranked_doc)

        results = []
        for doc, score in zip(documents, scores):
            reranked_doc = doc.copy()
            reranked_doc['score'] = float(score)
            reranked_doc['original_score'] = doc.get('score', 0)
            reranked_doc['cross_encoder_score'] = float(score)
            results.append(reranked_doc)

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[:top_k] if top_k else results


class LLMReranker(BaseReranker):
    """LLM 辅助重排序器 - 使用本地 LLM 进行语义重排序

    利用 Ollama 运行的本地 LLM 对文档进行语义相关性打分
    """

    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        max_candidates: int = 10,
        temperature: float = 0.1,
    ):
        """
        初始化 LLM 重排序器

        Args:
            ollama_base_url: Ollama API 地址
            model: LLM 模型名称
            max_candidates: 最多评分的文档数
            temperature: 生成温度 (越低越确定)
        """
        self.ollama_base_url = ollama_base_url
        self.model = model
        self.max_candidates = max_candidates
        self.temperature = temperature
        self._available = self._check_available()

    def _check_available(self) -> bool:
        """检查 Ollama 是否可用"""
        try:
            import requests
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            logger.warning(f"Ollama not available at {self.ollama_base_url}")
            return False

    def _score_document(self, query: str, document: str) -> float:
        """使用 LLM 对单个文档打分"""
        prompt = f"""请给查询和文档的相关性打分，返回0-10之间的分数。

查询: {query}

文档内容: {document[:500]}

只返回数字分数，不要其他内容。"""

        try:
            import requests
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self.temperature}
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                score_text = result.get("response", "").strip()
                # 提取数字
                import re
                match = re.search(r'(\d+(?:\.\d+)?)', score_text)
                if match:
                    score = float(match.group(1))
                    return min(score / 10.0, 1.0)  # 归一化到 [0,1]
            return 0.0
        except Exception as e:
            logger.debug(f"LLM scoring error: {e}")
            return 0.0

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """使用 LLM 重排序"""
        if not self._available:
            logger.warning("LLM reranker unavailable, returning original order")
            return documents[:top_k] if top_k else documents

        # 限制候选文档数量
        candidates = documents[:self.max_candidates]

        # 并行评分
        llm_scores = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    self._score_document,
                    query,
                    doc.get('document', '')
                ): i for i, doc in enumerate(candidates)
            }

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    score = future.result(timeout=15)
                    llm_scores[idx] = score
                except:
                    llm_scores[idx] = 0.0

        # 更新分数
        results = []
        for i, doc in enumerate(candidates):
            reranked_doc = doc.copy()
            llm_score = llm_scores.get(i, 0.0)
            original_score = doc.get('score', 0)

            # 结合分数: 50% LLM + 50% 原始
            reranked_doc['score'] = 0.5 * original_score + 0.5 * llm_score
            reranked_doc['original_score'] = original_score
            reranked_doc['llm_score'] = llm_score

            results.append(reranked_doc)

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[:top_k] if top_k else results


class RerankerManager:
    """重排序器管理器"""

    def __init__(self, reranker_type: str = 'score_boost'):
        """
        初始化重排序器管理器

        Args:
            reranker_type: 重排序器类型
                - 'score_boost': 快速关键词匹配（默认）
                - 'bm25': BM25 算法
                - 'llm': LLM 辅助语义重排序
                - 'cross_encoder': Cross-Encoder 模型（需要额外依赖）
                - 'none': 禁用重排序
        """
        self.reranker_type = reranker_type
        self._reranker = self._create_reranker(reranker_type)

    def _create_reranker(self, reranker_type: str) -> BaseReranker:
        """创建重排序器实例"""
        if reranker_type == 'score_boost':
            return ScoreBoostReranker(boost_factor=1.2)
        elif reranker_type == 'bm25':
            return BM25Reranker()
        elif reranker_type == 'llm':
            return LLMReranker()
        elif reranker_type == 'cross_encoder':
            return CrossEncoderReranker()
        else:
            return NoOpReranker()

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """重排序文档"""
        start_time = time.time()
        results = self._reranker.rerank(query, documents, top_k)
        elapsed = time.time() - start_time

        logger.debug(f"Reranker ({self.reranker_type}): reranked {len(documents)} docs in {elapsed:.3f}s")

        return results

    def set_reranker_type(self, reranker_type: str):
        """动态切换重排序器类型"""
        if reranker_type != self.reranker_type:
            self.reranker_type = reranker_type
            self._reranker = self._create_reranker(reranker_type)
            logger.info(f"Reranker switched to: {reranker_type}")


# 全局单例
_reranker_manager_instance: Optional[RerankerManager] = None


def get_reranker() -> RerankerManager:
    """获取重排序器管理器单例"""
    global _reranker_manager_instance
    if _reranker_manager_instance is None:
        import os

        # 优先从配置文件读取，然后从环境变量读取
        reranker_type = 'score_boost'

        try:
            from core.config import get_config
            config = get_config()
            if config.global_config and hasattr(config.global_config, 'reranker_type'):
                reranker_type = config.global_config.reranker_type
                logger.debug(f"Using reranker_type from config: {reranker_type}")
        except Exception as e:
            logger.debug(f"Could not load reranker_type from config: {e}")

        # 环境变量优先级最高
        reranker_type = os.getenv('RERANKER_TYPE', reranker_type)

        _reranker_manager_instance = RerankerManager(reranker_type)
        logger.info(f"Initialized reranker: {reranker_type}")
    return _reranker_manager_instance


def get_use_reranker() -> bool:
    """获取是否启用重排序器"""
    import os

    # 优先从配置文件读取
    try:
        from core.config import get_config
        config = get_config()
        if config.global_config and hasattr(config.global_config, 'use_reranker'):
            return config.global_config.use_reranker
    except Exception:
        pass

    # 从环境变量读取
    return os.getenv('USE_RERANKER', 'true').lower() == 'true'

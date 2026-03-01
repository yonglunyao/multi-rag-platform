"""
查询结果缓存模块

使用LRU缓存存储查询结果，减少重复查询的响应时间
"""
import hashlib
import json
import time
from typing import Dict, Any, Optional, List
from functools import lru_cache
from loguru import logger


class QueryCache:
    """查询结果缓存"""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        初始化缓存

        Args:
            max_size: 最大缓存条目数
            ttl: 缓存过期时间（秒），默认1小时
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, tuple[list, float]] = {}
        self._hits = 0
        self._misses = 0

    def _generate_key(self, query: str, top_k: int, collection: str = None, filter: Dict = None) -> str:
        """生成缓存键"""
        # 将查询参数序列化为字符串
        params = {
            "query": query,
            "top_k": top_k,
            "collection": collection,
            "filter": sorted(filter.items()) if filter else None
        }
        params_str = json.dumps(params, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(params_str.encode()).hexdigest()

    def get(self, query: str, top_k: int = 5, collection: str = None, filter: Dict = None) -> Optional[List[Dict]]:
        """
        获取缓存结果

        Args:
            query: 查询文本
            top_k: 返回结果数量
            collection: 集合名称
            filter: 过滤条件

        Returns:
            缓存的结果列表，如果未命中或过期则返回None
        """
        key = self._generate_key(query, top_k, collection, filter)

        if key not in self._cache:
            self._misses += 1
            return None

        results, timestamp = self._cache[key]

        # 检查是否过期
        if time.time() - timestamp > self.ttl:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        logger.debug(f"Cache hit for query: {query[:50]}...")
        return results

    def set(self, query: str, results: List[Dict], top_k: int = 5, collection: str = None, filter: Dict = None):
        """
        设置缓存

        Args:
            query: 查询文本
            results: 检索结果
            top_k: 返回结果数量
            collection: 集合名称
            filter: 过滤条件
        """
        key = self._generate_key(query, top_k, collection, filter)

        # LRU淘汰策略
        if len(self._cache) >= self.max_size and key not in self._cache:
            # 删除最旧的条目
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        self._cache[key] = (results, time.time())
        logger.debug(f"Cached query: {query[:50]}... (cache size: {len(self._cache)})")

    def invalidate(self, query: str = None, collection: str = None):
        """
        使缓存失效

        Args:
            query: 指定查询，如果为None则清除所有
            collection: 指定集合，如果为None则清除所有
        """
        if query is None and collection is None:
            self._cache.clear()
            logger.info("Cache cleared")
            return

        # 删除匹配的缓存条目
        keys_to_delete = []
        for key in self._cache:
            if collection and collection in key:
                keys_to_delete.append(key)
            elif query and query in key:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._cache[key]

        logger.info(f"Invalidated {len(keys_to_delete)} cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "ttl": self.ttl
        }

    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache cleared and stats reset")


# 全局缓存实例
_query_cache: Optional[QueryCache] = None


def get_query_cache() -> QueryCache:
    """获取全局查询缓存实例"""
    global _query_cache
    if _query_cache is None:
        # 从配置读取缓存参数
        try:
            from core.config import get_config
            config = get_config()
            cache_enabled = config.global_config.enable_cache if hasattr(config.global_config, 'enable_cache') else True
            cache_ttl = config.global_config.cache_ttl if hasattr(config.global_config, 'cache_ttl') else 3600
        except Exception:
            cache_enabled = True
            cache_ttl = 3600

        if cache_enabled:
            _query_cache = QueryCache(max_size=1000, ttl=cache_ttl)
            logger.info(f"Query cache enabled (TTL: {cache_ttl}s)")
        else:
            _query_cache = QueryCache(max_size=0)  # 禁用缓存
            logger.info("Query cache disabled")

    return _query_cache

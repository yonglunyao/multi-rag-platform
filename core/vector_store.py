"""
向量数据库：使用 ChromaDB 存储和检索文档向量

支持多集合模式，每个资料库使用独立的集合
"""
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from loguru import logger
import chromadb
from chromadb.config import Settings


class VectorStore:
    """向量数据库封装 - 支持多集合"""

    # 默认集合名（向后兼容）
    DEFAULT_COLLECTION = "harmony_docs"

    def __init__(
        self,
        persist_dir: str = None,
        collection_name: str = None,
    ):
        """
        初始化向量数据库

        Args:
            persist_dir: 数据持久化目录
            collection_name: 默认集合名称（向后兼容）
        """
        load_dotenv()

        self.persist_dir = persist_dir or os.getenv('CHROMA_PERSIST_DIR', './data/vectorstore')
        self.collection_name = collection_name or os.getenv('COLLECTION_NAME', self.DEFAULT_COLLECTION)

        # 确保目录存在
        os.makedirs(self.persist_dir, exist_ok=True)

        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )

        # 集合缓存 (懒加载)
        self._collections: Dict[str, Any] = {}

        # 向后兼容：初始化默认集合
        self.collection = self._get_or_create_collection(self.collection_name)

        logger.info(f"VectorStore initialized: {self.collection_name} at {self.persist_dir}")

    def _get_or_create_collection(self, collection_name: str):
        """
        获取或创建指定集合

        Args:
            collection_name: 集合名称

        Returns:
            ChromaDB Collection 对象
        """
        # 检查缓存
        if collection_name in self._collections:
            return self._collections[collection_name]

        # 尝试获取现有集合
        try:
            collection = self.client.get_collection(name=collection_name)
            logger.info(f"Using existing collection: {collection_name}")
        except Exception:
            # 集合不存在，创建新集合
            logger.info(f"Creating new collection: {collection_name}")
            collection = self.client.create_collection(name=collection_name)

        # 缓存集合
        self._collections[collection_name] = collection
        return collection

    def get_collection(self, collection_name: str):
        """
        获取指定资料库的集合

        Args:
            collection_name: 集合名称（通常为 lib_{library_id}）

        Returns:
            ChromaDB Collection 对象
        """
        return self._get_or_create_collection(collection_name)

    def list_collections(self) -> List[str]:
        """
        列出所有集合

        Returns:
            List[str]: 集合名称列表
        """
        try:
            # ChromaDB v0.6.0+ returns list of collection names (strings)
            return self.client.list_collections()
        except Exception:
            return []

    def delete_collection(self, collection_name: str) -> bool:
        """
        删除指定集合

        Args:
            collection_name: 集合名称

        Returns:
            bool: 是否成功删除
        """
        try:
            # 从缓存移除
            if collection_name in self._collections:
                del self._collections[collection_name]

            # 删除集合
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            return False

    def collection_exists(self, collection_name: str) -> bool:
        """
        检查集合是否存在

        Args:
            collection_name: 集合名称

        Returns:
            bool: 集合是否存在
        """
        return collection_name in self.list_collections()

    def migrate_collection(self, old_name: str, new_name: str) -> bool:
        """
        迁移集合（重命名）

        Args:
            old_name: 旧集合名
            new_name: 新集合名

        Returns:
            bool: 是否成功迁移
        """
        try:
            # 检查新集合是否已存在
            if self.collection_exists(new_name):
                logger.warning(f"Target collection already exists: {new_name}")
                return False

            # 获取旧集合数据
            old_collection = self._get_or_create_collection(old_name)
            count = old_collection.count()

            if count == 0:
                logger.info(f"Old collection is empty: {old_name}")
                # 直接创建新集合
                self._get_or_create_collection(new_name)
                return True

            # 获取所有数据
            logger.info(f"Migrating {count} documents from {old_name} to {new_name}")
            data = old_collection.get()

            # 创建新集合
            new_collection = self.client.create_collection(new_name)

            # 批量添加数据
            batch_size = 5000
            for i in range(0, count, batch_size):
                end_idx = min(i + batch_size, count)
                batch_ids = data['ids'][i:end_idx]
                batch_docs = data['documents'][i:end_idx]
                batch_embeds = data['embeddings'][i:end_idx] if data.get('embeddings') else None
                batch_metas = data['metadatas'][i:end_idx] if data.get('metadatas') else None

                new_collection.add(
                    ids=batch_ids,
                    documents=batch_docs,
                    embeddings=batch_embeds,
                    metadatas=batch_metas,
                )
                logger.info(f"Migrated {end_idx}/{count} documents")

            # 更新缓存
            self._collections[new_name] = new_collection

            logger.info(f"Migration completed: {old_name} -> {new_name}")
            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False

    def add_texts(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
        collection_name: Optional[str] = None,
    ):
        """
        添加文档到向量数据库

        Args:
            texts: 文档文本列表
            embeddings: 嵌入向量列表
            metadatas: 元数据列表
            ids: 文档ID列表（可选，自动生成）
            collection_name: 集合名称（可选，默认使用初始化时的集合）
        """
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(texts))]

        # 使用指定集合或默认集合
        collection = self._get_or_create_collection(collection_name or self.collection_name)

        collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"Added {len(texts)} documents to collection: {collection.name}")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索

        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            filter: 元数据过滤条件
            collection_name: 集合名称（可选，默认使用初始化时的集合）

        Returns:
            搜索结果列表
        """
        # 使用指定集合或默认集合
        collection = self._get_or_create_collection(collection_name or self.collection_name)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter,
        )

        # 格式化结果
        formatted_results = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'score': 1 - results['distances'][0][i],  # 转换为相似度分数
                })

        return formatted_results

    def get_stats(self, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取集合统计信息

        Args:
            collection_name: 集合名称（可选，默认使用初始化时的集合）

        Returns:
            统计信息字典
        """
        # 使用指定集合或默认集合
        collection = self._get_or_create_collection(collection_name or self.collection_name)
        count = collection.count()

        return {
            'collection_name': collection.name,
            'document_count': count,
            'persist_dir': self.persist_dir,
        }

    def reset(self, collection_name: Optional[str] = None):
        """
        清空集合

        Args:
            collection_name: 集合名称（可选，默认使用初始化时的集合）
        """
        name = collection_name or self.collection_name

        # 从缓存移除
        if name in self._collections:
            del self._collections[name]

        # 重新创建集合
        self.client.delete_collection(name)
        new_collection = self.client.create_collection(name)
        self._collections[name] = new_collection

        # 如果是默认集合，更新引用
        if name == self.collection_name:
            self.collection = new_collection

        logger.info(f"Reset collection: {name}")

    def count(self, collection_name: Optional[str] = None) -> int:
        """
        获取集合文档数量

        Args:
            collection_name: 集合名称（可选，默认使用初始化时的集合）

        Returns:
            int: 文档数量
        """
        collection = self._get_or_create_collection(collection_name or self.collection_name)
        return collection.count()


# 单例模式
_vector_store_instance = None


def get_vector_store() -> VectorStore:
    """获取向量存储单例"""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance

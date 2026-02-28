"""
数据导出器

支持将资料库数据导出为可移植格式，用于迁移到其他 RAG 系统
"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from loguru import logger

from core.library_manager import get_library_manager
from core.vector_store import get_vector_store


class DataExporter:
    """
    数据导出器

    支持将资料库数据导出为 JSON 格式，便于迁移到其他 RAG 系统
    """

    def export_library(
        self,
        library_id: str,
        output_path: str,
        format: str = "json",
        include_embeddings: bool = True,
    ) -> str:
        """
        导出资料库数据

        Args:
            library_id: 资料库 ID
            output_path: 输出文件路径
            format: 导出格式（目前仅支持 json）
            include_embeddings: 是否包含嵌入向量

        Returns:
            str: 导出文件路径
        """
        if format != "json":
            raise ValueError(f"不支持的导出格式: {format}")

        logger.info(f"开始导出资料库: {library_id}")

        # 获取资料库配置
        manager = get_library_manager()
        lib = manager.get_library(library_id)

        if lib is None:
            raise ValueError(f"资料库不存在: {library_id}")

        # 获取向量存储
        vector_store = get_vector_store()
        collection = vector_store.get_collection(lib.collection_name)

        # 获取所有数据
        count = collection.count()
        logger.info(f"导出 {count} 个文档块")

        data = collection.get()

        # 构建导出数据
        export_data = {
            "version": "2.0",
            "library_id": library_id,
            "exported_at": datetime.now().isoformat(),
            "config": {
                "id": lib.id,
                "name": lib.name,
                "type": lib.type.value,
                "source_path": lib.source_path,
                "embedding_model": lib.embedding_config.model_name,
                "embedding_dimension": lib.embedding_config.dimension,
                "chunk_size": lib.chunking_config.chunk_size,
                "chunk_overlap": lib.chunking_config.chunk_overlap,
            },
            "documents": [],
        }

        # 处理每个文档块
        for i, (doc_id, doc_text, metadata) in enumerate(zip(
            data.get('ids', []),
            data.get('documents', []),
            data.get('metadatas', []),
        )):
            doc_data = {
                "id": doc_id,
                "content": doc_text,
                "metadata": metadata,
            }

            # 可选：包含嵌入向量
            if include_embeddings and 'embeddings' in data:
                if i < len(data['embeddings']):
                    doc_data["embedding"] = data['embeddings'][i]

            export_data["documents"].append(doc_data)

        # 写入文件
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        logger.info(f"导出完成: {output_path} ({output_path.stat().st_size} bytes)")

        return str(output_path)

    def import_library(
        self,
        input_path: str,
        target_library_id: Optional[str] = None,
    ) -> str:
        """
        从导出文件导入数据

        Args:
            input_path: 导入文件路径
            target_library_id: 目标资料库 ID（可选，默认使用导出文件中的 ID）

        Returns:
            str: 导入的资料库 ID
        """
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"导入文件不存在: {input_path}")

        logger.info(f"开始导入数据: {input_path}")

        # 读取导出数据
        with open(input_path, 'r', encoding='utf-8') as f:
            export_data = json.load(f)

        # 验证版本
        version = export_data.get("version", "1.0")
        if not version.startswith(("1.", "2.")):
            raise ValueError(f"不支持的导出版本: {version}")

        # 获取或创建资料库 ID
        library_id = target_library_id or export_data.get("library_id", "imported")

        # 获取向量存储
        vector_store = get_vector_store()
        collection_name = f"lib_{library_id}"

        # 如果集合已存在，先删除
        if vector_store.collection_exists(collection_name):
            logger.warning(f"目标集合已存在，将被覆盖: {collection_name}")
            vector_store.delete_collection(collection_name)

        # 创建新集合
        collection = vector_store.get_collection(collection_name)

        # 批量添加文档
        documents = export_data.get("documents", [])
        logger.info(f"导入 {len(documents)} 个文档块")

        # 分批处理
        batch_size = 1000
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            ids = [doc.get("id", f"doc_{i + j}") for j, doc in enumerate(batch)]
            texts = [doc.get("content", "") for doc in batch]
            metadatas = [doc.get("metadata", {}) for doc in batch]

            # 提取嵌入向量（如果有）
            embeddings = None
            if "embedding" in batch[0]:
                embeddings = [doc.get("embedding") for doc in batch]

            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=embeddings,
            )

            logger.info(f"已导入 {min(i + batch_size, len(documents))}/{len(documents)} 个文档块")

        logger.info(f"导入完成: {library_id}")

        return library_id

    def get_export_summary(self, library_id: str) -> dict:
        """
        获取资料库导出摘要信息

        Args:
            library_id: 资料库 ID

        Returns:
            dict: 摘要信息
        """
        manager = get_library_manager()
        lib = manager.get_library(library_id)

        if lib is None:
            raise ValueError(f"资料库不存在: {library_id}")

        vector_store = get_vector_store()
        collection = vector_store.get_collection(lib.collection_name)
        count = collection.count()

        return {
            "library_id": library_id,
            "name": lib.name,
            "type": lib.type.value,
            "chunk_count": count,
            "embedding_model": lib.embedding_config.model_name,
            "embedding_dimension": lib.embedding_config.dimension,
            "estimated_size_mb": count * lib.embedding_config.dimension * 4 / (1024 * 1024),
        }

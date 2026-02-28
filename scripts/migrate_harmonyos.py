#!/usr/bin/env python3
"""
数据迁移脚本

将旧的 harmony_docs 集合迁移到新的 lib_harmonyos 集合
同时创建资料库配置文件
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from core.vector_store import get_vector_store
from core.library_manager import get_library_manager
from core.models import LibraryConfig, LibraryType, LibraryStatus, EmbeddingConfig, ChunkingConfig


def migrate_harmonyos_data():
    """迁移 HarmonyOS 数据到新格式"""
    logger.info("开始迁移 HarmonyOS 数据...")

    # 1. 获取向量存储
    vector_store = get_vector_store()

    # 2. 检查旧集合是否存在
    old_collection = "harmony_docs"
    new_collection = "lib_harmonyos"

    if not vector_store.collection_exists(old_collection):
        logger.warning(f"旧集合不存在: {old_collection}，跳过迁移")
        # 直接创建新配置
    else:
        logger.info(f"发现旧集合: {old_collection}")

        # 3. 迁移集合
        if vector_store.collection_exists(new_collection):
            logger.warning(f"新集合已存在: {new_collection}，将被覆盖")
            vector_store.delete_collection(new_collection)

        success = vector_store.migrate_collection(old_collection, new_collection)
        if success:
            logger.info(f"集合迁移成功: {old_collection} -> {new_collection}")
        else:
            logger.error("集合迁移失败")
            return False

    # 4. 创建/更新资料库配置
    manager = get_library_manager()
    config = manager.load_config()

    # 检查是否已存在 harmonyos 配置
    if "harmonyos" in config.libraries:
        logger.info("资料库配置已存在，更新集合名称")
        lib = config.libraries["harmonyos"]
        lib.collection_name = new_collection
    else:
        # 从环境变量读取配置
        docs_path = os.getenv("DOCS_SOURCE_PATH", "/home/mind/workspace/harmonyos/docs/zh-cn/application-dev")
        embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5")
        chunk_size = int(os.getenv("CHUNK_SIZE", "1200"))
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))

        lib = LibraryConfig(
            id="harmonyos",
            name="HarmonyOS应用开发文档",
            type=LibraryType.HARMONY_OS,
            source_path=docs_path,
            enabled=True,
            status=LibraryStatus.READY,
            collection_name=new_collection,
            embedding_config=EmbeddingConfig(
                model_name=embedding_model,
                device=os.getenv("EMBEDDING_DEVICE", "cpu"),
            ),
            chunking_config=ChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            ),
        )
        config.libraries["harmonyos"] = lib

    # 更新文档数量
    stats = vector_store.get_stats(new_collection)
    lib.document_count = stats.get("document_count", 0)
    lib.chunk_count = stats.get("document_count", 0)  # chunk_count ≈ document_count in ChromaDB

    # 5. 保存配置
    manager._config_loader.save(config)
    logger.info(f"资料库配置已更新: {lib.document_count} 个文档")

    # 6. 设置为默认资料库
    config.global_config.default_library = "harmonyos"
    manager._config_loader.save(config)

    logger.info("迁移完成!")
    logger.info(f"  - 旧集合: {old_collection} (保留)")
    logger.info(f"  - 新集合: {new_collection}")
    logger.info(f"  - 配置文件: ./data/libraries/config.yaml")
    logger.info(f"  - 文档数量: {lib.document_count}")

    return True


if __name__ == "__main__":
    success = migrate_harmonyos_data()
    sys.exit(0 if success else 1)

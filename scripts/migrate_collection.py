#!/usr/bin/env python3
"""
将数据从 harmony_docs 集合迁移到 lib_harmonyos 集合

Usage:
    python scripts/migrate_collection.py
"""
import sys
import time
from pathlib import Path
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vector_store import VectorStore
from core.library_manager import get_library_manager
from core.embedder import Embedder


def migrate_data(
    source_collection: str = "harmony_docs",
    target_library_id: str = "harmonyos",
    batch_size: int = 1000,
    verbose: bool = True
) -> dict:
    """
    迁移数据从源集合到目标资料库集合

    Args:
        source_collection: 源集合名称
        target_library_id: 目标资料库 ID
        batch_size: 批量处理大小
        verbose: 是否显示详细日志

    Returns:
        迁移统计信息
    """
    stats = {
        'source_count': 0,
        'migrated_count': 0,
        'skipped_count': 0,
        'error_count': 0,
        'start_time': time.time()
    }

    # 初始化组件
    vector_store = VectorStore()
    library_manager = get_library_manager()
    target_lib = library_manager.get_library(target_library_id)

    if not target_lib:
        logger.error(f"目标资料库不存在: {target_library_id}")
        return stats

    target_collection = target_lib.collection_name
    logger.info(f"开始迁移: {source_collection} -> {target_collection}")

    # 获取源集合
    source_coll = vector_store.get_collection(source_collection)

    # 统计源文档数量
    try:
        stats['source_count'] = source_coll.count()
    except Exception as e:
        logger.warning(f"无法统计源集合数量: {e}")
        # 使用 list 分页获取
        pass

    # 获取目标集合（用于写入）
    target_coll = vector_store.get_collection(target_collection)

    # 使用分页获取所有文档
    offset = 0
    batch_num = 0

    logger.info(f"源集合约有 {stats['source_count']} 个文档")

    while True:
        # 获取一批文档
        try:
            # ChromaDB v0.6.0+ 使用 limit 和 offset
            result = source_coll.get(
                limit=batch_size,
                offset=offset
            )
        except TypeError:
            # 旧版本 API
            result = source_coll.get(
                n_results=batch_size,
                offset=offset
            )

        if not result or not result['ids']:
            break

        batch_num += 1
        docs_in_batch = len(result['ids'])

        logger.info(f"处理批次 {batch_num}: {docs_in_batch} 个文档 (offset: {offset})")

        # 批量添加到目标集合
        try:
            # 准备文档数据
            documents = result['documents']
            metadatas = result['metadatas']
            ids = result['ids']

            # 生成 embeddings（如果需要）
            # 注意：ChromaDB 可以自动生成 embeddings，但为了速度最好重用
            # 这里我们让 ChromaDB 自动处理

            # 添加到目标集合
            target_coll.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

            stats['migrated_count'] += docs_in_batch

            if verbose and batch_num % 5 == 0:
                logger.info(f"已迁移 {stats['migrated_count']} / {stats['source_count']} 文档")

        except Exception as e:
            logger.error(f"批次 {batch_num} 迁移失败: {e}")
            stats['error_count'] += docs_in_batch

        # 检查是否完成
        if docs_in_batch < batch_size:
            break

        offset += batch_size

    stats['end_time'] = time.time()
    stats['duration'] = stats['end_time'] - stats['start_time']

    # 验证迁移结果
    try:
        final_count = target_coll.count()
        stats['final_count'] = final_count
        logger.info(f"迁移完成！目标集合现在有 {final_count} 个文档")
    except Exception as e:
        logger.warning(f"无法统计最终数量: {e}")

    return stats


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("数据迁移工具: harmony_docs -> lib_harmonyos")
    logger.info("=" * 50)

    stats = migrate_data(
        source_collection="harmony_docs",
        target_library_id="harmonyos",
        batch_size=1000
    )

    logger.info("=" * 50)
    logger.info("迁移统计:")
    logger.info(f"  源文档数量: {stats['source_count']}")
    logger.info(f"  已迁移: {stats['migrated_count']}")
    logger.info(f"  跳过: {stats['skipped_count']}")
    logger.info(f"  错误: {stats['error_count']}")
    if 'duration' in stats:
        logger.info(f"  耗时: {stats['duration']:.1f} 秒")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()

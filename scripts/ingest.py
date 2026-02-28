"""
文档摄取脚本：将 HarmonyOS 文档加载到向量数据库
"""
import os
import sys
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.document_parser import HarmonyDocParser
from core.embedder import Embedder
from core.vector_store import VectorStore


def ingest_documents(
    docs_root: str,
    max_files: int = None,
    batch_size: int = 100,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
):
    """
    摄取文档到向量数据库

    Args:
        docs_root: 文档根目录
        max_files: 最大处理文件数（用于测试）
        batch_size: 批处理大小
        chunk_size: 分块大小（字符数）
        chunk_overlap: 分块重叠大小
    """
    load_dotenv()

    logger.info("Starting document ingestion...")

    # 初始化组件
    parser = HarmonyDocParser(docs_root)
    embedder = Embedder()
    vector_store = VectorStore()

    # 扫描文档
    files = parser.scan_directory(max_files=max_files)
    logger.info(f"Found {len(files)} documents to process")

    # 解析文档
    documents = []
    for file_path in tqdm(files, desc="Parsing documents"):
        doc = parser.parse_file(file_path)
        if doc and doc['content']:
            documents.append(doc)

    logger.info(f"Parsed {len(documents)} valid documents")

    # 文档分块
    logger.info(f"Chunking documents (chunk_size={chunk_size}, overlap={chunk_overlap})...")
    chunks = []
    chunk_metadatas = []

    for doc in documents:
        doc_chunks = _chunk_text(doc['content'], chunk_size, chunk_overlap)
        for i, chunk in enumerate(doc_chunks):
            chunks.append({
                'content': chunk,
                'source': doc['source'],
                'metadata': doc['metadata'],
            })

    logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")

    # 批量嵌入和存储
    logger.info("Generating embeddings and storing in vector database...")

    doc_count = 0
    for i in tqdm(range(0, len(chunks), batch_size), desc="Embedding batches"):
        batch = chunks[i:i + batch_size]

        # 准备文本和元数据
        texts = [c['content'] for c in batch]
        metadatas = [
            {
                'source': c['source'],
                'category': c['metadata'].category or '',
                'kit': c['metadata'].kit or '',
                'subsystem': c['metadata'].subsystem or '',
            }
            for c in batch
        ]

        # 生成嵌入
        embeddings = embedder.embed_texts(texts)

        # 生成全局唯一 ID
        ids = [f"chunk_{doc_count + j}" for j in range(len(batch))]
        doc_count += len(batch)

        # 存储到向量数据库
        vector_store.add_texts(texts, embeddings, metadatas, ids)

    logger.info(f"Successfully ingested {len(chunks)} chunks from {len(documents)} documents")


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """将文本分成重叠的块"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():  # 只保留非空块
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Ingest HarmonyOS documents into vector database')
    parser.add_argument('--docs-root', type=str,
                       default=os.getenv('DOCS_SOURCE_PATH'),
                       help='Path to documents directory')
    parser.add_argument('--max-files', type=int, default=None,
                       help='Maximum number of files to process (for testing)')
    parser.add_argument('--batch-size', type=int, default=500,
                       help='Batch size for embedding')
    parser.add_argument('--chunk-size', type=int, default=1200,
                       help='Chunk size in characters')
    parser.add_argument('--chunk-overlap', type=int, default=200,
                       help='Chunk overlap in characters')

    args = parser.parse_args()

    if not args.docs_root:
        logger.error("Please provide --docs-root or set DOCS_SOURCE_PATH in .env")
        sys.exit(1)

    ingest_documents(
        docs_root=args.docs_root,
        max_files=args.max_files,
        batch_size=args.batch_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )


if __name__ == '__main__':
    main()

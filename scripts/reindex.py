"""
Reindex script: Properly reindex a library with new embedding model
"""
import os
import sys
import time
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_config
from core.embedder import Embedder
from core.parsers import get_parser
from core.vector_store import VectorStore


def reindex_library(library_id: str, batch_size: int = 500):
    """
    Reindex a library with fresh embeddings

    Args:
        library_id: Library identifier
        batch_size: Batch size for embedding
    """
    load_dotenv()

    logger.info(f"Starting reindex for library: {library_id}")

    # Load config
    config = get_config()
    library = config.libraries.get(library_id)

    if not library:
        logger.error(f"Library not found: {library_id}")
        return False

    logger.info(f"Library: {library.name}")
    logger.info(f"Source: {library.source_path}")
    logger.info(f"Model: {library.embedding_config.model_name}")

    # Initialize VectorStore
    vector_store = VectorStore(
        persist_dir=config.global_config.vector_store_path
    )

    # Delete old collection
    collection_name = library.collection_name
    logger.info(f"Deleting old collection: {collection_name}")
    vector_store.delete_collection(collection_name)

    # Initialize embedder with library config
    embedder = Embedder(
        model_name=library.embedding_config.model_name,
        device=library.embedding_config.device
    )

    logger.info(f"Embedder initialized: {embedder.model_name}")
    logger.info(f"Dimension: {embedder.dimension}")
    logger.info(f"Device: {embedder.device}")

    # Get parser for library type with chunking config
    parser = get_parser(
        library.type,
        docs_root=library.source_path,
        chunk_size=library.chunking_config.chunk_size,
        chunk_overlap=library.chunking_config.chunk_overlap
    )

    # Scan documents
    source_path = Path(library.source_path)
    if not source_path.exists():
        logger.error(f"Source path does not exist: {source_path}")
        return False

    logger.info("Scanning documents...")
    files = list(source_path.rglob("*.md"))
    logger.info(f"Found {len(files)} markdown files")

    # Parse and chunk documents
    logger.info("Parsing and chunking documents...")
    all_chunks = []
    all_metadatas = []

    for file_path in tqdm(files, desc="Processing files", unit="file"):
        try:
            # Parse the file to get document(s)
            docs = parser.parse(file_path)

            for doc in docs:
                # Chunk the document content
                chunks = parser.chunk_text(doc.content, doc.metadata, doc.source)

                for chunk in chunks:
                    all_chunks.append(chunk.text)
                    # Merge chunk metadata
                    chunk_metadata = chunk.metadata.copy()
                    chunk_metadata['source'] = doc.source
                    all_metadatas.append(chunk_metadata)

        except Exception as e:
            logger.warning(f"Error processing {file_path}: {e}")
            continue

    logger.info(f"Created {len(all_chunks)} chunks from {len(files)} files")

    if len(all_chunks) == 0:
        logger.error("No chunks created!")
        return False

    # Generate embeddings and store
    logger.info(f"Generating embeddings...")
    logger.info(f"Batch size: {batch_size}")

    # Create timestamp for unique IDs
    timestamp = int(time.time() * 1000)
    logger.info(f"Using timestamp prefix: {timestamp}")

    total_processed = 0
    start_time = time.time()

    for i in tqdm(range(0, len(all_chunks), batch_size), desc="Embedding batches"):
        batch_chunks = all_chunks[i:i + batch_size]
        batch_metadatas = all_metadatas[i:i + batch_size]

        # Generate embeddings
        embeddings = embedder.embed_texts(batch_chunks)

        # Generate unique IDs with timestamp
        ids = [f"{timestamp}_{j}" for j in range(total_processed, total_processed + len(batch_chunks))]
        total_processed += len(batch_chunks)

        # Add to vector store
        vector_store.add_texts(
            texts=batch_chunks,
            embeddings=embeddings,
            metadatas=batch_metadatas,
            ids=ids,
            collection_name=collection_name
        )

    elapsed = time.time() - start_time
    logger.info(f"Successfully indexed {total_processed} chunks in {elapsed:.1f}s ({total_processed/elapsed:.1f} chunks/s)")

    # Verify collection
    collection = vector_store.get_collection(collection_name)
    final_count = collection.count()
    logger.info(f"Final collection count: {final_count}")

    logger.info("Reindex complete!")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Reindex a library with new embeddings')
    parser.add_argument('--library-id', type=str, default='harmonyos_full',
                       help='Library ID to reindex')
    parser.add_argument('--batch-size', type=int, default=500,
                       help='Batch size for embedding')

    args = parser.parse_args()

    success = reindex_library(
        library_id=args.library_id,
        batch_size=args.batch_size
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

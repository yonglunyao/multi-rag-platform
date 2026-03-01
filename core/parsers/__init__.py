"""
文档解析器包

提供可扩展的文档解析器框架
"""
from typing import Optional

from core.models import LibraryType
from core.parsers.base import BaseParser, Document
from core.parsers.harmonyos import HarmonyOSParser
from core.parsers.generic import GenericMarkdownParser


def get_parser(
    library_type: LibraryType,
    docs_root: Optional[str] = None,
    chunk_size: int = 1200,
    chunk_overlap: int = 200
) -> BaseParser:
    """
    获取对应类型的解析器

    Args:
        library_type: 资料库类型
        docs_root: 文档根目录路径
        chunk_size: 分块大小
        chunk_overlap: 分块重叠大小

    Returns:
        BaseParser: 解析器实例
    """
    parsers = {
        LibraryType.HARMONY_OS: HarmonyOSParser(
            docs_root=docs_root,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        ),
        LibraryType.GENERIC_MARKDOWN: GenericMarkdownParser(
            docs_root=docs_root,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        ),
        LibraryType.GENERIC_PDF: GenericMarkdownParser(
            docs_root=docs_root,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        ),
    }

    parser = parsers.get(library_type)
    if parser is None:
        # 默认使用通用解析器
        return GenericMarkdownParser(
            docs_root=docs_root,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    return parser


__all__ = [
    'BaseParser',
    'Document',
    'HarmonyOSParser',
    'GenericMarkdownParser',
    'get_parser',
]

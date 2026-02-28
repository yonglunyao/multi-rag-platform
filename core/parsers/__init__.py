"""
文档解析器包

提供可扩展的文档解析器框架
"""
from typing import Optional

from core.models import LibraryType
from core.parsers.base import BaseParser, Document
from core.parsers.harmonyos import HarmonyOSParser
from core.parsers.generic import GenericMarkdownParser


def get_parser(library_type: LibraryType) -> BaseParser:
    """
    获取对应类型的解析器

    Args:
        library_type: 资料库类型

    Returns:
        BaseParser: 解析器实例
    """
    parsers = {
        LibraryType.HARMONY_OS: HarmonyOSParser(),
        LibraryType.GENERIC_MARKDOWN: GenericMarkdownParser(),
        LibraryType.GENERIC_PDF: GenericMarkdownParser(),  # 暂时复用
    }

    parser = parsers.get(library_type)
    if parser is None:
        # 默认使用通用解析器
        return GenericMarkdownParser()

    return parser


__all__ = [
    'BaseParser',
    'Document',
    'HarmonyOSParser',
    'GenericMarkdownParser',
    'get_parser',
]

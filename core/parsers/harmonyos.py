"""
HarmonyOS 文档解析器

支持解析 HarmonyOS Markdown 文档的元数据（Kit, Subsystem, Owner 等）
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from loguru import logger

from core.parsers.base import BaseParser, Document, Chunk


@dataclass
class HarmonyOSMetadata:
    """HarmonyOS 文档元数据"""
    kit: Optional[str] = None
    subsystem: Optional[str] = None
    owner: Optional[str] = None
    designer: Optional[str] = None
    tester: Optional[str] = None
    adviser: Optional[str] = None
    category: Optional[str] = None  # 从路径推断

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'kit': self.kit,
            'subsystem': self.subsystem,
            'owner': self.owner,
            'designer': self.designer,
            'tester': self.tester,
            'adviser': self.adviser,
            'category': self.category,
        }


class HarmonyOSParser(BaseParser):
    """
    HarmonyOS 文档解析器

    解析 HarmonyOS 文档的专用元数据格式：
    <!--Kit: Xxx-->
    <!--Subsystem: Xxx-->
    <!--Owner: Xxx-->
    """

    # 元数据正则模式
    METADATA_PATTERNS = {
        'kit': r'<!--Kit:\s*(.+?)\s*-->',
        'subsystem': r'<!--Subsystem:\s*(.+?)\s*-->',
        'owner': r'<!--Owner:\s*(.+?)\s*-->',
        'designer': r'<!--Designer:\s*(.+?)\s*-->',
        'tester': r'<!--Tester:\s*(.+?)\s*-->',
        'adviser': r'<!--Adviser:\s*(.+?)\s*-->',
    }

    # 分类映射
    CATEGORY_MAP = {
        'quick-start': '快速入门',
        'application-models': '应用框架',
        'security': '安全服务',
        'network': '网络服务',
        'media': '媒体服务',
        'graphics': '图形服务',
        'ai': 'AI服务',
        'device': '设备服务',
        'basic-services': '基础服务',
    }

    def __init__(self, docs_root: Optional[str] = None, chunk_size: int = 1200, chunk_overlap: int = 200):
        """
        初始化 HarmonyOS 解析器

        Args:
            docs_root: 文档根目录路径
            chunk_size: 分块大小
            chunk_overlap: 分块重叠大小
        """
        super().__init__(chunk_size, chunk_overlap)
        self.docs_root = Path(docs_root) if docs_root else None

    def parse(self, file_path: Path) -> List[Document]:
        """
        解析 HarmonyOS 文档文件

        Args:
            file_path: 文档文件路径

        Returns:
            List[Document]: 解析后的文档列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return []

        # 解析元数据
        metadata = self.extract_metadata(file_path, content)

        # 清理内容
        cleaned_content = self._clean_content(content)

        # 创建文档对象
        source = str(file_path)
        if self.docs_root:
            try:
                source = str(file_path.relative_to(self.docs_root))
            except ValueError:
                pass

        doc = Document(
            content=cleaned_content,
            metadata=metadata,
            source=source,
        )

        return [doc]

    def extract_metadata(self, file_path: Path, content: str) -> Dict[str, Any]:
        """
        从文档内容中提取元数据

        Args:
            file_path: 文件路径
            content: 文档内容

        Returns:
            Dict[str, Any]: 元数据字典
        """
        metadata = HarmonyOSMetadata()

        # 从文档注释中提取元数据
        for key, pattern in self.METADATA_PATTERNS.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                setattr(metadata, key, value)

        # 从路径推断分类
        metadata.category = self._infer_category(file_path)

        return metadata.to_dict()

    def _infer_category(self, path: Path) -> str:
        """
        从文件路径推断分类

        Args:
            path: 文件路径

        Returns:
            str: 分类名称
        """
        if self.docs_root:
            try:
                relative = path.relative_to(self.docs_root)
                parts = relative.parts

                for part in parts:
                    if part in self.CATEGORY_MAP:
                        return self.CATEGORY_MAP[part]
            except ValueError:
                pass

        return '其他'

    def _clean_content(self, content: str) -> str:
        """
        清理文档内容

        Args:
            content: 原始内容

        Returns:
            str: 清理后的内容
        """
        # 移除元数据注释
        for pattern in self.METADATA_PATTERNS.values():
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)

        # 移除 HTML 注释
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

        # 规范化空白
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = content.strip()

        return content

    def scan_directory(
        self,
        docs_root: str,
        max_files: Optional[int] = None,
    ) -> List[Path]:
        """
        扫描文档目录，返回所有 Markdown 文件

        Args:
            docs_root: 文档根目录路径
            max_files: 最大文件数限制（用于测试）

        Returns:
            List[Path]: Markdown 文件路径列表
        """
        self.docs_root = Path(docs_root)
        md_files = list(self.docs_root.rglob('*.md'))

        # 排除隐藏文件和特殊文件
        md_files = [
            f for f in md_files
            if not f.name.startswith('.')
            and 'node_modules' not in f.parts
        ]

        logger.info(f"Found {len(md_files)} markdown files in {self.docs_root}")

        if max_files:
            md_files = md_files[:max_files]
            logger.info(f"Limited to {max_files} files for testing")

        return md_files

    def supported_extensions(self) -> List[str]:
        """
        获取支持的文件扩展名

        Returns:
            List[str]: 支持的扩展名列表
        """
        return ['.md']

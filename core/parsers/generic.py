"""
通用 Markdown 文档解析器

支持解析通用的 Markdown 文档
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger

from core.parsers.base import BaseParser, Document


class GenericMarkdownParser(BaseParser):
    """
    通用 Markdown 文档解析器

    支持解析标准 Markdown 文档，提取标题作为元数据
    """

    def __init__(self, docs_root: Optional[str] = None, chunk_size: int = 1200, chunk_overlap: int = 200):
        """
        初始化通用 Markdown 解析器

        Args:
            docs_root: 文档根目录路径
            chunk_size: 分块大小
            chunk_overlap: 分块重叠大小
        """
        super().__init__(chunk_size, chunk_overlap)
        self.docs_root = Path(docs_root) if docs_root else None

    def parse(self, file_path: Path) -> List[Document]:
        """
        解析 Markdown 文档文件

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
        metadata = {
            'filename': file_path.name,
            'extension': file_path.suffix,
        }

        # 提取第一个标题
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata['title'] = title_match.group(1).strip()
        else:
            metadata['title'] = file_path.stem

        # 提取所有标题（转换为逗号分隔的字符串）
        headers = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
        if headers:
            metadata['headers'] = ','.join([h[1].strip() for h in headers[:10]])  # 只保留前10个

        # 提取代码块语言（转换为逗号分隔的字符串）
        code_blocks = re.findall(r'```(\w+)', content)
        if code_blocks:
            metadata['code_languages'] = ','.join(list(set(code_blocks)))

        # 从路径推断分类
        if self.docs_root:
            try:
                relative = file_path.relative_to(self.docs_root)
                metadata['category'] = str(relative.parent)
            except ValueError:
                pass

        return metadata

    def _clean_content(self, content: str) -> str:
        """
        清理文档内容

        Args:
            content: 原始内容

        Returns:
            str: 清理后的内容
        """
        # 移除 YAML frontmatter（如果有）
        content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

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
        扫描文档目录，返回所有支持的文件

        Args:
            docs_root: 文档根目录路径
            max_files: 最大文件数限制（用于测试）

        Returns:
            List[Path]: 文件路径列表
        """
        self.docs_root = Path(docs_root)

        # 支持多种文件类型
        patterns = ['*.md', '*.markdown', '*.txt']
        files = []

        for pattern in patterns:
            files.extend(self.docs_root.rglob(pattern))

        # 去重并排序
        files = sorted(set(files))

        # 排除隐藏文件和特殊文件
        files = [
            f for f in files
            if not f.name.startswith('.')
            and 'node_modules' not in f.parts
        ]

        logger.info(f"Found {len(files)} supported files in {self.docs_root}")

        if max_files:
            files = files[:max_files]
            logger.info(f"Limited to {max_files} files for testing")

        return files

    def supported_extensions(self) -> List[str]:
        """
        获取支持的文件扩展名

        Returns:
            List[str]: 支持的扩展名列表
        """
        return ['.md', '.markdown', '.txt']

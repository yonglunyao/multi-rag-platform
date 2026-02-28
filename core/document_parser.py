"""
HarmonyOS 文档解析器
支持解析 Markdown 文档的元数据（Kit, Subsystem, Owner 等）
"""
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class DocumentMetadata:
    """文档元数据"""
    kit: Optional[str] = None
    subsystem: Optional[str] = None
    owner: Optional[str] = None
    designer: Optional[str] = None
    tester: Optional[str] = None
    adviser: Optional[str] = None
    category: Optional[str] = None  # 从路径推断


class HarmonyDocParser:
    """HarmonyOS 文档解析器"""

    # 元数据正则模式
    METADATA_PATTERNS = {
        'kit': r'<!--Kit:\s*(.+?)\s*-->',
        'subsystem': r'<!--Subsystem:\s*(.+?)\s*-->',
        'owner': r'<!--Owner:\s*(.+?)\s*-->',
        'designer': r'<!--Designer:\s*(.+?)\s*-->',
        'tester': r'<!--Tester:\s*(.+?)\s*-->',
        'adviser': r'<!--Adviser:\s*(.+?)\s*-->',
    }

    def __init__(self, docs_root: str):
        """
        初始化解析器

        Args:
            docs_root: 文档根目录路径
        """
        self.docs_root = Path(docs_root)

    def parse_file(self, file_path: str) -> Dict:
        """
        解析单个文档文件

        Args:
            file_path: 文档文件路径

        Returns:
            包含内容和元数据的字典
        """
        path = Path(file_path)

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return None

        # 解析元数据
        metadata = self._extract_metadata(content)

        # 从路径推断分类
        metadata.category = self._infer_category(path)

        # 清理内容
        cleaned_content = self._clean_content(content)

        return {
            'content': cleaned_content,
            'metadata': metadata,
            'source': str(path.relative_to(self.docs_root)),
            'file_path': str(path),
        }

    def _extract_metadata(self, content: str) -> DocumentMetadata:
        """从文档内容中提取元数据"""
        metadata = DocumentMetadata()

        for key, pattern in self.METADATA_PATTERNS.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                setattr(metadata, key, value)

        return metadata

    def _infer_category(self, path: Path) -> str:
        """从文件路径推断分类"""
        relative = path.relative_to(self.docs_root)
        parts = relative.parts

        # 根据目录结构推断分类
        category_map = {
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

        for part in parts:
            if part in category_map:
                return category_map[part]

        return '其他'

    def _clean_content(self, content: str) -> str:
        """清理文档内容"""
        # 移除元数据注释
        for pattern in self.METADATA_PATTERNS.values():
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)

        # 移除 HTML 注释
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)

        # 规范化空白
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = content.strip()

        return content

    def scan_directory(self, max_files: Optional[int] = None) -> List[Path]:
        """
        扫描文档目录，返回所有 Markdown 文件

        Args:
            max_files: 最大文件数限制（用于测试）

        Returns:
            Markdown 文件路径列表
        """
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


def test_parser():
    """测试解析器"""
    docs_root = "/home/mind/workspace/harmonyos/docs/zh-cn/application-dev"
    parser = HarmonyDocParser(docs_root)

    # 扫描文件（限制10个用于测试）
    files = parser.scan_directory(max_files=10)
    print(f"Found {len(files)} files")

    # 解析第一个文件
    if files:
        result = parser.parse_file(files[0])
        print(f"\nFile: {result['source']}")
        print(f"Category: {result['metadata'].category}")
        print(f"Kit: {result['metadata'].kit}")
        print(f"Content preview: {result['content'][:200]}...")


if __name__ == '__main__':
    test_parser()

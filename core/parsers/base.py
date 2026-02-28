"""
文档解析器基类

定义所有解析器的通用接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class Document:
    """文档数据类"""
    content: str                           # 文档内容
    metadata: Dict[str, Any]               # 元数据
    source: str                            # 来源文件路径
    chunk_id: Optional[str] = None         # 块 ID

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'content': self.content,
            'metadata': self.metadata,
            'source': self.source,
            'chunk_id': self.chunk_id,
        }


@dataclass
class Chunk:
    """文档块"""
    text: str                              # 块文本
    metadata: Dict[str, Any]               # 元数据
    source: str                            # 来源文件

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'text': self.text,
            'metadata': self.metadata,
            'source': self.source,
        }


class BaseParser(ABC):
    """
    文档解析器抽象基类

    所有解析器必须继承此类并实现 parse 方法
    """

    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 200):
        """
        初始化解析器

        Args:
            chunk_size: 分块大小
            chunk_overlap: 分块重叠大小
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @abstractmethod
    def parse(self, file_path: Path) -> List[Document]:
        """
        解析文档文件

        Args:
            file_path: 文档文件路径

        Returns:
            List[Document]: 解析后的文档列表
        """
        pass

    @abstractmethod
    def extract_metadata(self, file_path: Path, content: str) -> Dict[str, Any]:
        """
        从文档中提取元数据

        Args:
            file_path: 文档文件路径
            content: 文档内容

        Returns:
            Dict[str, Any]: 元数据字典
        """
        pass

    def chunk_text(self, text: str, metadata: Dict[str, Any], source: str) -> List[Chunk]:
        """
        将文本分块

        Args:
            text: 原始文本
            metadata: 元数据
            source: 来源文件路径

        Returns:
            List[Chunk]: 文档块列表
        """
        chunks = []
        start = 0
        chunk_id = 0

        while start < len(text):
            end = start + self.chunk_size

            # 如果不是最后一块，尝试在分隔符处截断
            if end < len(text):
                # 在重叠部分寻找合适的分隔符
                separator_pos = -1
                for sep in ['\n\n', '\n', '。', '！', '？', '；', ' ']:
                    pos = text.rfind(sep, start + self.chunk_size - 200, end)
                    if pos > start + 100:  # 确保至少有 100 字符
                        separator_pos = pos + len(sep)
                        break

                if separator_pos > 0:
                    end = separator_pos

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunk = Chunk(
                    text=chunk_text,
                    metadata={
                        **metadata,
                        'chunk_id': f"{source}_chunk_{chunk_id}",
                        'start': start,
                        'end': end,
                    },
                    source=source,
                )
                chunks.append(chunk)
                chunk_id += 1

            # 移动到下一块（考虑重叠）
            start = end - self.chunk_overlap if end < len(text) else end

        return chunks

    def is_supported_file(self, file_path: Path) -> bool:
        """
        检查文件是否支持

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否支持
        """
        return file_path.suffix.lower() in self.supported_extensions()

    def supported_extensions(self) -> List[str]:
        """
        获取支持的文件扩展名

        Returns:
            List[str]: 支持的扩展名列表
        """
        return ['.md', '.markdown', '.txt']

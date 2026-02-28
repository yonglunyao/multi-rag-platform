"""
权限名倒排索引：快速查找权限对应的文档
"""
import re
from pathlib import Path
from typing import Dict, List, Set
from loguru import logger
import json


class PermissionIndex:
    """权限名倒排索引"""

    def __init__(self, docs_root: str = None):
        """
        初始化权限索引

        Args:
            docs_root: 文档根目录
        """
        self.docs_root = docs_root
        self.index: Dict[str, List[str]] = {}  # permission -> [sources]
        self._loaded = False

    def build(self, docs_root: str = None):
        """
        构建权限索引

        Args:
            docs_root: 文档根目录
        """
        if docs_root:
            self.docs_root = docs_root

        if not self.docs_root:
            logger.warning("No docs_root provided for permission index")
            return

        logger.info(f"Building permission index from {self.docs_root}")

        # 扫描所有 Markdown 文件
        doc_path = Path(self.docs_root)
        md_files = list(doc_path.rglob("*.md"))

        for file_path in md_files:
            self._index_file(file_path)

        self._loaded = True
        logger.info(f"Permission index built: {len(self.index)} permissions found")

    def _index_file(self, file_path: Path):
        """索引单个文件"""
        try:
            content = file_path.read_text(encoding='utf-8')
            relative_path = str(file_path.relative_to(self.docs_root))

            # 查找所有 ohos.permission.*
            permissions = re.findall(r'ohos\.permission\.[a-zA-Z0-9_]+', content)

            for perm in permissions:
                if perm not in self.index:
                    self.index[perm] = []
                self.index[perm].append(relative_path)

        except Exception as e:
            logger.warning(f"Failed to index {file_path}: {e}")

    def get_sources(self, permission: str) -> List[str]:
        """
        获取权限对应的文档来源

        Args:
            permission: 权限名

        Returns:
            文档来源列表
        """
        return self.index.get(permission, [])

    def search_permissions(self, query: str) -> List[str]:
        """
        在权限名中搜索匹配的权限

        Args:
            query: 查询关键词

        Returns:
            匹配的权限名列表
        """
        results = []

        query_lower = query.lower()

        for perm in self.index.keys():
            # 精确匹配
            if query_lower in perm.lower():
                results.append(perm)

        return results

    def get_all_permissions(self) -> List[str]:
        """获取所有权限名"""
        return list(self.index.keys())

    def save(self, file_path: str):
        """保存索引到文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
        logger.info(f"Permission index saved to {file_path}")

    def load(self, file_path: str):
        """从文件加载索引"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.index = json.load(f)
            self._loaded = True
            logger.info(f"Permission index loaded from {file_path}: {len(self.index)} permissions")
        except Exception as e:
            logger.error(f"Failed to load permission index: {e}")

    def is_loaded(self) -> bool:
        """检查索引是否已加载"""
        return self._loaded


# 单例
_permission_index_instance = None


def get_permission_index() -> PermissionIndex:
    """获取权限索引单例"""
    global _permission_index_instance
    if _permission_index_instance is None:
        _permission_index_instance = PermissionIndex()
    return _permission_index_instance

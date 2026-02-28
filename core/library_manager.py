"""
资料库管理器

负责管理多个资料库的生命周期、状态和索引
"""
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger
from datetime import datetime

from core.models import LibraryConfig, LibraryStatus, LibraryType, AppConfig
from core.config import get_config_loader


class IndexLock:
    """全局索引锁 - 确保串行索引"""

    def __init__(self):
        self._lock = threading.Lock()
        self._current_indexing: Optional[str] = None
        self._lock_owner: Optional[threading.Thread] = None

    def acquire(self, library_id: str, timeout: float = 0.1) -> bool:
        """
        尝试获取索引锁

        Args:
            library_id: 资料库 ID
            timeout: 超时时间（秒）

        Returns:
            bool: 是否成功获取锁
        """
        if self._lock.acquire(timeout=timeout):
            self._current_indexing = library_id
            self._lock_owner = threading.current_thread()
            logger.info(f"[IndexLock] 索引锁已获取: {library_id}")
            return True
        else:
            logger.warning(f"[IndexLock] 索引锁获取失败: {library_id} (正在索引: {self._current_indexing})")
            return False

    def release(self, library_id: str) -> None:
        """
        释放索引锁

        Args:
            library_id: 资料库 ID
        """
        if self._current_indexing == library_id:
            self._current_indexing = None
            self._lock_owner = None
            self._lock.release()
            logger.info(f"[IndexLock] 索引锁已释放: {library_id}")
        else:
            logger.warning(f"[IndexLock] 尝试释放非持有的锁: {library_id}")

    def is_locked(self) -> bool:
        """检查是否被锁定"""
        return self._lock.locked()

    def get_current_indexing(self) -> Optional[str]:
        """获取当前正在索引的资料库"""
        return self._current_indexing


# 全局索引锁实例
_index_lock = IndexLock()


def get_index_lock() -> IndexLock:
    """获取全局索引锁实例"""
    return _index_lock


class LibraryManager:
    """
    资料库管理器

    负责管理多个资料库的生命周期、状态和索引操作
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化资料库管理器

        Args:
            config_path: 配置文件路径
        """
        self._config_loader = get_config_loader(config_path)
        self._config: Optional[AppConfig] = None
        self._active_library: Optional[str] = None
        self._loaded_collections: Dict[str, any] = {}  # 已加载的集合
        logger.info("LibraryManager 初始化")

    def load_config(self) -> AppConfig:
        """
        加载配置文件

        Returns:
            AppConfig: 应用配置
        """
        self._config = self._config_loader.load()
        # 设置默认活动资料库
        if self._active_library is None:
            self._active_library = self._config.global_config.default_library
        return self._config

    def reload_config(self) -> AppConfig:
        """
        重新加载配置文件

        Returns:
            AppConfig: 应用配置
        """
        self._config = self._config_loader.reload()
        return self._config

    def get_config(self) -> AppConfig:
        """
        获取当前配置

        Returns:
            AppConfig: 应用配置
        """
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def list_libraries(self, include_disabled: bool = False) -> List[LibraryConfig]:
        """
        列出所有资料库

        Args:
            include_disabled: 是否包含禁用的资料库

        Returns:
            List[LibraryConfig]: 资料库列表
        """
        config = self.get_config()
        if include_disabled:
            return list(config.libraries.values())
        else:
            return config.get_enabled_libraries()

    def get_library(self, library_id: str) -> Optional[LibraryConfig]:
        """
        获取指定资料库配置

        Args:
            library_id: 资料库 ID

        Returns:
            LibraryConfig: 资料库配置，不存在返回 None
        """
        config = self.get_config()
        return config.get_library(library_id)

    def get_active_library(self) -> Optional[LibraryConfig]:
        """
        获取活动资料库

        Returns:
            LibraryConfig: 活动资料库配置
        """
        active_id = self.get_active_library_id()
        if active_id:
            return self.get_library(active_id)
        return None

    def get_active_library_id(self) -> Optional[str]:
        """
        获取活动资料库 ID

        Returns:
            str: 活动 ID
        """
        if self._active_library:
            return self._active_library
        config = self.get_config()
        return config.global_config.default_library

    def set_active_library(self, library_id: str) -> bool:
        """
        设置活动资料库

        Args:
            library_id: 资料库 ID

        Returns:
            bool: 是否成功设置
        """
        lib = self.get_library(library_id)
        if lib is None:
            logger.error(f"资料库不存在: {library_id}")
            return False

        if not lib.enabled:
            logger.warning(f"资料库未启用: {library_id}")
            return False

        self._active_library = library_id
        logger.info(f"活动资料库已设置: {library_id}")
        return True

    def create_library(self, config: LibraryConfig) -> bool:
        """
        创建新资料库

        Args:
            config: 资料库配置

        Returns:
            bool: 是否成功创建
        """
        # 检查 ID 是否已存在
        if self.get_library(config.id):
            logger.error(f"资料库 ID 已存在: {config.id}")
            return False

        # 检查源路径是否存在
        if not Path(config.source_path).exists():
            logger.error(f"文档源路径不存在: {config.source_path}")
            return False

        # 添加到配置
        app_config = self.get_config()
        app_config.libraries[config.id] = config

        # 保存配置
        self._config_loader.save(app_config)

        logger.info(f"资料库已创建: {config.id}")
        return True

    def delete_library(self, library_id: str) -> bool:
        """
        删除资料库

        Args:
            library_id: 资料库 ID

        Returns:
            bool: 是否成功删除
        """
        lib = self.get_library(library_id)
        if lib is None:
            logger.error(f"资料库不存在: {library_id}")
            return False

        # 删除向量集合
        try:
            from core.vector_store import get_vector_store
            vector_store = get_vector_store()
            vector_store.delete_collection(library_id)
            logger.info(f"已删除向量集合: {lib.collection_name}")
        except Exception as e:
            logger.warning(f"删除向量集合失败: {e}")

        # 从配置中移除
        app_config = self.get_config()
        if library_id in app_config.libraries:
            del app_config.libraries[library_id]

        # 保存配置
        self._config_loader.save(app_config)

        # 如果是活动资料库，清除
        if self._active_library == library_id:
            self._active_library = None

        logger.info(f"资料库已删除: {library_id}")
        return True

    def update_library_status(self, library_id: str, status: LibraryStatus) -> bool:
        """
        更新资料库状态

        Args:
            library_id: 资料库 ID
            status: 新状态

        Returns:
            bool: 是否成功更新
        """
        lib = self.get_library(library_id)
        if lib is None:
            return False

        lib.status = status
        if status == LibraryStatus.READY:
            lib.last_indexed = datetime.now()

        # 保存配置
        app_config = self.get_config()
        self._config_loader.save(app_config)

        return True

    def acquire_index_lock(self, library_id: str, timeout: float = 0.1) -> bool:
        """
        获取索引锁

        Args:
            library_id: 资料库 ID
            timeout: 超时时间

        Returns:
            bool: 是否成功获取
        """
        return _index_lock.acquire(library_id, timeout)

    def release_index_lock(self, library_id: str) -> None:
        """
        释放索引锁

        Args:
            library_id: 资料库 ID
        """
        _index_lock.release(library_id)

    def is_indexing(self) -> bool:
        """检查是否有索引正在进行"""
        return _index_lock.is_locked()

    def get_current_indexing(self) -> Optional[str]:
        """获取当前正在索引的资料库"""
        return _index_lock.get_current_indexing()

    def get_library_stats(self, library_id: str) -> Optional[Dict]:
        """
        获取资料库统计信息

        Args:
            library_id: 资料库 ID

        Returns:
            Dict: 统计信息
        """
        lib = self.get_library(library_id)
        if lib is None:
            return None

        return {
            "library_id": lib.id,
            "name": lib.name,
            "type": lib.type.value,
            "enabled": lib.enabled,
            "status": lib.status.value,
            "document_count": lib.document_count,
            "chunk_count": lib.chunk_count,
            "collection_name": lib.collection_name,
            "last_indexed": lib.last_indexed.isoformat() if lib.last_indexed else None,
            "created_at": lib.created_at.isoformat() if lib.created_at else None,
            "source_path": lib.source_path,
        }


# 全局资料库管理器实例
_library_manager: Optional[LibraryManager] = None
_manager_lock = threading.Lock()


def get_library_manager(config_path: Optional[str] = None) -> LibraryManager:
    """
    获取全局资料库管理器实例

    Args:
        config_path: 配置文件路径

    Returns:
        LibraryManager: 资料库管理器实例
    """
    global _library_manager
    if _library_manager is None:
        with _manager_lock:
            if _library_manager is None:
                _library_manager = LibraryManager(config_path)
    return _library_manager

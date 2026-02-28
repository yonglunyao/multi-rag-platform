"""
配置加载器

负责从 YAML 文件加载资料库配置
"""
import os
import yaml
from pathlib import Path
from typing import Optional
from loguru import logger

from core.models import AppConfig, LibraryConfig, GlobalConfig


class ConfigLoader:
    """配置加载器"""

    DEFAULT_CONFIG_PATH = "./data/libraries/config.yaml"
    DEFAULT_CONFIG_EXAMPLE = "./data/libraries/config.yaml.example"

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置加载器

        Args:
            config_path: 配置文件路径，默认为 DEFAULT_CONFIG_PATH
        """
        self.config_path = Path(config_path or self.DEFAULT_CONFIG_PATH)
        self._config: Optional[AppConfig] = None

    def load(self) -> AppConfig:
        """
        加载配置文件

        Returns:
            AppConfig: 应用配置
        """
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}")
            logger.info("将创建默认配置")
            return self._create_default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"配置文件为空: {self.config_path}")
                return self._create_default_config()

            self._config = AppConfig.from_dict(data)
            logger.info(f"成功加载配置: {self.config_path}")
            logger.info(f"资料库数量: {len(self._config.libraries)}")
            logger.info(f"启用的资料库: {len(self._config.get_enabled_libraries())}")

            return self._config

        except yaml.YAMLError as e:
            logger.error(f"YAML 解析错误: {e}")
            return self._create_default_config()
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return self._create_default_config()

    def save(self, config: AppConfig) -> None:
        """
        保存配置到文件

        Args:
            config: 应用配置
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config.to_dict(), f, allow_unicode=True, default_flow_style=False)

        logger.info(f"配置已保存: {self.config_path}")
        self._config = config

    def reload(self) -> AppConfig:
        """重新加载配置"""
        self._config = None
        return self.load()

    def get_config(self) -> AppConfig:
        """
        获取当前配置（如果未加载则自动加载）

        Returns:
            AppConfig: 应用配置
        """
        if self._config is None:
            self._config = self.load()
        return self._config

    def _create_default_config(self) -> AppConfig:
        """
        创建默认配置

        Returns:
            AppConfig: 默认应用配置
        """
        # 尝试从环境变量或现有配置迁移
        default_config = AppConfig()

        # 检查是否有现有的 HarmonyOS 配置需要迁移
        harmonyos_lib = self._migrate_harmonyos_config()
        if harmonyos_lib:
            default_config.libraries["harmonyos"] = harmonyos_lib

        return default_config

    def _migrate_harmonyos_config(self) -> Optional[LibraryConfig]:
        """
        迁移现有 HarmonyOS 配置

        Returns:
            LibraryConfig: HarmonyOS 资料库配置，如果没有现有配置则返回 None
        """
        # 从环境变量读取现有配置
        docs_path = os.getenv("DOCS_SOURCE_PATH")
        collection_name = os.getenv("COLLECTION_NAME", "harmony_docs")
        embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5")
        chunk_size = int(os.getenv("CHUNK_SIZE", "1200"))
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))

        if docs_path and Path(docs_path).exists():
            logger.info(f"检测到现有 HarmonyOS 配置，正在迁移: {docs_path}")

            from core.models import EmbeddingConfig, ChunkingConfig, LibraryType, LibraryStatus

            return LibraryConfig(
                id="harmonyos",
                name="HarmonyOS应用开发文档",
                type=LibraryType.HARMONY_OS,
                source_path=docs_path,
                enabled=True,
                status=LibraryStatus.READY,
                collection_name="lib_harmonyos",  # 新集合名
                embedding_config=EmbeddingConfig(
                    model_name=embedding_model,
                    device=os.getenv("EMBEDDING_DEVICE", "cpu"),
                ),
                chunking_config=ChunkingConfig(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                ),
            )

        return None

    def create_example_config(self) -> None:
        """创建示例配置文件"""
        example_path = Path(self.DEFAULT_CONFIG_EXAMPLE)
        example_path.parent.mkdir(parents=True, exist_ok=True)

        example_config = AppConfig()
        example_config.libraries["harmonyos"] = LibraryConfig(
            id="harmonyos",
            name="HarmonyOS应用开发文档",
            type="harmony_os",
            source_path="/home/mind/workspace/harmonyos/docs/zh-cn/application-dev",
            enabled=True,
        )

        with open(example_path, 'w', encoding='utf-8') as f:
            yaml.dump(example_config.to_dict(), f, allow_unicode=True, default_flow_style=False)

        logger.info(f"示例配置已创建: {example_path}")


# 全局配置加载器实例
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(config_path: Optional[str] = None) -> ConfigLoader:
    """
    获取全局配置加载器实例

    Args:
        config_path: 配置文件路径

    Returns:
        ConfigLoader: 配置加载器实例
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_path)
    return _config_loader


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    加载配置（便捷函数）

    Args:
        config_path: 配置文件路径

    Returns:
        AppConfig: 应用配置
    """
    return get_config_loader(config_path).load()


def get_config() -> AppConfig:
    """
    获取当前配置（便捷函数）

    Returns:
        AppConfig: 应用配置
    """
    return get_config_loader().get_config()

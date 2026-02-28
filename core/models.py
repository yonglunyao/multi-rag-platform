"""
资料库数据模型

定义多资料库RAG平台的核心数据结构
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import json


class LibraryType(Enum):
    """资料库类型支持的枚举"""
    HARMONY_OS = "harmony_os"           # HarmonyOS 文档
    GENERIC_MARKDOWN = "generic_md"     # 通用 Markdown 文档
    GENERIC_PDF = "generic_pdf"         # PDF 文档
    CUSTOM = "custom"                   # 自定义解析器


class LibraryStatus(Enum):
    """资料库生命周期状态"""
    INITIALIZING = "initializing"
    READY = "ready"
    INDEXING = "indexing"
    ERROR = "error"
    ARCHIVED = "archived"


@dataclass
class EmbeddingConfig:
    """嵌入模型配置"""
    model_name: str = "BAAI/bge-base-zh-v1.5"
    device: str = "cpu"
    dimension: int = 768
    batch_size: int = 32

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "device": self.device,
            "dimension": self.dimension,
            "batch_size": self.batch_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmbeddingConfig":
        return cls(
            model_name=data.get("model_name", "BAAI/bge-base-zh-v1.5"),
            device=data.get("device", "cpu"),
            dimension=data.get("dimension", 768),
            batch_size=data.get("batch_size", 32),
        )


@dataclass
class ChunkingConfig:
    """文档分块配置"""
    chunk_size: int = 1200
    chunk_overlap: int = 200
    separators: List[str] = field(default_factory=lambda: ["\n\n", "\n", "。", "！", "？", "；", " ", ""])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "separators": self.separators,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkingConfig":
        return cls(
            chunk_size=data.get("chunk_size", 1200),
            chunk_overlap=data.get("chunk_overlap", 200),
            separators=data.get("separators", ["\n\n", "\n", "。", "！", "？", "；", " ", ""]),
        )


@dataclass
class LibraryConfig:
    """资料库配置"""
    id: str                              # 唯一标识符
    name: str                            # 显示名称
    type: LibraryType                    # 资料库类型
    source_path: str                     # 文档源目录
    enabled: bool = True                 # 是否启用
    status: LibraryStatus = LibraryStatus.READY
    collection_name: Optional[str] = None  # ChromaDB 集合名称
    embedding_config: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking_config: ChunkingConfig = field(default_factory=ChunkingConfig)
    data_path: Optional[str] = None      # 数据存储路径
    metadata: Dict[str, Any] = field(default_factory=dict)  # 自定义元数据
    created_at: datetime = field(default_factory=datetime.now)
    last_indexed: Optional[datetime] = None
    document_count: int = 0
    chunk_count: int = 0

    def __post_init__(self):
        """初始化后处理"""
        if self.collection_name is None:
            self.collection_name = f"lib_{self.id}"
        if self.data_path is None:
            self.data_path = f"./data/libraries/{self.id}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value if isinstance(self.type, LibraryType) else self.type,
            "source_path": self.source_path,
            "enabled": self.enabled,
            "status": self.status.value if isinstance(self.status, LibraryStatus) else self.status,
            "collection_name": self.collection_name,
            "embedding_config": self.embedding_config.to_dict(),
            "chunking_config": self.chunking_config.to_dict(),
            "data_path": self.data_path,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_indexed": self.last_indexed.isoformat() if self.last_indexed else None,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LibraryConfig":
        """从字典创建"""
        # 处理 type 枚举
        lib_type = data.get("type", "generic_md")
        if isinstance(lib_type, str):
            try:
                lib_type = LibraryType(lib_type)
            except ValueError:
                lib_type = LibraryType.GENERIC_MARKDOWN

        # 处理 status 枚举
        status = data.get("status", "ready")
        if isinstance(status, str):
            try:
                status = LibraryStatus(status)
            except ValueError:
                status = LibraryStatus.READY

        # 处理时间
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        last_indexed = data.get("last_indexed")
        if last_indexed and isinstance(last_indexed, str):
            last_indexed = datetime.fromisoformat(last_indexed)

        return cls(
            id=data["id"],
            name=data["name"],
            type=lib_type,
            source_path=data["source_path"],
            enabled=data.get("enabled", True),
            status=status,
            collection_name=data.get("collection_name"),
            embedding_config=EmbeddingConfig.from_dict(data.get("embedding_config", {})),
            chunking_config=ChunkingConfig.from_dict(data.get("chunking_config", {})),
            data_path=data.get("data_path"),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            last_indexed=last_indexed,
            document_count=data.get("document_count", 0),
            chunk_count=data.get("chunk_count", 0),
        )

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "LibraryConfig":
        """从 JSON 字符串创建"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class GlobalConfig:
    """全局配置"""
    default_library: str = "harmonyos"
    max_concurrent_indexing: int = 1
    embedding_device: str = "cpu"
    data_root: str = "./data/libraries"
    export_dir: str = "./data/exports"
    vector_store_path: str = "./data/vectorstore"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "default_library": self.default_library,
            "max_concurrent_indexing": self.max_concurrent_indexing,
            "embedding_device": self.embedding_device,
            "data_root": self.data_root,
            "export_dir": self.export_dir,
            "vector_store_path": self.vector_store_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalConfig":
        return cls(
            default_library=data.get("default_library", "harmonyos"),
            max_concurrent_indexing=data.get("max_concurrent_indexing", 1),
            embedding_device=data.get("embedding_device", "cpu"),
            data_root=data.get("data_root", "./data/libraries"),
            export_dir=data.get("export_dir", "./data/exports"),
            vector_store_path=data.get("vector_store_path", "./data/vectorstore"),
        )


@dataclass
class AppConfig:
    """应用配置（包含所有资料库配置）"""
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    libraries: Dict[str, LibraryConfig] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "global": self.global_config.to_dict(),
            "libraries": {
                lib_id: lib_config.to_dict()
                for lib_id, lib_config in self.libraries.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        global_config = GlobalConfig.from_dict(data.get("global", {}))
        libraries = {}
        for lib_id, lib_data in data.get("libraries", {}).items():
            libraries[lib_id] = LibraryConfig.from_dict(lib_data)
        return cls(global_config=global_config, libraries=libraries)

    def get_library(self, library_id: str) -> Optional[LibraryConfig]:
        """获取指定资料库配置"""
        return self.libraries.get(library_id)

    def get_enabled_libraries(self) -> List[LibraryConfig]:
        """获取所有启用的资料库"""
        return [lib for lib in self.libraries.values() if lib.enabled]

    def get_default_library(self) -> Optional[LibraryConfig]:
        """获取默认资料库"""
        return self.libraries.get(self.global_config.default_library)

# 多资料库 RAG 平台 - 架构设计

## 系统概述

将现有的单资料库 HarmonyOS RAG 系统改造为通用的多资料库训练和部署平台。

### 设计目标
- **配置化管理**: 通过 YAML 配置文件管理资料库
- **高性能低资源**: 串行索引、按需加载、共享 Embedding
- **可扩展性**: 支持不同类型文档解析器
- **可移植性**: 数据导出支持迁移到其他 RAG 系统

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端层                                  │
│  REST API | MCP SSE (Claude Code) | CLI                        │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                         API 层                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ /libraries   │  │ /query       │  │ /export      │          │
│  │ 资料库管理    │  │ 查询接口      │  │ 数据导出      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                         服务层                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │              LibraryManager (单例)                      │     │
│  │  - 加载配置  - 管理资料库  - 索引锁  - 状态跟踪          │     │
│  └────────────────────────────────────────────────────────┘     │
│                                │                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ VectorStore │  │  Retriever  │  │  Exporter   │             │
│  │ 多集合管理   │  │ 资料库感知   │  │ 数据导出     │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                         解析器层                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ HarmonyOS    │  │ Generic MD   │  │  Custom...   │          │
│  │ Parser       │  │  Parser      │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                        ↑                                         │
│              Parser Factory                                      │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                         数据层                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ ChromaDB     │  │ Config YAML  │  │ File System  │          │
│  │ 多集合向量库  │  │ 资料库配置    │  │ 文档源/导出   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                         外部服务                                 │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ Ollama LLM   │  │ Embedding    │                            │
│  │ (共享)        │  │ Model (共享)  │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心组件

### 1. LibraryManager (资料库管理器)

**职责**:
- 从 YAML 配置加载资料库定义
- 管理资料库生命周期
- 控制索引并发 (全局锁)
- 跟踪资料库状态

**关键方法**:
```python
class LibraryManager:
    def load_from_config(config_path: str) -> None
    def get_library(library_id: str) -> LibraryConfig
    def list_enabled() -> List[LibraryConfig]
    def set_active(library_id: str) -> None
    def get_active() -> str
    def acquire_index_lock() -> bool
    def release_index_lock() -> None
```

**资源管理**:
- 只加载 `enabled=true` 的资料库
- 全局索引锁确保串行索引
- 共享 Embedder 单例

---

### 2. VectorStore (向量存储)

**改造要点**:
- 动态集合名称: `lib_{library_id}`
- 懒加载: 按需创建集合
- 共享 ChromaDB 客户端

**关键方法**:
```python
class VectorStore:
    def get_collection(library_id: str) -> Collection
    def list_collections() -> List[str]
    def delete_collection(library_id: str) -> bool
```

---

### 3. 解析器系统

**设计模式**: 工厂模式 + 插件架构

**基类**:
```python
class BaseParser(ABC):
    @abstractmethod
    def parse(file_path: Path) -> List[Document]

    @abstractmethod
    def extract_metadata(file_path: Path) -> Dict[str, Any]
```

**工厂函数**:
```python
def get_parser(library_type: LibraryType) -> BaseParser:
    parsers = {
        LibraryType.HARMONY_OS: HarmonyOSParser(),
        LibraryType.GENERIC_MARKDOWN: GenericMarkdownParser(),
    }
    return parsers.get(library_type, GenericMarkdownParser())
```

---

### 4. 数据导出

**导出格式**:
```json
{
  "version": "1.0",
  "library_id": "harmonyos",
  "exported_at": "2026-02-28T10:00:00Z",
  "config": {...},
  "documents": [
    {
      "id": "doc_001",
      "content": "...",
      "metadata": {...},
      "embedding": [0.1, 0.2, ...]
    }
  ]
}
```

---

## 配置系统

### 配置文件结构

```yaml
# data/libraries/config.yaml
libraries:
  harmonyos:
    name: "HarmonyOS应用开发文档"
    type: "harmony_os"
    enabled: true
    source_path: "/path/to/docs"
    collection_name: "lib_harmonyos"
    embedding_model: "BAAI/bge-base-zh-v1.5"
    chunk_size: 1200
    chunk_overlap: 200

global:
  default_library: "harmonyos"
  max_concurrent_indexing: 1
  embedding_device: "cpu"
```

### 配置加载流程

```
启动服务
   │
   ├─→ 读取 config.yaml
   │
   ├─→ 验证配置
   │
   ├─→ 加载 enabled=true 的资料库
   │
   └─→ 初始化 VectorStore 集合
```

---

## API 设计

### 资料库管理 API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/libraries` | GET | 列出所有资料库 |
| `/api/v1/libraries` | POST | 创建新资料库 |
| `/api/v1/libraries/{id}` | GET | 获取资料库详情 |
| `/api/v1/libraries/{id}` | DELETE | 删除资料库 |
| `/api/v1/libraries/{id}/index` | POST | 触发索引 |
| `/api/v1/libraries/{id}/stats` | GET | 获取统计信息 |
| `/api/v1/libraries/{id}/export` | POST | 导出数据 |
| `/api/v1/libraries/active` | GET | 获取活动资料库 |
| `/api/v1/libraries/active` | POST | 设置活动资料库 |

### 查询 API

**改造后**:
```python
POST /api/v1/query?library_id=harmonyos
```

**向后兼容**: 不指定 `library_id` 时使用默认资料库

---

## MCP 工具

### 新增工具

```python
@mcp.tool()
async def list_libraries() -> list:
    """列出所有资料库"""

@mcp.tool()
async def rag_query(query: str, library_id: str = None) -> dict:
    """RAG查询，支持指定资料库"""

@mcp.tool()
async def get_library_stats(library_id: str) -> dict:
    """获取资料库统计信息"""
```

---

## 数据流程

### 索引流程

```
用户触发索引
   │
   ├─→ 获取索引锁
   │
   ├─→ 读取资料库配置
   │
   ├─→ 获取对应解析器
   │
   ├─→ 扫描文档目录
   │
   ├─→ 解析文档 → 生成 chunks
   │
   ├─→ 生成 embeddings (共享 Embedder)
   │
   ├─→ 存储到 ChromaDB (lib_{id})
   │
   └─→ 释放索引锁
```

### 查询流程

```
用户查询
   │
   ├─→ 确定 library_id
   │
   ├─→ 获取对应集合
   │
   ├─→ 向量检索
   │
   ├─→ 构建 context
   │
   ├─→ LLM 生成回答
   │
   └─→ 返回结果 + 来源
```

---

## 资源优化策略

### 1. 串行索引
- 全局索引锁
- 避免 CPU/内存峰值

### 2. 按需加载
- 只加载 `enabled=true` 的资料库
- ChromaDB 集合懒加载

### 3. 共享资源
- Embedder 单例 (所有库共用)
- LLM 连接复用

### 4. 内存管理
- 不预加载所有集合
- 查询时按需加载

---

## 迁移策略

### 现有数据迁移

```
harmony_docs (旧)
      │
      ├─→ collection 重命名为 lib_harmonyos
      │
      ├─→ 生成 config.yaml
      │
      └─→ permission_index 迁移到 data/libraries/harmonyos/
```

### 向后兼容

- 不指定 `library_id` 时使用默认资料库
- 保留原 API 端点
- 环境变量 `DEFAULT_LIBRARY` 设置默认值

---

## 安全考虑

### 输入验证
- 资料库 ID 格式验证
- 路径遍历防护
- 配置文件验证

### 访问控制
- API 认证 (现有 API_KEY)
- 资料库级别访问控制 (未来)

---

## 监控和日志

### 关键指标
- 资料库数量
- 每个资料库的文档数
- 索引状态
- 查询延迟
- 内存/CPU 占用

### 日志
- 资料库操作日志
- 索引进度日志
- 错误日志

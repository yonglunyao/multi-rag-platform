# 多资料库 RAG 平台 - API 接口文档

## 基础信息

**Base URL**: `http://localhost:8000`

**认证**: API Key (可选，通过环境变量配置)

```http
Authorization: Bearer your-api-key
```

---

## 资料库管理 API

### 1. 列出所有资料库

```http
GET /api/v1/libraries
```

**响应**:
```json
{
  "libraries": [
    {
      "id": "harmonyos",
      "name": "HarmonyOS应用开发文档",
      "type": "harmony_os",
      "enabled": true,
      "status": "ready",
      "document_count": 5196,
      "chunk_count": 64142,
      "created_at": "2026-02-01T00:00:00Z"
    },
    {
      "id": "another_lib",
      "name": "其他技术文档",
      "type": "generic_markdown",
      "enabled": false,
      "status": "ready",
      "document_count": 100,
      "chunk_count": 1200,
      "created_at": "2026-02-15T00:00:00Z"
    }
  ]
}
```

---

### 2. 获取资料库详情

```http
GET /api/v1/libraries/{library_id}
```

**路径参数**:
- `library_id`: 资料库 ID

**响应**:
```json
{
  "id": "harmonyos",
  "name": "HarmonyOS应用开发文档",
  "type": "harmony_os",
  "enabled": true,
  "status": "ready",
  "source_path": "/home/mind/workspace/harmonyos/docs/zh-cn/application-dev",
  "collection_name": "lib_harmonyos",
  "embedding_model": "BAAI/bge-base-zh-v1.5",
  "chunk_size": 1200,
  "chunk_overlap": 200,
  "document_count": 5196,
  "chunk_count": 64142,
  "last_indexed": "2026-02-28T10:00:00Z",
  "created_at": "2026-02-01T00:00:00Z"
}
```

---

### 3. 创建资料库

```http
POST /api/v1/libraries
```

**请求体**:
```json
{
  "id": "my_docs",
  "name": "我的文档库",
  "type": "generic_markdown",
  "enabled": true,
  "source_path": "/path/to/docs",
  "embedding_model": "BAAI/bge-base-zh-v1.5",
  "chunk_size": 1200,
  "chunk_overlap": 200
}
```

**响应**:
```json
{
  "id": "my_docs",
  "status": "initializing",
  "message": "资料库创建成功，请调用索引接口开始索引"
}
```

---

### 4. 删除资料库

```http
DELETE /api/v1/libraries/{library_id}
```

**响应**:
```json
{
  "message": "资料库 my_docs 已删除"
}
```

---

### 5. 触发索引

```http
POST /api/v1/libraries/{library_id}/index
```

**请求体** (可选):
```json
{
  "force": false
}
```

**响应**:
```json
{
  "library_id": "harmonyos",
  "status": "indexing",
  "message": "索引任务已启动",
  "task_id": "index_20260228_100000"
}
```

---

### 6. 获取资料库统计

```http
GET /api/v1/libraries/{library_id}/stats
```

**响应**:
```json
{
  "library_id": "harmonyos",
  "document_count": 5196,
  "chunk_count": 64142,
  "total_tokens": 15000000,
  "indexing_time": "2026-02-28T10:00:00Z",
  "indexing_duration": 1800,
  "vector_dimension": 768
}
```

---

### 7. 导出数据

```http
POST /api/v1/libraries/{library_id}/export
```

**请求体**:
```json
{
  "format": "json",
  "include_embeddings": true
}
```

**响应**:
```json
{
  "library_id": "harmonyos",
  "format": "json",
  "file_path": "/app/data/exports/harmonyos_20260228_100000.json",
  "size_bytes": 52428800,
  "download_url": "/api/v1/exports/harmonyos_20260228_100000.json"
}
```

---

## 活动资料库 API

### 8. 获取活动资料库

```http
GET /api/v1/libraries/active
```

**响应**:
```json
{
  "active_library": "harmonyos"
}
```

---

### 9. 设置活动资料库

```http
POST /api/v1/libraries/active
```

**请求体**:
```json
{
  "library_id": "harmonyos"
}
```

**响应**:
```json
{
  "message": "活动资料库已设置为 harmonyos"
}
```

---

## 查询 API

### 10. RAG 查询

```http
POST /api/v1/query?library_id=harmonyos
```

**查询参数**:
- `library_id` (可选): 资料库 ID，不指定则使用默认资料库

**请求体**:
```json
{
  "query": "如何创建后台任务？",
  "context_length": 5,
  "temperature": 0.7,
  "max_tokens": 2048,
  "filter": {
    "kit": "AbilityKit"
  }
}
```

**响应**:
```json
{
  "answer": "在 HarmonyOS 中创建后台任务需要使用 KEEP_BACKGROUND_RUNNING 权限...",
  "sources": [
    {
      "file": "application-models/background/task.md",
      "relevance": 0.95,
      "category": "后台任务",
      "kit": "BackgroundKit"
    }
  ],
  "library_id": "harmonyos",
  "retrieval_metadata": {
    "method": "smart_retrieve",
    "permissions_found": ["ohos.permission.KEEP_BACKGROUND_RUNNING"],
    "expansion_count": 1
  }
}
```

---

### 11. 批量查询

```http
POST /api/v1/batch_query?library_id=harmonyos
```

**请求体**:
```json
{
  "queries": [
    "如何创建页面？",
    "后台任务需要什么权限？",
    "如何使用网络请求？"
  ]
}
```

**响应**:
```json
{
  "results": {
    "如何创建页面？": [
      {
        "document": "页面是 UI 构建的基本单元...",
        "source": "ui/page.md",
        "score": 0.92
      }
    ],
    "后台任务需要什么权限？": [
      {
        "document": "长时任务需要 KEEP_BACKGROUND_RUNNING 权限...",
        "source": "background/task.md",
        "score": 0.95
      }
    ]
  }
}
```

---

## MCP 工具

### list_libraries

列出所有资料库及其状态。

**参数**: 无

**返回**:
```json
[
  {
    "id": "harmonyos",
    "name": "HarmonyOS应用开发文档",
    "enabled": true,
    "status": "ready",
    "document_count": 5196
  }
]
```

---

### rag_query

执行 RAG 查询，可指定资料库。

**参数**:
- `query` (str): 查询问题
- `library_id` (str, 可选): 资料库 ID

**返回**:
```json
{
  "answer": "基于文档的回答...",
  "sources": [...],
  "library_id": "harmonyos"
}
```

---

### get_library_stats

获取资料库统计信息。

**参数**:
- `library_id` (str): 资料库 ID

**返回**:
```json
{
  "library_id": "harmonyos",
  "document_count": 5196,
  "chunk_count": 64142,
  "status": "ready"
}
```

---

## 错误响应

### 错误格式

```json
{
  "error": {
    "code": "LIBRARY_NOT_FOUND",
    "message": "资料库不存在: unknown_lib",
    "details": {}
  }
}
```

### 错误码

| 错误码 | HTTP 状态 | 描述 |
|--------|----------|------|
| `LIBRARY_NOT_FOUND` | 404 | 资料库不存在 |
| `LIBRARY_ALREADY_EXISTS` | 409 | 资料库已存在 |
| `INVALID_LIBRARY_ID` | 400 | 资料库 ID 格式无效 |
| `INDEX_IN_PROGRESS` | 409 | 索引正在进行中 |
| `CONFIG_INVALID` | 400 | 配置无效 |
| `SOURCE_PATH_NOT_FOUND` | 404 | 文档源路径不存在 |

---

## 速率限制

根据环境变量配置，默认:
- 每分钟 60 次请求
- 超出限制返回 429 状态码

---

## 健康检查

```http
GET /api/v1/health
```

**响应**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "libraries": {
    "total": 2,
    "enabled": 1,
    "indexing": 0
  },
  "services": {
    "vector_store": "ok",
    "llm": "ok",
    "embedding": "ok"
  }
}
```

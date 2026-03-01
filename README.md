# Multi-Library RAG 平台

通用的多资料库 RAG (检索增强生成) 训练和部署平台，支持管理多个独立的文档资料库，提供 REST API 和 MCP 接口给 AI Agent 调用。

## 特性

- 📚 **多资料库管理** - 支持创建、管理多个独立的文档资料库
- 🔍 **智能检索** - 混合检索（向量 + BM25）+ 查询扩展 + 重排序 + 答案验证
- 🤖 **本地 LLM** - Ollama + Qwen2.5，数据隐私安全
- 🐳 **Docker 部署** - 一键部署，自动健康检查
- 🌍 **中文优化** - 针对中文文档优化，支持拼音搜索
- 📤 **数据导出** - 支持导出训练数据用于迁移
- 🔌 **MCP 接口** - 支持 Claude Code/Deskop 通过 MCP 调用

## 检索增强功能

### 查询扩展 (Query Expansion)
自动将用户查询扩展为多维度查询，提高召回率：
- **同义词扩展**: "权限" → "permission", "许可", "授权"
- **中英互译**: "创建" → "create", "start", "init"
- **领域术语**: "mdm" → "企业设备管理", "MDM Kit"
- **拼音搜索**: 支持 "quanxian" → "权限"
- **拼写纠错**: "screentimeguard" → "ScreenTimeGuard"

### 元数据增强
文档解析时自动提取丰富的元数据：
- API 模块 (@ohos.xxx)
- 权限名 (ohos.permission.xxx)
- 接口名（带频率统计）
- 文档类型（api/guide/glossary）
- Kit 名称推断
- 标签生成

### 重排序器 (Reranker)
支持多种重排序策略提高检索精度：
- **BM25**: 基于 BM25 算法的精确重排序（推荐，已验证）
- **ScoreBoost**: 基于关键词匹配的快速重排序
- **NoOp**: 禁用重排序

| 策略 | 精度 | 延迟 | 状态 |
|------|------|------|------|
| **bm25** | ⭐⭐⭐⭐ | ~10ms | ✅ 推荐 |
| score_boost | ⭐⭐⭐ | ~1ms | ✅ 可用 |
| none | ⭐⭐ | ~0ms | ✅ 可用 |

> **注意**: CrossEncoder 由于依赖冲突暂时不可用。BM25 已提供高精度检索效果。

## 快速开始

### 1. 安装依赖

```bash
# 安装 Docker
sudo apt install docker.io docker-compose

# 安装 Ollama (宿主机运行)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
```

### 2. 配置环境

```bash
# 复制环境变量配置
cp .env.example .env

# 复制资料库配置
cp data/libraries/config.yaml.example data/libraries/config.yaml

# 根据需要编辑配置
nano .env
nano data/libraries/config.yaml
```

### 3. 启动服务

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 4. 数据迁移（如果有旧数据）

```bash
# 运行迁移脚本
docker-compose exec rag-api python scripts/migrate_harmonyos.py
```

## API 接口

### 资料库管理

```bash
# 列出所有资料库
curl http://localhost:8000/api/v1/libraries

# 创建新资料库
curl -X POST http://localhost:8000/api/v1/libraries \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my_docs",
    "name": "我的文档",
    "type": "generic_md",
    "source_path": "/path/to/docs",
    "enabled": true
  }'

# 索引资料库
curl -X POST http://localhost:8000/api/v1/libraries/my_docs/index

# 查询资料库
curl -X POST "http://localhost:8000/api/v1/query?library_id=my_docs" \
  -H "Content-Type: application/json" \
  -d '{"query": "如何使用这个功能？"}'
```

### 健康检查

```bash
curl http://localhost:8000/api/v1/health
```

## MCP 配置

### Claude Code/Desktop 配置

在 Claude Desktop 的配置文件中添加：

```json
{
  "mcpServers": {
    "harmonyos-docs-rag": {
      "type": "sse",
      "url": "http://<SERVER_IP>:8002/sse"
    }
  }
}
```

配置文件位置：
- Windows: `C:\Users\<username>\AppData\Roaming\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**使用方式：**
```
@rag_query 剪贴板 API 用法
@rag_query 如何申请长时任务权限
@list_libraries
```

## 配置文件

### 资料库配置 (data/libraries/config.yaml)

```yaml
libraries:
  harmonyos:
    id: harmonyos
    name: "HarmonyOS应用开发文档"
    type: harmony_os
    enabled: true
    source_path: "/path/to/docs"
    embedding_config:
      model_name: "BAAI/bge-base-zh-v1.5"
      device: "cpu"
    chunking_config:
      chunk_size: 1200
      chunk_overlap: 200

global:
  default_library: "harmonyos"
  max_concurrent_indexing: 1
  embedding_device: "cpu"
  use_reranker: true         # 是否启用重排序器
  reranker_type: score_boost # 重排序器类型: score_boost, bm25, none
```

### 环境变量配置 (.env)

```bash
# 检索配置
TOP_K=5                      # 返回结果数量
CHUNK_SIZE=500               # 文档分块大小
CHUNK_OVERLAP=50             # 分块重叠大小

# 重排序器配置
USE_RERANKER=true            # 是否启用重排序器
RERANKER_TYPE=score_boost    # 重排序器类型: score_boost, bm25, none
```

## 项目结构

```
multi-rag-platform/
├── api/                    # FastAPI 服务
│   ├── routes/            # API 路由
│   │   ├── libraries.py   # 资料库管理
│   │   ├── query.py       # 查询接口
│   │   └── ...
│   └── schemas/           # Pydantic 模型
├── bin/                    # 可执行脚本
│   ├── deploy-docker.sh
│   ├── quick_test.sh
│   └── start-mcp-remote.sh
├── core/                   # 核心逻辑
│   ├── models.py          # 数据模型
│   ├── config.py          # 配置加载器
│   ├── library_manager.py # 资料库管理器
│   ├── parsers/           # 文档解析器
│   │   ├── base.py        # 基类
│   │   ├── harmonyos.py   # HarmonyOS 解析器
│   │   └── generic.py     # 通用解析器
│   ├── vector_store.py    # 向量存储
│   ├── retriever.py       # 检索器
│   ├── query_expander.py  # 查询扩展器
│   ├── reranker.py        # 重排序器
│   └── exporter.py        # 数据导出
├── data/                   # 数据目录
│   ├── libraries/         # 资料库配置和数据
│   ├── vectorstore/       # ChromaDB 向量库
│   └── exports/           # 导出数据
├── scripts/                # 工具脚本
│   └── migrate_harmonyos.py  # 数据迁移
├── mcp_server_sse.py       # MCP SSE 服务器
├── docker-compose.yml      # Docker 编排
└── requirements.txt        # Python 依赖
```

## 测试

```bash
# 快速测试
./bin/quick_test.sh

# 运行单元测试
pytest tests/

# 性能测试
python scripts/stress_test.py
```

## 文档

- [API 文档](docs/API.md)
- [架构设计](docs/ARCHITECTURE.md)
- [迭代计划](docs/ITERATION_PLAN.md)
- [待办事项](docs/TODO.md)

## License

MIT

# Multi-Library RAG 平台

通用的多资料库 RAG (检索增强生成) 训练和部署平台，支持管理多个独立的文档资料库，提供 REST API 和 MCP 接口给 AI Agent 调用。

## 特性

- 📚 **多资料库管理** - 支持创建、管理多个独立的文档资料库
- 🔍 **智能检索** - 混合检索（向量 + BM25）+ 查询扩展 + 答案验证
- 🤖 **本地 LLM** - Ollama + Qwen2.5，数据隐私安全
- 🐳 **Docker 部署** - 一键部署，自动健康检查
- 🌍 **中文优化** - 针对中文文档优化
- 📤 **数据导出** - 支持导出训练数据用于迁移
- 🔌 **MCP 接口** - 支持 Claude Code/Deskop 通过 MCP 调用

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
    "rag-server": {
      "type": "sse",
      "url": "http://<LINUX_IP>:8001/sse"
    }
  }
}
```

配置文件位置：
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

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

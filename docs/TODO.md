# 多资料库 RAG 平台 - 待办任务列表

## 总览

将当前单资料库 HarmonyOS RAG 系统改造为通用的多资料库训练和部署平台。

**当前进度**: `[████████░░] 80% 设计完成, 0% 实现`

---

## Phase 1: 配置系统 (Foundation)

### 1.1 核心数据模型
- [ ] `core/models.py` - LibraryConfig, LibraryType, LibraryStatus 等数据类
- [ ] `core/models.py` - EmbeddingConfig, ChunkingConfig 配置类
- [ ] `core/models.py` - Pydantic schema 用于 API 验证

### 1.2 配置加载器
- [ ] `core/config.py` - YAML 配置文件加载器
- [ ] `core/config.py` - 配置验证和默认值处理
- [ ] `core/config.py` - 配置热更新支持 (可选)

### 1.3 配置文件模板
- [ ] `data/libraries/config.yaml.example` - 配置模板
- [ ] 自动迁移现有 HarmonyOS 配置到新格式

---

## Phase 2: 资料库管理器 (Core)

### 2.1 LibraryManager 核心
- [ ] `core/library_manager.py` - LibraryManager 类实现
- [ ] `core/library_manager.py` - 从配置加载资料库列表
- [ ] `core/library_manager.py` - 获取启用/禁用的资料库
- [ ] `core/library_manager.py` - 设置默认资料库

### 2.2 资源管理
- [ ] 全局索引锁 (串行索引)
- [ ] 按需加载机制 (只加载 enabled=true 的库)
- [ ] 共享 Embedder 单例

### 2.3 状态管理
- [ ] 资料库状态追踪 (ready, indexing, error)
- [ ] 索引进度跟踪

---

## Phase 3: 多集合支持

### 3.1 VectorStore 改造
- [ ] `core/vector_store.py` - 动态集合名称
- [ ] `core/vector_store.py` - 懒加载集合 (按需创建)
- [ ] `core/vector_store.py` - list_collections() 方法

### 3.2 Retriever 改造
- [ ] `core/retriever.py` - 接受 library_id 参数
- [ ] `core/retriever.py` - 资料库感知检索

### 3.3 数据迁移
- [ ] 迁移脚本: `harmony_docs` → `lib_harmonyos`
- [ ] 迁移现有 permission_index

---

## Phase 4: 解析器抽象

### 4.1 基础框架
- [ ] `core/parsers/__init__.py` - 包初始化
- [ ] `core/parsers/base.py` - BaseParser 抽象类
- [ ] `core/parsers/__init__.py` - get_parser() 工厂函数

### 4.2 具体解析器
- [ ] `core/parsers/harmonyos.py` - 从 document_parser.py 提取
- [ ] `core/parsers/generic.py` - 通用 Markdown 解析器

---

## Phase 5: API 开发

### 5.1 资料库管理 API
- [ ] `api/routes/libraries.py` - GET /api/v1/libraries (列出所有)
- [ ] `api/routes/libraries.py` - GET /api/v1/libraries/{id} (详情)
- [ ] `api/routes/libraries.py` - POST /api/v1/libraries (创建)
- [ ] `api/routes/libraries.py` - DELETE /api/v1/libraries/{id} (删除)
- [ ] `api/routes/libraries.py` - POST /api/v1/libraries/{id}/index (索引)
- [ ] `api/routes/libraries.py` - GET /api/v1/libraries/{id}/stats (统计)

### 5.2 活动资料库 API
- [ ] `api/routes/libraries.py` - GET /api/v1/libraries/active (获取)
- [ ] `api/routes/libraries.py` - POST /api/v1/libraries/active (设置)

### 5.3 查询 API 改造
- [ ] `api/routes/query.py` - 添加 library_id 可选参数
- [ ] `api/schemas.py` - 更新 QueryRequest schema

### 5.4 API 初始化
- [ ] `api/main.py` - 启动时初始化 LibraryManager
- [ ] `api/main.py` - 加载配置文件

---

## Phase 6: MCP 接口扩展

### 6.1 新增 MCP 工具
- [ ] `mcp_server_sse.py` - list_libraries() 工具
- [ ] `mcp_server_sse.py` - rag_query(query, library_id) 工具
- [ ] `mcp_server_sse.py` - get_library_stats(library_id) 工具

---

## Phase 7: 数据导出

### 7.1 导出功能
- [ ] `core/exporter.py` - DataExporter 类
- [ ] `core/exporter.py` - JSON 格式导出
- [ ] `api/routes/libraries.py` - POST /api/v1/libraries/{id}/export

### 7.2 导出格式
- [ ] 包含文档内容
- [ ] 包含向量嵌入
- [ ] 包含元数据
- [ ] 包含配置信息

---

## Phase 8: Docker 部署

### 8.1 配置更新
- [ ] `docker-compose.yml` - 更新卷结构
- [ ] `docker-compose.yml` - 添加环境变量
- [ ] `.env.example` - 更新环境变量模板

### 8.2 Dockerfile 更新
- [ ] `docker/Dockerfile` - 安装 PyYAML

---

## Phase 9: 测试

### 9.1 单元测试
- [ ] 测试配置加载
- [ ] 测试资料库管理器
- [ ] 测试多集合检索

### 9.2 集成测试
- [ ] 测试 API 端点
- [ ] 测试 MCP 工具
- [ ] 测试数据导出/导入

### 9.3 性能测试
- [ ] 内存占用测试
- [ ] CPU 占用测试
- [ ] 并发查询测试

---

## Phase 10: 文档

### 10.1 用户文档
- [ ] 更新 README.md
- [ ] 更新 CLAUDE.md
- [ ] 创建配置示例文档

### 10.2 API 文档
- [ ] API.md - 接口文档

### 10.3 架构文档
- [ ] ARCHITECTURE.md - 架构设计

---

## 优先级说明

**P0 (必须)**: Phase 1-3 - 核心功能
**P1 (重要)**: Phase 4-6 - API 和 MCP
**P2 (可选)**: Phase 7-10 - 导出、测试、文档

---

## 快速开始

```bash
# 1. 创建目录结构
mkdir -p data/libraries
mkdir -p core/parsers

# 2. 开始开发 (按 Phase 顺序)
# TODO: 具体命令
```

# 多资料库 RAG 平台 - 迭代计划

## 迭代概览

| 迭代 | 目标 | 预计工作量 | 依赖 |
|------|------|-----------|------|
| **Iteration 1** | 配置系统和数据模型 | 2-3小时 | 无 |
| **Iteration 2** | 资料库管理器和多集合支持 | 3-4小时 | Iteration 1 |
| **Iteration 3** | 解析器抽象和 API 开发 | 4-5小时 | Iteration 2 |
| **Iteration 4** | MCP 扩展和数据导出 | 2-3小时 | Iteration 3 |
| **Iteration 5** | Docker 部署和测试 | 2-3小时 | Iteration 4 |

**总预计工作量**: 13-18 小时

---

## Iteration 1: 配置系统和数据模型

### 目标
建立配置系统基础设施，定义数据模型

### 任务清单
1. 创建 `core/models.py` - 数据类定义
2. 创建 `core/config.py` - YAML 配置加载器
3. 创建 `data/libraries/config.yaml.example` - 配置模板
4. 编写配置迁移脚本

### 交付物
- [ ] `core/models.py`
- [ ] `core/config.py`
- [ ] `data/libraries/config.yaml.example`
- [ ] 单元测试: `tests/test_config.py`

### 验收标准
- 可以加载 YAML 配置文件
- 配置验证正确
- 自动迁移现有 HarmonyOS 配置

---

## Iteration 2: 资料库管理器和多集合支持

### 目标
实现资料库管理核心功能，支持多集合向量存储

### 任务清单
1. 创建 `core/library_manager.py`
2. 修改 `core/vector_store.py` - 动态集合
3. 修改 `core/retriever.py` - 资料库感知
4. 实现全局索引锁
5. 数据迁移脚本

### 交付物
- [ ] `core/library_manager.py`
- [ ] 修改后的 `core/vector_store.py`
- [ ] 修改后的 `core/retriever.py`
- [ ] 迁移脚本 `scripts/migrate_harmonyos.py`
- [ ] 单元测试: `tests/test_library_manager.py`

### 验收标准
- 可以创建、列出、删除资料库
- 可以设置默认资料库
- 向量存储支持多集合
- 现有 HarmonyOS 数据成功迁移

---

## Iteration 3: 解析器抽象和 API 开发

### 目标
实现解析器插件系统，开发资料库管理 API

### 任务清单
1. 创建解析器基础框架
2. 提取 HarmonyOS 解析器
3. 创建通用 Markdown 解析器
4. 开发资料库管理 API
5. 修改查询 API

### 交付物
- [ ] `core/parsers/__init__.py`
- [ ] `core/parsers/base.py`
- [ ] `core/parsers/harmonyos.py`
- [ ] `core/parsers/generic.py`
- [ ] `api/routes/libraries.py`
- [ ] 修改后的 `api/routes/query.py`
- [ ] 修改后的 `api/main.py`
- [ ] API 测试: `tests/test_api_libraries.py`

### 验收标准
- 可以通过 API 管理资料库
- 查询 API 支持 library_id 参数
- 解析器插件系统工作正常

---

## Iteration 4: MCP 扩展和数据导出

### 目标
扩展 MCP 工具，实现数据导出功能

### 任务清单
1. 扩展 MCP SSE 服务器
2. 实现数据导出器
3. 添加导出 API 端点

### 交付物
- [ ] 修改后的 `mcp_server_sse.py`
- [ ] `core/exporter.py`
- [ ] API 测试: `tests/test_export.py`

### 验收标准
- MCP 可以列出资料库
- MCP 可以查询指定资料库
- 可以导出 JSON 格式数据
- 导出数据包含所有必要信息

---

## Iteration 5: Docker 部署和测试

### 目标
更新 Docker 配置，完成集成测试和文档

### 任务清单
1. 更新 docker-compose.yml
2. 更新 Dockerfile
3. 集成测试
4. 性能测试
5. 更新文档

### 交付物
- [ ] 修改后的 `docker-compose.yml`
- [ ] 修改后的 `docker/Dockerfile`
- [ ] 集成测试: `tests/test_integration.py`
- [ ] 更新后的 `README.md`
- [ ] 更新后的 `CLAUDE.md`
- [ ] `ARCHITECTURE.md`
- [ ] `API.md`

### 验收标准
- Docker 部署成功
- 所有测试通过
- 内存占用合理
- 文档完整

---

## 风险和依赖

### 技术风险
| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| ChromaDB 多集合兼容性 | 中 | 提前测试，准备降级方案 |
| 配置迁移数据丢失 | 高 | 备份现有数据，测试迁移脚本 |
| 资源占用增加 | 中 | 懒加载机制，共享 Embedder |

### 依赖项
- PyYAML (配置加载)
- 现有 HarmonyOS 数据结构

---

## 回滚计划

如果迭代失败：
1. 保留现有 `harmony_docs` 集合
2. 新功能通过 feature flag 控制
3. 可以回退到单资料库模式

---

## 里程碑

| 里程碑 | 标准 |
|--------|------|
| **M1**: 配置系统完成 | 可以加载和管理配置 |
| **M2**: 多集合支持 | 可以查询不同资料库 |
| **M3**: API 完成 | 可以通过 API 管理资料库 |
| **M4**: MCP 扩展 | MCP 支持多资料库 |
| **M5**: 生产就绪 | Docker 部署，测试通过 |

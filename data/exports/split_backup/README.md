# ChromaDB 分卷备份

训练数据备份文件，用于在新的机器上快速恢复 RAG 服务。

## 文件说明

- **分卷数量**: 81 个文件
- **每卷大小**: 50 MB
- **总大小**: ~4.0 GB
- **格式**: SQLite3 数据库分卷

## 恢复方法

### 方法1：使用恢复脚本（推荐）

```bash
cd data/exports/split_backup
./restore.sh
```

### 方法2：手动恢复

```bash
# 1. 停止 RAG 服务
pkill -f "uvicorn api.main:app"

# 2. 合并分卷文件 (需要几分钟)
cat data/exports/split_backup/chroma.sqlite3.part* > data/vectorstore/chroma.sqlite3

# 3. 重启服务
cd /path/to/harmony-docs-rag
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## 验证

恢复后验证数据：

```bash
# 检查服务状态
curl http://localhost:8000/api/v1/health

# 测试查询
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"剪贴板 API","use_llm":false}'
```

## 数据统计

- **资料库**: harmonyos_full (HarmonyOS完整文档)
- **文档数量**: 9,693
- **向量数量**: 85,880 块
- **向量维度**: 768 (bge-base-zh-v1.5)
- **集合名称**: lib_harmonyos_full

## 注意事项

- ⚠️ 恢复过程需要几分钟时间
- ⚠️ 确保有足够的磁盘空间 (至少 5GB)
- ⚠️ 恢复前会自动备份现有数据库

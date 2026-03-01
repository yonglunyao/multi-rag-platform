#!/bin/bash
# 分卷备份 ChromaDB 数据库
# 每卷 1GB，可以推送到 GitHub

set -e

BACKUP_DIR="./data/exports/split_backup"
SOURCE_DB="./data/vectorstore/chroma.sqlite3"
PART_SIZE="1G"

echo "=== 分卷备份工具 ==="
echo "源文件: $SOURCE_DB"
echo "目标目录: $BACKUP_DIR"
echo "分卷大小: $PART_SIZE"
echo ""

# 检查源文件
if [ ! -f "$SOURCE_DB" ]; then
    echo "❌ 源文件不存在: $SOURCE_DB"
    exit 1
fi

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 获取文件信息
FILE_SIZE=$(stat -f%z "$SOURCE_DB" 2>/dev/null || stat -c%s "$SOURCE_DB")
FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))

echo "源文件大小: ${FILE_SIZE_MB} MB"
echo "开始分卷..."
echo ""

# 分卷备份
split -b "$PART_SIZE" "$SOURCE_DB" "$BACKUP_DIR/chroma.sqlite3.part"

# 列出生成的文件
PART_COUNT=$(ls -1 "$BACKUP_DIR"/chroma.sqlite3.part* | wc -l)
echo ""
echo "✅ 分卷完成！共 $PART_COUNT 个文件"
echo ""
echo "生成的文件:"
ls -lh "$BACKUP_DIR"/chroma.sqlite3.part* | awk '{print $9, $5}'

# 创建恢复脚本
cat > "$BACKUP_DIR/restore.sh" << 'RESTORE_EOF'
#!/bin/bash
# 恢复分卷文件

set -e

BACKUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DB="./data/vectorstore/chroma.sqlite3"

echo "=== 恢复 ChromaDB 数据 ==="
echo "备份目录: $BACKUP_DIR"
echo "目标文件: $TARGET_DB"
echo ""

# 检查分卷文件
PART_FILES=("$BACKUP_DIR"/chroma.sqlite3.part*)
if [ ${#PART_FILES[@]} -eq 0 ]; then
    echo "❌ 未找到分卷文件"
    exit 1
fi

echo "找到 ${#PART_FILES[@]} 个分卷文件"
echo "开始恢复..."
echo ""

# 停止服务
echo "停止 RAG 服务..."
pkill -f "uvicorn api.main:app" 2>/dev/null || true
sleep 2

# 创建目标目录
mkdir -p "$(dirname "$TARGET_DB")"

# 合并分卷
cat "$BACKUP_DIR"/chroma.sqlite3.part* > "$TARGET_DB"

# 验证文件
if [ -f "$TARGET_DB" ]; then
    RESTORED_SIZE=$(stat -f%z "$TARGET_DB" 2>/dev/null || stat -c%s "$TARGET_DB")
    RESTORED_SIZE_MB=$((RESTORED_SIZE / 1024 / 1024))
    echo "✅ 恢复完成！"
    echo "   文件大小: ${RESTORED_SIZE_MB} MB"
    echo "   位置: $TARGET_DB"
    echo ""
    echo "请重启 RAG 服务："
    echo "  cd $(dirname "$(dirname "$TARGET_DB")")"
    echo "  python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000"
else
    echo "❌ 恢复失败"
    exit 1
fi
RESTORE_EOF

chmod +x "$BACKUP_DIR/restore.sh"

# 创建说明文档
cat > "$BACKUP_DIR/README.md" << 'README_EOF'
# ChromaDB 分卷备份

## 文件列表

```
chroma.sqlite3.part*  - 数据库分卷文件 (每卷 1GB)
restore.sh           - 恢复脚本
```

## 恢复方法

### 方法1：使用恢复脚本（推荐）

```bash
./restore.sh
```

### 方法2：手动恢复

```bash
# 停止服务
pkill -f "uvicorn api.main:app"

# 合并分卷
cat chroma.sqlite3.part* > ../data/vectorstore/chroma.sqlite3

# 重启服务
cd ../..
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## 说明

- 原始文件大小：~4.0 GB
- 分卷数量：4 个
- 每卷大小：1 GB
- 总大小：~4.0 GB
README_EOF

# 创建元数据
cat > "$BACKUP_DIR/backup_info.json" << META_EOF
{
  "version": "1.0.0",
  "backup_date": "$(date -Iseconds)",
  "source_file": "chroma.sqlite3",
  "source_size_bytes": $FILE_SIZE,
  "source_size_mb": $FILE_SIZE_MB,
  "part_size": "1G",
  "part_count": $PART_COUNT,
  "description": "ChromaDB vector store split backup for GitHub"
}
META_EOF

echo ""
echo "=== 备份文件 ==="
echo "- 恢复脚本: restore.sh"
echo "- 说明文档: README.md"
echo "- 元数据: backup_info.json"
echo ""
echo "📁 备份目录: $BACKUP_DIR"
echo ""
echo "恢复方法："
echo "  cd $BACKUP_DIR"
echo "  ./restore.sh"

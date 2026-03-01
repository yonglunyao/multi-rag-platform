#!/bin/bash
# 恢复 ChromaDB 分卷备份 (81个分卷，每卷50MB)

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

# 备份现有文件
if [ -f "$TARGET_DB" ]; then
    echo "备份现有文件..."
    cp "$TARGET_DB" "${TARGET_DB}.before_restore"
fi

# 合并分卷
echo "合并分卷文件 (可能需要几分钟)..."
cat "$BACKUP_DIR"/chroma.sqlite3.part* > "$TARGET_DB"

# 验证文件
if [ -f "$TARGET_DB" ]; then
    RESTORED_SIZE=$(stat -c%s "$TARGET_DB")
    RESTORED_SIZE_MB=$((RESTORED_SIZE / 1024 / 1024))
    echo ""
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

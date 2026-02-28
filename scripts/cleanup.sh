#!/bin/bash
# 清理项目中的废弃文件

set -e

PROJECT_DIR="/home/mind/workspace/harmony-docs-rag"

echo "======================================"
echo "清理项目废弃文件"
echo "======================================"

# 1. 清理 Python 缓存文件
echo ""
echo "[1/3] 清理 Python 缓存文件..."
find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$PROJECT_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
find "$PROJECT_DIR" -type f -name ".pytest_cache" -delete 2>/dev/null || true
echo "✓ Python 缓存文件已清理"

# 2. 清理 /tmp 日志文件
echo ""
echo "[2/3] 清理临时日志文件..."
rm -f /tmp/*.log 2>/dev/null || true
echo "✓ 临时日志文件已清理"

# 3. 清理备份文件
echo ""
echo "[3/3] 清理备份文件..."
find "$PROJECT_DIR" -type f -name "*~" -delete 2>/dev/null || true
find "$PROJECT_DIR" -type f -name "*.bak" -delete 2>/dev/null || true
find "$PROJECT_DIR" -type f -name "*.swp" -delete 2>/dev/null || true
find "$PROJECT_DIR" -type f -name "*.swo" -delete 2>/dev/null || true
echo "✓ 备份文件已清理"

# 统计
echo ""
echo "======================================"
echo "清理完成！"
echo "======================================"

# 显示剩余的 Python 文件数量
python_count=$(find "$PROJECT_DIR" -name "*.py" -type f | wc -l)
echo "Python 文件: $python_count"

# 显示 __pycache__ 是否还有残留
pycache_count=$(find "$PROJECT_DIR" -name "__pycache__" -type d | wc -l)
echo "__pycache__ 目录: $pycache_count"

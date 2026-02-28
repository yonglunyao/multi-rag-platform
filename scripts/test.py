"""
简单测试脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.document_parser import HarmonyDocParser

def test_parser():
    """测试文档解析器"""
    docs_root = "/home/mind/workspace/harmonyos/docs/zh-cn/application-dev"
    parser = HarmonyDocParser(docs_root)

    # 扫描文件（限制5个用于测试）
    files = parser.scan_directory(max_files=5)
    print(f"Found {len(files)} files")

    # 解析第一个文件
    if files:
        result = parser.parse_file(files[0])
        if result:
            print(f"\nFile: {result['source']}")
            print(f"Category: {result['metadata'].category}")
            print(f"Kit: {result['metadata'].kit}")
            print(f"Subsystem: {result['metadata'].subsystem}")
            print(f"Content preview: {result['content'][:200]}...")
        else:
            print("Failed to parse file")


if __name__ == '__main__':
    test_parser()

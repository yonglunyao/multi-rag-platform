#!/bin/bash
# Multi-Library RAG 平台 - 快速测试脚本

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Multi-Library RAG 平台快速测试 ===${NC}\n"

# 1. 检查依赖
echo -e "${YELLOW}[1] 检查依赖...${NC}"
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}Python3 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python3 已安装${NC}"

# 2. 安装依赖
echo -e "\n${YELLOW}[2] 安装依赖...${NC}"
pip install -q pyyaml fastapi uvicorn || true
echo -e "${GREEN}✓ 依赖安装完成${NC}"

# 3. 测试配置加载
echo -e "\n${YELLOW}[3] 测试配置加载...${NC}"
python3 -c "
from core.config import load_config
config = load_config()
print(f'  资料库数量: {len(config.libraries)}')
for lib_id, lib in config.libraries.items():
    print(f'  - {lib_id}: {lib.name} ({\"enabled\" if lib.enabled else \"disabled\"})')
"
echo -e "${GREEN}✓ 配置加载成功${NC}"

# 4. 测试资料库管理器
echo -e "\n${YELLOW}[4] 测试资料库管理器...${NC}"
python3 -c "
from core.library_manager import get_library_manager
manager = get_library_manager()
libs = manager.list_libraries()
print(f'  启用的资料库: {len(libs)}')
for lib in libs:
    print(f'  - {lib.id}: {lib.name}')
"
echo -e "${GREEN}✓ 资料库管理器正常${NC}"

# 5. 测试向量存储
echo -e "\n${YELLOW}[5] 测试向量存储...${NC}"
python3 -c "
from core.vector_store import get_vector_store
vs = get_vector_store()
collections = vs.list_collections()
print(f'  集合数量: {len(collections)}')
for col in collections:
    stats = vs.get_stats(col)
    print(f'  - {col}: {stats[\"document_count\"]} 个文档')
"
echo -e "${GREEN}✓ 向量存储正常${NC}"

# 6. 测试解析器
echo -e "\n${YELLOW}[6] 测试解析器...${NC}"
python3 -c "
from core.parsers import get_parser
from core.models import LibraryType
parser = get_parser(LibraryType.HARMONY_OS)
print(f'  HarmonyOS 解析器: {type(parser).__name__}')
parser2 = get_parser(LibraryType.GENERIC_MARKDOWN)
print(f'  通用解析器: {type(parser2).__name__}')
"
echo -e "${GREEN}✓ 解析器正常${NC}"

# 7. 测试 API 健康检查
echo -e "\n${YELLOW}[7] 测试 API 健康检查...${NC}"
if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ RAG API 服务正常${NC}"
else
    echo -e "${YELLOW}⚠ RAG API 服务未运行（这是正常的，如果还没启动服务）${NC}"
fi

# 8. 总结
echo -e "\n${GREEN}=== 测试完成 ===${NC}"
echo -e "启动服务:"
echo -e "  ${YELLOW}docker-compose up -d${NC}"
echo -e ""
echo -e "查看日志:"
echo -e "  ${YELLOW}docker-compose logs -f${NC}"
echo -e ""

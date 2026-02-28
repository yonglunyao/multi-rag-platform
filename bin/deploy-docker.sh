#!/bin/bash
# HarmonyOS RAG Docker 部署脚本

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== HarmonyOS RAG Docker 部署 ===${NC}\n"

# 检查依赖
echo -e "${YELLOW}[1] 检查依赖...${NC}"
if ! command -v docker >/dev/null 2>&1; then
    echo -e "${YELLOW}Docker 未安装，请先安装 Docker${NC}"
    exit 1
fi
if ! command -v docker-compose >/dev/null 2>&1; then
    echo -e "${YELLOW}docker-compose 未安装，请先安装 docker-compose${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker 环境就绪${NC}"

# 构建 Docker 镜像
echo -e "\n${YELLOW}[2] 构建 Docker 镜像...${NC}"
docker-compose build

# 启动服务
echo -e "\n${YELLOW}[3] 启动服务...${NC}"
docker-compose up -d

# 等待服务启动
echo -e "\n${YELLOW}[4] 等待服务启动...${NC}"
sleep 10

# 检查服务状态
echo -e "\n${YELLOW}[5] 检查服务状态...${NC}"
docker-compose ps

# 健康检查
echo -e "\n${YELLOW}[6] 健康检查...${NC}"

if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ RAG API 服务正常${NC}"
    curl -s http://localhost:8000/api/v1/health | python3 -m json.tool 2>/dev/null || echo "  响应: OK"
else
    echo -e "${YELLOW}⚠ RAG API 服务未响应${NC}"
fi

if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ MCP SSE 服务正常${NC}"
    curl -s http://localhost:8001/health | python3 -m json.tool 2>/dev/null || echo "  响应: OK"
else
    echo -e "${YELLOW}⚠ MCP SSE 服务未响应${NC}"
fi

# 显示服务信息
IP=$(hostname -I | awk '{print $1}')
echo -e "\n${GREEN}=== 部署完成 ===${NC}"
echo -e "RAG API:       ${GREEN}http://localhost:8000${NC}"
echo -e "RAG API (远程): ${GREEN}http://$IP:8000${NC}"
echo -e "MCP SSE:       ${GREEN}http://$IP:8001/sse${NC}"
echo -e "健康检查:      ${GREEN}http://$IP:8000/api/v1/health${NC}"
echo -e ""
echo -e "${YELLOW}常用命令:${NC}"
echo -e "  查看日志: docker-compose logs -f"
echo -e "  停止服务: docker-compose down"
echo -e "  重启服务: docker-compose restart"
echo -e ""

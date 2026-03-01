#!/bin/bash
# HarmonyOS RAG 远程 MCP 服务启动脚本

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}HarmonyOS RAG 远程 MCP 服务${NC}"
echo -e "${GREEN}========================================${NC}"

# 1. 启动 RAG API 服务
echo -e "\n${YELLOW}[1/2] 启动 RAG API 服务 (端口 8000)...${NC}"
if ! curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    cd /home/mind/workspace/harmony-docs-rag
    nohup python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/rag-service.log 2>&1 &
    sleep 5
    if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ RAG API 服务启动成功${NC}"
    else
        echo -e "${RED}✗ RAG API 服务启动失败${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ RAG API 服务已运行${NC}"
fi

# 2. 启动 MCP SSE 服务
echo -e "\n${YELLOW}[2/2] 启动 MCP SSE 服务 (端口 8001)...${NC}"
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    cd /home/mind/workspace/harmony-docs-rag
    nohup python3 mcp_server_sse.py > /tmp/mcp-sse-service.log 2>&1 &
    sleep 3
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ MCP SSE 服务启动成功${NC}"
    else
        echo -e "${RED}✗ MCP SSE 服务启动失败${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ MCP SSE 服务已运行${NC}"
fi

# 显示配置信息
IP=$(hostname -I | awk '{print $1}')
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}服务状态${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "RAG API:       ${GREEN}http://localhost:8000${NC}"
echo -e "MCP SSE:       ${GREEN}http://$IP:8002/sse${NC}"
echo -e "健康检查:      ${GREEN}http://$IP:8002/health${NC}"

echo -e "\n${BLUE}本地 Claude Code 配置 (~/.config/claude-code/mcp_servers.json):${NC}"
cat << EOF
{
  "mcpServers": {
    "harmonyos-docs-rag": {
      "type": "sse",
      "url": "http://localhost:8002/sse"
    }
  }
}
EOF

echo -e "\n${BLUE}远程 Claude Code 配置:${NC}"
cat << EOF
{
  "mcpServers": {
    "harmonyos-docs-rag": {
      "type": "sse",
      "url": "http://$IP:8002/sse"
    }
  }
}
EOF

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}使用方式${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "@rag_query 长时任务需要什么权限"
echo -e "@rag_query 如何使用 UIAbility"
echo -e "@rag_query 剪贴板 API 用法"
echo -e "@list_libraries"
echo -e ""

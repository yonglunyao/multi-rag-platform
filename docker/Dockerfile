FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（增加超时和重试处理）
RUN pip install --no-cache-dir --timeout=1000 --retries=5 -r requirements.txt || \
    pip install --no-cache-dir --timeout=1000 --default-timeout=1000 -r requirements.txt

# 复制项目文件
COPY api/ ./api/
COPY core/ ./core/
COPY mcp_server_sse.py .
COPY .env.example .env

# 创建数据目录结构
RUN mkdir -p data/processed data/vectorstore data/documents data/libraries data/exports

# 暴露端口
EXPOSE 8000 8001

# 默认启动 RAG API 服务
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

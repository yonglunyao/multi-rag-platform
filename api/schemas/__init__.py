"""
Pydantic schemas for API requests and responses
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ===== 查询相关 =====

class QueryRequest(BaseModel):
    """查询请求"""
    query: str = Field(..., description="查询文本", min_length=1)
    context_length: int = Field(4, description="返回上下文数量", ge=1, le=10)
    temperature: float = Field(0.7, description="生成温度", ge=0.0, le=1.0)
    max_tokens: int = Field(2048, description="最大生成token数", ge=100, le=4096)
    filter: Optional[Dict[str, Any]] = Field(None, description="元数据过滤条件")


class SourceDocument(BaseModel):
    """来源文档"""
    file: str = Field(..., description="文件路径")
    relevance: float = Field(..., description="相关度分数")
    category: str = Field(..., description="文档分类")
    kit: str = Field("", description="所属Kit")


class QueryResponse(BaseModel):
    """查询响应"""
    answer: str = Field(..., description="生成的回答")
    sources: List[SourceDocument] = Field(default_factory=list, description="来源文档列表")


class BatchQueryRequest(BaseModel):
    """批量查询请求"""
    queries: List[str] = Field(..., description="查询列表", min_items=1, max_items=10)


class BatchQueryResponse(BaseModel):
    """批量查询响应"""
    results: Dict[str, List[Dict[str, Any]]]


# ===== Agent 相关 =====

class AgentSearchRequest(BaseModel):
    """Agent 搜索请求"""
    query: str = Field(..., description="搜索关键词", min_length=1)
    top_k: int = Field(5, description="返回结果数量", ge=1, le=20)
    filter: Optional[Dict[str, Any]] = Field(None, description="元数据过滤条件")
    return_content: bool = Field(True, description="是否返回文档内容")


class SearchResult(BaseModel):
    """搜索结果"""
    id: str
    document: str
    metadata: Dict[str, Any]
    score: float


class AgentSearchResponse(BaseModel):
    """Agent 搜索响应"""
    results: List[SearchResult]
    query: str
    total: int


class AgentContextRequest(BaseModel):
    """Agent 上下文请求"""
    user_query: str = Field(..., description="用户问题")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    max_tokens: int = Field(2000, description="最大上下文长度", ge=500, le=8000)


class AgentContextResponse(BaseModel):
    """Agent 上下文响应"""
    context: str
    sources: List[SourceDocument]


# ===== 健康检查 =====

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    document_count: int
    llm_status: str


# ===== 文档统计 =====

class DocumentStatsResponse(BaseModel):
    """文档统计响应"""
    total_documents: int
    collection_name: str
    categories: Dict[str, int]


# ===== 资料库管理相关 =====

class LibraryInfo(BaseModel):
    """资料库信息"""
    id: str
    name: str
    type: str
    enabled: bool
    status: str
    document_count: int
    chunk_count: int
    created_at: Optional[str] = None


class LibraryListResponse(BaseModel):
    """资料库列表响应"""
    libraries: List[LibraryInfo] = Field(default_factory=list)


class LibraryDetailResponse(BaseModel):
    """资料库详情响应"""
    id: str
    name: str
    type: str
    enabled: bool
    status: str
    source_path: str
    collection_name: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    document_count: int
    chunk_count: int
    last_indexed: Optional[str] = None
    created_at: Optional[str] = None


class LibraryCreateRequest(BaseModel):
    """创建资料库请求"""
    id: str = Field(..., description="资料库 ID（唯一标识）", min_length=1, max_length=50)
    name: str = Field(..., description="资料库名称", min_length=1, max_length=100)
    type: str = Field(..., description="资料库类型: harmony_os, generic_md, generic_pdf, custom")
    source_path: str = Field(..., description="文档源目录路径")
    enabled: bool = Field(True, description="是否启用")
    embedding_model: Optional[str] = Field(None, description="嵌入模型名称")
    chunk_size: Optional[int] = Field(None, description="分块大小", ge=100, le=5000)
    chunk_overlap: Optional[int] = Field(None, description="分块重叠", ge=0, le=1000)


class IndexResponse(BaseModel):
    """索引响应"""
    library_id: str
    status: str
    message: str
    task_id: str


class StatsResponse(BaseModel):
    """统计响应"""
    library_id: str
    name: str
    type: str
    enabled: bool
    status: str
    document_count: int
    chunk_count: int
    collection_name: str
    last_indexed: Optional[str] = None
    created_at: Optional[str] = None
    source_path: str


class ExportRequest(BaseModel):
    """导出请求"""
    format: str = Field("json", description="导出格式: json")
    include_embeddings: bool = Field(True, description="是否包含嵌入向量")


class ExportResponse(BaseModel):
    """导出响应"""
    library_id: str
    format: str
    file_path: str
    size_bytes: int
    download_url: str


class SetActiveRequest(BaseModel):
    """设置活动资料库请求"""
    library_id: str = Field(..., description="资料库 ID")


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str

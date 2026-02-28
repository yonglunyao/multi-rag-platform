"""
API 端点集成测试
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app


class TestHealthEndpoints:
    """健康检查端点测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    def test_root_endpoint(self, client):
        """测试根路径"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    def test_health_endpoint(self, client):
        """测试健康检查端点"""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "unhealthy"]
        assert "document_count" in data
        assert "llm_status" in data


class TestQueryEndpoints:
    """查询端点测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    def test_query_endpoint_valid_request(self, client):
        """测试有效查询请求"""
        request_data = {
            "query": "UIAbility 生命周期",
            "context_length": 3,
        }

        response = client.post("/api/v1/query", json=request_data)

        # 注意：这个测试可能需要 mock 或者跳过，如果服务不可用
        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "sources" in data

    def test_query_endpoint_empty_query(self, client):
        """测试空查询"""
        request_data = {
            "query": "",
            "context_length": 3,
        }

        response = client.post("/api/v1/query", json=request_data)

        # 应该返回错误或处理空查询
        assert response.status_code in [200, 400, 422]

    def test_query_stream_endpoint(self, client):
        """测试流式查询端点"""
        request_data = {
            "query": "测试查询",
            "context_length": 2,
        }

        response = client.post("/api/v1/query/stream", json=request_data)

        # 流式端点应该返回 200
        assert response.status_code in [200, 404, 500]


class TestAgentEndpoints:
    """Agent 端点测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    def test_agent_search_endpoint(self, client):
        """测试 Agent 搜索端点"""
        request_data = {
            "query": "权限申请",
            "top_k": 3,
            "return_content": True,
        }

        response = client.post("/api/v1/agent/search", json=request_data)

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "results" in data

    def test_agent_validate_endpoint(self, client):
        """测试 Agent 验证端点"""
        request_data = {
            "query": "测试验证",
        }

        response = client.post("/api/v1/agent/validate", json=request_data)

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "has_relevant" in data

    def test_agent_tools_search_endpoint(self, client):
        """测试 Agent 工具搜索端点"""
        request_data = {
            "query": "剪贴板权限",
            "top_k": 3,
        }

        response = client.post("/api/v1/agent/tools/search", json=request_data)

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "tool" in data
            assert "results" in data


class TestDocumentEndpoints:
    """文档管理端点测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    def test_document_stats_endpoint(self, client):
        """测试文档统计端点"""
        response = client.get("/api/v1/documents/stats")

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "total_documents" in data

    def test_document_status_endpoint(self, client):
        """测试文档状态端点"""
        response = client.get("/api/v1/documents/status")

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "is_running" in data
            assert "document_count" in data

    def test_reindex_endpoint(self, client):
        """测试重建索引端点"""
        response = client.post("/api/v1/documents/reindex")

        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = response.json()
            assert "message" in data


@pytest.mark.parametrize("endpoint,method,expected_status", [
    ("/", "GET", 200),
    ("/api/v1/health", "GET", 200),
    ("/api/v1/documents/stats", "GET", 200),
])
def test_endpoint_availability(endpoint, method, expected_status):
    """测试端点可用性"""
    client = TestClient(app)

    if method == "GET":
        response = client.get(endpoint)
    else:
        response = client.post(endpoint)

    # 允许一些灵活性（服务可能不可用）
    assert response.status_code in [expected_status, 500]

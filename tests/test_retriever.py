"""
Retriever 组件单元测试
"""
import pytest
from core.retriever import Retriever
from core.embedder import Embedder
from core.vector_store import VectorStore


class TestRetriever:
    """Retriever 单元测试"""

    @pytest.fixture
    def retriever(self, mock_vector_store, mock_embedder):
        """创建测试用的检索器"""
        return Retriever(
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            top_k=5,
            use_hybrid=True,
        )

    def test_extract_keywords_permissions(self, retriever):
        """测试权限关键词提取"""
        text = "需要申请 ohos.permission.READ_PASTEBOARD 权限"
        keywords = retriever._extract_keywords(text)

        assert "ohos.permission.READ_PASTEBOARD" in keywords

    def test_extract_keywords_apis(self, retriever):
        """测试 API 关键词提取"""
        text = "使用 @kit.NAPI 接口"
        keywords = retriever._extract_keywords(text)

        assert "@kit.NAPI" in keywords

    def test_extract_keywords_classes(self, retriever):
        """测试类名关键词提取"""
        text = "继承 UIAbility 和 AbilityContext"
        keywords = retriever._extract_keywords(text)

        assert "UIAbility" in keywords
        assert "AbilityContext" in keywords

    def test_keyword_match_score(self, retriever):
        """测试关键词匹配分数"""
        keywords = ["ohos.permission.READ_PASTEBOARD", "UIAbility"]
        text = "需要申请 ohos.permission.READ_PASTEBOARD 权限来使用剪贴板"

        score = retriever._keyword_match_score(keywords, text)

        assert score > 0.5  # 应该匹配到至少一个关键词

    def test_keyword_match_score_empty(self, retriever):
        """测试空关键词列表"""
        score = retriever._keyword_match_score([], "some text")

        assert score == 0.0

    def test_keyword_weight_permissions(self, retriever):
        """测试权限关键词权重"""
        # 权限名应该有 3 倍权重
        keywords = ["ohos.permission.READ_PASTEBOARD", "普通词"]
        text = "ohos.permission.READ_PASTEBOARD"

        score = retriever._keyword_match_score(keywords, text)
        # 权限匹配应该贡献更高的分数
        assert score > 0


class TestEmbedder:
    """Embedder 单元测试"""

    @pytest.fixture
    def embedder(self):
        """创建测试用的嵌入器"""
        return Embedder()

    def test_embed_text(self, embedder):
        """测试文本嵌入"""
        text = "测试文本嵌入"
        embedding = embedder.embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_texts_batch(self, embedder):
        """测试批量文本嵌入"""
        texts = ["文本1", "文本2", "文本3"]
        embeddings = embedder.embed_texts(texts)

        assert len(embeddings) == len(texts)
        assert all(isinstance(e, list) for e in embeddings)


class TestVectorStore:
    """VectorStore 单元测试"""

    @pytest.fixture
    def vector_store(self):
        """创建测试用的向量存储"""
        return VectorStore()

    def test_get_stats(self, vector_store):
        """测试获取统计信息"""
        stats = vector_store.get_stats()

        assert "document_count" in stats
        assert "collection_name" in stats
        assert stats["document_count"] >= 0


@pytest.fixture
def mock_vector_store(mocker):
    """模拟向量存储"""
    mock = mocker.Mock(spec=VectorStore)

    # 模拟搜索结果
    mock.search.return_value = [
        {
            "id": "1",
            "document": "测试文档内容",
            "metadata": {
                "source": "test.md",
                "category": "测试",
                "kit": "Test Kit"
            },
            "score": 0.9
        }
    ]

    mock.get_stats.return_value = {
        "document_count": 100,
        "collection_name": "test_collection"
    }

    return mock


@pytest.fixture
def mock_embedder(mocker):
    """模拟嵌入器"""
    mock = mocker.Mock(spec=Embedder)

    # 模拟嵌入向量
    mock.embed_text.return_value = [0.1] * 768
    mock.embed_texts.return_value = [[0.1] * 768, [0.2] * 768]

    return mock

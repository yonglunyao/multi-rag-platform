"""
文本嵌入模型：使用中文优化的 bge-small-zh-v1.5 (384维)
注意：与现有 harmony_docs 集合维度匹配
"""
import os
from typing import List, Union
from dotenv import load_dotenv
from loguru import logger
import torch


class Embedder:
    """文本嵌入模型"""

    def __init__(
        self,
        model_name: str = None,
        device: str = None,
    ):
        """
        初始化嵌入模型

        Args:
            model_name: 模型名称
            device: 运行设备 (cpu/cuda)
        """
        load_dotenv()

        self.model_name = model_name or os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-zh-v1.5')
        self.device = device or os.getenv('EMBEDDING_DEVICE', 'cpu')

        # 检测 CUDA
        if self.device == 'cuda' and not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to CPU")
            self.device = 'cpu'

        self.model = None
        self._load_model()

    def _load_model(self):
        """加载模型"""
        try:
            # 禁用 LangChain 的回调以避免冲突
            import os
            os.environ['LANGCHAIN_CALLBACKS'] = 'false'

            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Loaded embedding model: {self.model_name} on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def embed_text(self, text: str) -> List[float]:
        """
        对单个文本生成嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        if not self.model:
            self._load_model()

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成嵌入向量

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        if not self.model:
            self._load_model()

        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """返回嵌入向量维度"""
        if self.model:
            return self.model.get_sentence_embedding_dimension()
        return 768  # bge-base-zh-v1.5 的默认维度


# 单例模式
_embedder_instance = None


def get_embedder() -> Embedder:
    """获取嵌入模型单例"""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance

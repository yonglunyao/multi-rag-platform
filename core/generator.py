"""
LLM 生成器：使用 Ollama 本地模型
"""
import os
import json
from typing import List, AsyncGenerator
from dotenv import load_dotenv
from loguru import logger
import httpx
import asyncio


class Generator:
    """LLM 生成器"""

    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        temperature: float = None,
    ):
        """
        初始化生成器

        Args:
            base_url: Ollama API 地址
            model: 模型名称
            temperature: 生成温度
        """
        load_dotenv()

        self.base_url = base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = model or os.getenv('LLM_MODEL', 'qwen2.5:7b')
        self.temperature = temperature or float(os.getenv('LLM_TEMPERATURE', '0.7'))
        self.max_tokens = int(os.getenv('LLM_MAX_TOKENS', '2048'))

        # 检查 Ollama 连接
        self._check_connection()

    def _check_connection(self):
        """检查 Ollama 服务是否可用"""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    logger.info(f"Connected to Ollama at {self.base_url}")
                else:
                    logger.warning(f"Ollama returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Cannot connect to Ollama: {e}")

    def generate(
        self,
        query: str,
        context: str,
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """
        根据查询和上下文生成回答

        Args:
            query: 用户查询
            context: 检索到的上下文
            temperature: 生成温度
            max_tokens: 最大token数

        Returns:
            生成的回答
        """
        temperature = temperature or self.temperature
        max_tokens = max_tokens or self.max_tokens

        # 构建提示词
        prompt = self._build_prompt(query, context)

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        }
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '').strip()
                else:
                    logger.error(f"Ollama error: {response.status_code} - {response.text}")
                    return self._fallback_response(query, context)

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return self._fallback_response(query, context)

    def _build_prompt(self, query: str, context: str) -> str:
        """构建提示词"""
        return f"""你是一个 HarmonyOS 应用开发专家助手。

【关键约束 - 必须严格遵守】
1. **只基于以下文档内容回答**，不得使用文档之外的知识
2. **权限名称必须完全匹配**：只使用文档中明确出现的以"ohos.permission."开头的权限名
3. **不得编造技术术语**：如果文档中没有提到某个权限或API，必须说"文档中没有提及"
4. **区分不同概念**：短时任务、长时任务、后台代理是不同的功能，不能混淆
5. **不确定性处理**：如果文档信息不完整，明确说明"根据文档现有信息"并只提及文档中确实存在的内容

文档内容：
{context}

用户问题：{query}

请基于文档内容准确回答。如果文档中没有明确提及所需权限，请明确说明"文档中未提及该功能的权限要求"。

回答："""

    def _fallback_response(self, query: str, context: str) -> str:
        """当 LLM 不可用时的降级响应"""
        return f"根据检索到的文档，关于「{query}」的相关信息请参考：{context[:200]}..."

    async def generate_stream(
        self,
        query: str,
        context: str,
        temperature: float = None,
        max_tokens: int = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回答

        Args:
            query: 用户查询
            context: 检索到的上下文
            temperature: 生成温度
            max_tokens: 最大token数

        Yields:
            生成的文本片段
        """
        temperature = temperature or self.temperature
        max_tokens = max_tokens or self.max_tokens

        # 构建提示词
        prompt = self._build_prompt(query, context)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        }
                    }
                ) as response:
                    if response.status_code == 200:
                        async for line in response.aiter_lines():
                            if line.strip():
                                try:
                                    data = json.loads(line)
                                    if "response" in data:
                                        yield data["response"]
                                except json.JSONDecodeError:
                                    continue
                    else:
                        logger.error(f"Ollama error: {response.status_code}")
                        yield self._fallback_response(query, context)

        except Exception as e:
            logger.error(f"Stream generation error: {e}")
            yield self._fallback_response(query, context)


# 单例模式
_generator_instance = None


def get_generator() -> Generator:
    """获取生成器单例"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = Generator()
    return _generator_instance

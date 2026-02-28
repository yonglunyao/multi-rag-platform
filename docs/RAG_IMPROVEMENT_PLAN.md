# RAG 系统改进方案

## 当前问题总结

1. **检索召回率不足** - 相关文档没有被检索到
2. **LLM 幻觉** - 生成不在文档中的内容
3. **检索精度低** - 返回的文档相关度不高
4. **Prompt 工程** - 没有约束 LLM 行为

---

## 改进方案（按优先级）

### 优先级 1: 修复 Prompt 工程

**问题**: LLM 没有被约束仅基于文档回答

**解决方案**: 在 generator.py 中改进 Prompt

```python
def _build_prompt(self, query: str, context: str) -> str:
    return f"""你是一个 HarmonyOS 应用开发专家助手。

【重要】请严格遵守以下规则：
1. 只基于以下文档内容回答问题
2. 如果文档中没有相关信息，明确说明"文档中没有提到"
3. 不得编造或猜测任何权限名称、API 名称
4. 引用文档时使用准确的术语

文档内容：
{context}

用户问题：{query}

请基于上述文档内容回答：
"""
```

### 优先级 2: 改进文档分块策略

**问题**: 当前分块大小 (500) 可能太小，导致上下文丢失

**解决方案**:
- 增加分块大小到 1000-1500
- 按标题层级分块（保持语义完整）
- 添加重叠区域确保上下文连续

```python
# core/document_parser.py
CHUNK_SIZE = 1000  # 增加到 1000
CHUNK_OVERLAP = 200  # 增加重叠
```

### 优先级 3: 改进检索策略

**问题**: 纯向量检索召回不足

**解决方案**: 实现混合检索（BM25 + 向量）

```python
# 核心改进：添加关键词权重
def retrieve(self, query: str, top_k: int = 5):
    # 1. 向量检索
    vector_results = self.vector_store.search(query_embedding, top_k=top_k * 2)

    # 2. 关键词匹配（提取权限名、API 名等术语）
    keywords = self._extract_technical_terms(query)
    for result in vector_results:
        keyword_score = self._match_keywords(keywords, result['document'])
        result['score'] = 0.6 * result['score'] + 0.4 * keyword_score

    # 3. 重新排序
    vector_results.sort(key=lambda x: x['score'], reverse=True)
    return vector_results[:top_k]
```

### 优先级 4: 添加文档重排序

**问题**: 向量相似度不一定等于语义相关性

**解决方案**: 使用 Cross-Encoder 重排序

```python
# 安装: pip install flagembedding
from FlagEmbedding import FlagReranker

reranker = FlagReranker('BAAI/bge-reranker-base')

def rerank_results(query, results):
    pairs = [[query, doc['document']] for doc in results]
    scores = reranker.compute_score(pairs)
    for doc, score in zip(results, scores):
        doc['rerank_score'] = score
    results.sort(key=lambda x: x['rerank_score'], reverse=True)
    return results
```

### 优先级 5: 更换更好的嵌入模型

**问题**: bge-base-zh-v1.5 可能不够准确

**解决方案**: 升级到更大或专门优化的模型

| 模型 | 维度 | 特点 |
|------|------|------|
| bge-large-zh-v1.5 | 1024 | 更高精度，需要更多资源 |
| bge-reranker-base | 768 | 专门用于重排序 |
| m3e-base | 768 | 中文通用 |

### 优先级 6: 添加元数据过滤

**问题**: 没有利用文档的 Kit/Subsystem 元数据

**解决方案**: 增强检索时考虑元数据

```python
def retrieve(self, query: str, filters: dict = None):
    # 提取查询中的 Kit 上下文
    detected_kits = self._detect_kits_in_query(query)

    # 如果检测到 Kit，优先过滤
    if detected_kits:
        filter = {'kit': {'$in': detected_kits}}

    results = self.vector_store.search(query_embedding, top_k=top_k, filter=filter)
    return results
```

---

## 实施建议

### 立即可做（高优先级）

1. **修改 Prompt** - 最快见效，10分钟
2. **调整分块参数** - 需要重新索引，30分钟
3. **添加关键词匹配** - 改进代码，1小时

### 中期优化

4. **添加重排序** - 安装依赖，2小时
5. **元数据过滤** - 功能增强，3小时

### 长期优化

6. **更换嵌入模型** - 需要重新索引和测试
7. **微调嵌入模型** - 需要标注数据和训练资源

---

## 快速验证方案

### 测试用例集

```python
test_cases = [
    {
        "query": "鸿蒙应用读取剪贴板需要什么权限",
        "expected": ["ohos.permission.READ_PASTEBOARD"],
        "must_not_contain": ["READ_EXTERNAL_DATA", "READ_CONTACTS"]
    },
    {
        "query": "UIAbility 生命周期有哪些回调",
        "expected": ["onCreate", "onStart", "onForeground", "onBackground", "onDestroy"],
        "must_not_contain": ["onResume", "onPause"]  # Android 生命周期
    },
    {
        "query": "如何创建分布式任务",
        "expected": ["distributedSchedule", "DeviceManager"],
        "must_not_contain": ["WorkManager", "JobScheduler"]  # Android API
    }
]
```

### 评估指标

| 指标 | 目标 | 当前 |
|------|------|------|
| 准确率 | >85% | ~60% |
| 幻觉率 | <5% | ~30% |
| 检索召回率 | >80% | ~50% |
| 响应时间 | <2秒 | 10秒 |

---

## 下一步行动

建议优先实施：
1. 修改 Prompt 添加约束
2. 增加分块大小
3. 添加关键词匹配

需要我立即实施这些改进吗？

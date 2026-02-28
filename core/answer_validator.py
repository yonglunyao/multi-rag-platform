"""
答案验证：验证生成的答案中的权限名是否在上下文中存在
"""
import re
from typing import List, Dict, Any
from loguru import logger


class AnswerValidator:
    """答案验证器"""

    # 验证规则
    VALIDATION_RULES = {
        'permission': {
            'pattern': r'ohos\.permission\.[a-zA-Z0-9_]+',
            'required': True,
            'description': 'HarmonyOS权限名'
        },
        'api': {
            'pattern': r'@[a-zA-Z]+\.[a-zA-Z0-9_]+',
            'required': False,
            'description': 'API标识'
        },
        'class': {
            'pattern': r'\b[A-Z][a-zA-Z]+(?:Ability|Context|Manager|Kit|Service)\b',
            'required': False,
            'description': '类名'
        },
    }

    def validate_answer(self, answer: str, context_documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        验证答案中的技术术语是否在上下文中存在

        Args:
            answer: 生成的答案
            context_documents: 检索到的上下文文档

        Returns:
            验证结果
        """
        # 提取答案中的所有技术术语
        extracted = self._extract_technical_terms(answer)

        # 构建上下文词汇集合
        context_text = " ".join([doc['document'] for doc in context_documents])
        context_terms = self._build_context_terms(context_text)

        # 验证每个提取的术语
        validation_results = {
            'valid': [],
            'invalid': [],
            'missing_rules': []
        }

        for term, term_type in extracted:
            if term_type not in self.VALIDATION_RULES:
                continue

            # 检查是否在上下文中
            is_in_context = self._check_in_context(term, context_text, context_terms)

            if is_in_context:
                validation_results['valid'].append({
                    'term': term,
                    'type': term_type
                })
            else:
                validation_results['invalid'].append({
                    'term': term,
                    'type': term_type
                })

        # 计算验证分数
        # 提取答案中所有必选类型的术语
        required_terms_in_answer = [item for item in validation_results['valid'] + validation_results['invalid']
                                    if self.VALIDATION_RULES.get(item.get('type'), {}).get('required', False)]

        # 统计必选术语中有效的数量
        valid_required = sum(1 for item in validation_results['valid']
                            if self.VALIDATION_RULES.get(item['type'], {}).get('required', False))

        # 计算分数：有效的必选术语 / 答案中所有必选术语
        if len(required_terms_in_answer) > 0:
            validation_results['score'] = valid_required / len(required_terms_in_answer)
        else:
            # 如果答案中没有必选术语（如权限名），则检查是否有可选术语
            if validation_results['valid']:
                validation_results['score'] = 1.0  # 有可选术语匹配，视为有效
            else:
                validation_results['score'] = 0.0  # 完全没有技术术语匹配

        # 调试日志
        logger.debug(f"Validation: extracted {len(extracted)} terms, "
                    f"required in answer: {len(required_terms_in_answer)}, "
                    f"valid required: {valid_required}, "
                    f"score: {validation_results['score']:.2%}")
        if validation_results['invalid']:
            logger.debug(f"Invalid terms: {[item['term'] for item in validation_results['invalid']]}")

        return validation_results

    def _extract_technical_terms(self, text: str) -> List[tuple[str, str]]:
        """提取文本中的技术术语"""
        results = []

        for term_type, rule in self.VALIDATION_RULES.items():
            pattern = rule['pattern']
            matches = re.findall(pattern, text)

            for match in matches:
                results.append((match, term_type))

        return results

    def _build_context_terms(self, context_text: str) -> set:
        """构建上下文词汇集合"""
        terms = set()

        # 添加所有权限名
        terms.update(re.findall(r'ohos\.permission\.[a-zA-Z0-9_]+', context_text))

        # 添加 API 标识
        terms.update(re.findall(r'@[a-zA-Z]+\.[a-zA-Z0-9_]+', context_text))

        # 添加类名
        terms.update(re.findall(r'\b[A-Z][a-zA-Z]+(?:Ability|Context|Manager|Kit|Service)\b', context_text))

        return terms

    def _check_in_context(self, term: str, context_text: str, context_terms: set) -> bool:
        """检查术语是否在上下文中"""
        # 精确匹配
        if term in context_text:
            return True

        # 在术语集合中
        if term in context_terms:
            return True

        return False

    def should_reject(self, validation_results: Dict[str, Any], threshold: float = 0.5) -> tuple[bool, str]:
        """
        判断是否应该拒绝该答案

        Args:
            validation_results: 验证结果
            threshold: 拒绝阈值

        Returns:
            (是否拒绝, 拒绝原因)
        """
        score = validation_results.get('score', 0)

        if score < threshold:
            return True, f"答案中的技术术语验证失败（准确率: {score:.0%}）"

        if validation_results['invalid']:
            invalid_terms = [item['term'] for item in validation_results['invalid']]
            # 检查是否有必须的术语无效
            required_invalid = any(
                self.VALIDATION_RULES.get(item['type'], {}).get('required', False)
                for item in validation_results['invalid']
            )
            if required_invalid:
                return True, f"答案中提到了上下文中不存在的权限: {invalid_terms}"

        return False, ""


# 单例
_answer_validator_instance = None


def get_answer_validator() -> AnswerValidator:
    """获取答案验证器单例"""
    global _answer_validator_instance
    if _answer_validator_instance is None:
        _answer_validator_instance = AnswerValidator()
    return _answer_validator_instance

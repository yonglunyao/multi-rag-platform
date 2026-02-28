"""
查询扩展：将用户查询扩展为包含技术术语
"""
import re
from typing import List, Dict
from loguru import logger


class QueryExpander:
    """查询扩展器"""

    # 查询扩展映射表
    EXPANSION_RULES = {
        # 后台任务相关
        "后台任务": ["backgroundTask", "backgroundTaskManager", "后台模式", "backgroundModes"],
        "长时任务": ["continuous-task", "长时任务", "ContinuousTask", "startBackgroundRunning"],
        "短时任务": ["transient-task", "短时任务", "requestSuspendDelay", "DelaySuspendInfo"],
        "后台运行": ["KEEP_BACKGROUND_RUNNING", "background running"],

        # 权限相关
        "权限申请": ["申请权限", "requestPermissions", "权限声明", "declare-permissions"],
        "后台权限": ["background permission", "后台模式权限"],
        "权限": ["ohos.permission", "permission", "权限"],

        # 组件相关
        "页面": ["UIAbility", "Page", "Ability", "窗口"],
        "服务": ["ServiceAbility", "ServiceExtensionAbility"],
        "数据共享": ["DataShareExtensionAbility"],

        # Kit相关
        "剪贴板": ["Pasteboard", "pasteboard"],
        "网络": ["网络连接", "NetManager"],
        "相机": ["Camera", "cameraKit"],

        # API相关
        "创建": ["申请", "start", "create", "init"],
        "使用": ["调用", "call", "use", "apply"],
        "停止": ["取消", "cancel", "stop"],
    }

    # 组合模式扩展：当多个关键词同时出现时，添加额外的扩展
    COMBO_PATTERNS = {
        ("后台任务", "权限"): ["ohos.permission.KEEP_BACKGROUND_RUNNING", "长时任务", "短时任务"],
        ("长时任务", "权限"): ["ohos.permission.KEEP_BACKGROUND_RUNNING", "startBackgroundRunning"],
        ("后台运行", "权限"): ["ohos.permission.KEEP_BACKGROUND_RUNNING"],
        ("短时任务", "权限"): ["requestSuspendDelay"],  # 短时任务不需要权限
        ("剪贴板", "权限"): ["ohos.permission.READ_PASTEBOARD", "ohos.permission.WRITE_PASTEBOARD"],
    }

    # 技术术语到常见查询词的反向映射
    TECHNICAL_TERMS = {
        # 后台任务
        "backgroundTaskManager": "后台任务管理器",
        "startBackgroundRunning": "申请长时任务",
        "requestSuspendDelay": "申请短时任务",
        "continuous-task": "长时任务",
        "transient-task": "短时任务",
        "KEEP_BACKGROUND_RUNNING": "后台运行权限",

        # 权限
        "ohos.permission": "HarmonyOS权限",
        "requestPermissionsFromUser": "向用户申请授权",
        "declare-permissions": "声明权限",

        # 组件
        "UIAbility": "页面能力",
        "ServiceAbility": "服务能力",
        "AbilityStage": "能力调度",

        # Kit
        "BackgroundTasksKit": "后台任务套件",
        "AbilityKit": "能力套件",
    }

    def expand_query(self, query: str) -> List[str]:
        """
        扩展查询，返回扩展后的查询列表

        Args:
            query: 原始查询

        Returns:
            扩展后的查询列表（包含原始查询）
        """
        queries = [query]

        # 提取查询中的关键词
        keywords = self._extract_keywords(query)

        # 对每个关键词进行扩展
        for keyword in keywords:
            if keyword in self.EXPANSION_RULES:
                # 添加技术术语
                technical_terms = self.EXPANSION_RULES[keyword]
                for term in technical_terms:
                    if term not in query:
                        queries.append(f"{query} {term}")

        # 检查组合模式
        for combo, extra_terms in self.COMBO_PATTERNS.items():
            if all(kw in query for kw in combo):
                for term in extra_terms:
                    if term not in query and not any(term in q for q in queries):
                        queries.append(f"{query} {term}")
                        logger.debug(f"Combo pattern matched: {combo} -> adding '{term}'")

        return queries

    def _extract_keywords(self, query: str) -> List[str]:
        """从查询中提取关键词"""
        keywords = []

        # 匹配扩展规则中的关键词
        for key in self.EXPANSION_RULES.keys():
            if key in query:
                keywords.append(key)

        return keywords

    def expand_with_context(self, query: str, context_history: List[str] = None) -> str:
        """
        基于上下文的查询扩展

        Args:
            query: 当前查询
            context_history: 对话历史

        Returns:
            增强后的查询
        """
        # 如果有对话历史，从中提取关键词
        if context_history and len(context_history) > 0:
            recent_context = context_history[-2:] if len(context_history) >= 2 else context_history
            context_text = " ".join(recent_context)

            # 提取技术术语
            technical_terms = []
            for term, desc in self.TECHNICAL_TERMS.items():
                if term in context_text or desc in context_text:
                    technical_terms.append(term)

            if technical_terms:
                # 将技术术语添加到查询中
                terms_str = " ".join(technical_terms[:3])  # 最多3个
                return f"{query} ({terms_str})"

        return query


# 单例
_query_expander_instance = None


def get_query_expander() -> QueryExpander:
    """获取查询扩展器单例"""
    global _query_expander_instance
    if _query_expander_instance is None:
        _query_expander_instance = QueryExpander()
    return _query_expander_instance

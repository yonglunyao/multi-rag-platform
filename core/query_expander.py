"""
查询扩展：将用户查询扩展为包含技术术语、同义词、拼音等多维度查询

支持：
- 同义词扩展
- 拼音匹配
- 英文/中文互译
- HarmonyOS 领域术语
"""
import re
from typing import List, Dict, Set, Tuple
from loguru import logger

try:
    from pypinyin import lazy_pinyin, Style
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False
    logger.warning("pypinyin not installed, pinyin expansion disabled")


class QueryExpander:
    """查询扩展器 - 多维度查询增强"""

    # ========== 1. 同义词映射 ==========
    SYNONYMS = {
        # Ability 相关
        "ability": ["页面", "页面能力", "UIAbility", "窗口", "abilityslice", "AbilitySlice"],
        "uiability": ["页面", "页面能力", "窗口", "ability"],
        "abilityslice": ["切片", "切片能力", "ability"],

        # Service 相关
        "service": ["服务", "serviceability", "后台服务", "extensionability"],

        # 权限相关
        "权限": ["permission", "许可", "授权", "ohos.permission"],
        "申请权限": ["requestPermissions", "权限声明", "declare-permissions", "向用户申请授权"],

        # 后台任务
        "后台任务": ["backgroundTask", "backgroundTaskManager", "后台模式", "backgroundModes"],
        "长时任务": ["continuous-task", "长时任务", "ContinuousTask", "startBackgroundRunning"],
        "短时任务": ["transient-task", "短时任务", "requestSuspendDelay"],
        "后台运行": ["KEEP_BACKGROUND_RUNNING", "background running"],

        # Kit 相关
        "剪贴板": ["Pasteboard", "pasteboard", "clipboard"],
        "相机": ["Camera", "cameraKit"],
        "屏幕时间": ["ScreenTime", "screen time"],
        "屏幕时间守护": ["ScreenTimeGuard", "screen time guard", "守护"],

        # MDM 相关
        "mdm": ["企业设备管理", "enterprise device management", "MDM Kit"],
        "byod": ["自带设备", "个人设备", "bring your own device"],
        "策略": ["policy", "限制", "restrictions"],
        "wifi": ["Wi-Fi", "无线网络", "无线局域网"],

        # 网络相关
        "网络": ["network", "网络连接", "netmanager"],
        "蓝牙": ["bluetooth", "BT", "蓝牙"],
        "nfc": ["近场通信", "near field communication"],

        # 安全相关
        "加密": ["encryption", "encrypt"],
        "认证": ["auth", "authentication", "verify"],
        "签名": ["signature", "sign"],

        # 设备相关
        "设备": ["device", "终端"],
        "手机": ["phone", "移动电话"],
        "平板": ["tablet", "pad"],
        "电脑": ["pc", "computer"],
    }

    # ========== 2. 英文-中文映射 ==========
    EN_CN_TERMS = {
        # API keywords
        "create": ["创建", "申请", "start", "init", "新建"],
        "query": ["查询", "搜索", "search"],
        "update": ["更新", "修改", "upgrade"],
        "delete": ["删除", "移除", "remove"],
        "add": ["添加", "增加", "insert"],

        # HarmonyOS specific
        "ability": ["能力", "uiability"],
        "bundle": ["包", "应用包", "bundleName"],
        "module": ["模块", "ng分"],
        "process": ["进程", "处理"],
        "thread": ["线程"],

        # MDM terms
        "policy": ["策略", "限制"],
        "restrictions": ["限制类策略", "企业限制"],
        "provisioning": ["配置", "供应", "设置"],
        "enrollment": ["注册", "登记"],
        "wipe": ["擦除", "清除"],
        "lock": ["锁定", "锁屏"],

        # Network
        "ssid": ["网络名称", "wifi名称"],
        "bssid": ["mac地址", "ap地址"],
        "password": ["密码", "密钥", "key"],
        "security": ["安全", "加密方式", "认证方式"],
    }

    # ========== 3. HarmonyOS 领域术语 ==========
    HARMONYOS_TERMS = {
        # Kits
        "backgroundtaskskit": ["后台任务套件", "BackgroundTasksKit"],
        "abilitykit": ["能力套件", "AbilityKit"],
        "screentimeguardkit": ["屏幕时间守护套件", "ScreenTimeGuardKit"],
        "mdmkit": ["企业设备管理套件", "MDM Kit"],

        # Components
        "uiability": ["页面能力", "UIAbility", "页面"],
        "serviceability": ["服务能力", "ServiceAbility", "后台服务"],
        "extensionability": ["扩展能力", "ExtensionAbility"],
        "dataharextensionability": ["数据共享能力", "DataShareExtensionAbility"],

        # Permissions
        "ohos.permission.manage_screen_time_guard": ["屏幕时间守护权限"],
        "ohos.permission.enterprise_manage_wifi": ["企业Wi-Fi管理权限"],
        "ohos.permission.enterprise_manage_restrictions": ["企业限制管理权限"],

        # API modules
        "networkmanager": ["网络管理器", "@ohos.enterprise.networkManager"],
        "wifimanager": ["Wi-Fi管理器", "@ohos.enterprise.wifiManager"],
        "restrictions": ["限制策略", "@ohos.enterprise.restrictions"],
        "adminmanager": ["管理员权限", "@ohos.enterprise.adminManager"],

        # Concepts
        "byod": ["自带设备办公", "Bring Your Own Device"],
        "cope": ["企业所有设备", "Corporate Owned Personally Enabled"],
        "supervised": ["受监管设备", "监督模式"],
    }

    # ========== 4. 常见纠错映射 ==========
    TYPO_CORRECTIONS = {
        "screentimeguard": "ScreenTimeGuard",
        "screen_time_guard": "ScreenTimeGuard",
        "backgroundmode": "backgroundModes",
        "backgroundtask": "backgroundTask",
        "uiability": "UIAbility",
        "serviceability": "ServiceAbility",
        "extensionability": "ExtensionAbility",
        "wifimanager": "wifiManager",
        "networkmanager": "networkManager",
    }

    def __init__(self):
        """初始化查询扩展器"""
        # 构建反向索引用于快速查找
        self._synonym_reverse = self._build_reverse_index()
        self._en_cn_reverse = self._build_en_cn_reverse()

    def _build_reverse_index(self) -> Dict[str, List[str]]:
        """构建同义词反向索引"""
        reverse = {}
        for main_term, synonyms in self.SYNONYMS.items():
            for syn in synonyms:
                if syn not in reverse:
                    reverse[syn] = []
                reverse[syn].append(main_term)
        return reverse

    def _build_en_cn_reverse(self) -> Dict[str, List[str]]:
        """构建英文-中文反向索引"""
        reverse = {}
        for en_term, cn_terms in self.EN_CN_TERMS.items():
            for cn_term in cn_terms:
                if cn_term not in reverse:
                    reverse[cn_term] = []
                reverse[cn_term].append(en_term)
        return reverse

    def expand_query(self, query: str, max_expansions: int = 8) -> List[str]:
        """
        扩展查询，返回多维度扩展后的查询列表

        Args:
            query: 原始查询
            max_expansions: 最大扩展数量

        Returns:
            扩展后的查询列表（包含原始查询）
        """
        queries = [query]
        seen = {query.lower()}

        # 1. 基础同义词扩展
        queries.extend(self._expand_with_synonyms(query, seen, max_expansions))

        # 2. 英文-中文互译扩展
        queries.extend(self._expand_with_translation(query, seen, max_expansions))

        # 3. 拼音扩展（如果可用）
        if PYPINYIN_AVAILABLE:
            queries.extend(self._expand_with_pinyin(query, seen, max_expansions))

        # 4. HarmonyOS 领域术语扩展
        queries.extend(self._expand_with_harmonyos_terms(query, seen, max_expansions))

        # 5. 拼写纠错
        queries.extend(self._expand_with_correction(query, seen))

        # 去重并保持顺序
        unique_queries = []
        for q in queries:
            lower = q.lower()
            if lower not in seen and len(unique_queries) < max_expansions:
                seen.add(lower)
                unique_queries.append(q)

        logger.debug(f"Query expansion: '{query}' -> {len(unique_queries)} variants")
        return unique_queries

    def _expand_with_synonyms(self, query: str, seen: Set[str], max_count: int) -> List[str]:
        """使用同义词扩展查询"""
        expansions = []

        for term, synonyms in self.SYNONYMS.items():
            if term.lower() in query.lower():
                for syn in synonyms:
                    expanded = query.replace(term, syn, 1)
                    if expanded.lower() not in seen:
                        expansions.append(expanded)
                        if len(expansions) >= max_count:
                            break

        return expansions

    def _expand_with_translation(self, query: str, seen: Set[str], max_count: int) -> List[str]:
        """使用英文-中文互译扩展"""
        expansions = []

        # 中文 -> 英文
        for cn_term, en_terms in self._en_cn_reverse.items():
            if cn_term in query:
                for en_term in en_terms:
                    expanded = query.replace(cn_term, en_term, 1)
                    if expanded.lower() not in seen:
                        expansions.append(expanded)

        # 英文 -> 中文
        for word in query.split():
            if word in self.EN_CN_TERMS:
                for cn_term in self.EN_CN_TERMS[word]:
                    expanded = query.replace(word, cn_term, 1)
                    if expanded.lower() not in seen:
                        expansions.append(expanded)

        return expansions[:max_count]

    def _expand_with_pinyin(self, query: str, seen: Set[str], max_count: int) -> List[str]:
        """使用拼音扩展查询"""
        if not PYPINYIN_AVAILABLE:
            return []

        expansions = []
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', query)

        for chars in chinese_chars:
            # 全拼
            full_pinyin = ''.join([''.join(p) for p in lazy_pinyin(chars, style=Style.NORMAL)])
            if full_pinyin != chars and full_pinyin.lower() not in seen:
                expansions.append(query.replace(chars, full_pinyin, 1))

            # 首字母
            first_letters = ''.join([p[0] for p in lazy_pinyin(chars, style=Style.FIRST_LETTER)])
            if first_letters and first_letters != chars and first_letters.lower() not in seen:
                expansions.append(query.replace(chars, first_letters, 1))

        return expansions[:max_count]

    def _expand_with_harmonyos_terms(self, query: str, seen: Set[str], max_count: int) -> List[str]:
        """使用HarmonyOS领域术语扩展"""
        expansions = []

        # 转小写匹配
        query_lower = query.lower()

        for term, variations in self.HARMONYOS_TERMS.items():
            if term.lower() in query_lower:
                for variation in variations:
                    # 替换为完整术语
                    expanded = re.sub(term, variation, query, flags=re.IGNORECASE)
                    if expanded.lower() != query_lower and expanded.lower() not in seen:
                        expansions.append(expanded)

        return expansions[:max_count]

    def _expand_with_correction(self, query: str, seen: Set[str]) -> List[str]:
        """拼写纠错扩展"""
        expansions = []

        for typo, correct in self.TYPO_CORRECTIONS.items():
            if typo.lower() in query.lower():
                corrected = re.sub(typo, correct, query, flags=re.IGNORECASE)
                if corrected != query and corrected.lower() not in seen:
                    expansions.append(corrected)

        return expansions

    def get_expansion_metadata(self, query: str) -> Dict[str, any]:
        """
        获取查询扩展的元数据（用于调试和分析）

        Returns:
            扩展元数据字典
        """
        metadata = {
            "original": query,
            "has_synonyms": False,
            "has_translation": False,
            "has_pinyin": False,
            "has_corrections": False,
            "has_harmonyos_terms": False,
        }

        query_lower = query.lower()

        # 检查各种扩展类型
        for term, synonyms in self.SYNONYMS.items():
            if term.lower() in query_lower:
                metadata["has_synonyms"] = True
                break

        for cn_term in self._en_cn_reverse:
            if cn_term in query:
                metadata["has_translation"] = True
                break

        if PYPINYIN_AVAILABLE:
            chinese_chars = re.findall(r'[\u4e00-\u9fff]+', query)
            if chinese_chars:
                metadata["has_pinyin"] = True

        for typo in self.TYPO_CORRECTIONS:
            if typo.lower() in query_lower:
                metadata["has_corrections"] = True
                break

        for term in self.HARMONYOS_TERMS:
            if term.lower() in query_lower:
                metadata["has_harmonyos_terms"] = True
                break

        return metadata

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

            # 提取HarmonyOS技术术语
            for term, variations in self.HARMONYOS_TERMS.items():
                if any(v.lower() in context_text.lower() for v in variations):
                    if term not in query and not any(v in query for v in variations):
                        return f"{query} {term}"

        return query


# 单例
_query_expander_instance = None


def get_query_expander() -> QueryExpander:
    """获取查询扩展器单例"""
    global _query_expander_instance
    if _query_expander_instance is None:
        _query_expander_instance = QueryExpander()
    return _query_expander_instance

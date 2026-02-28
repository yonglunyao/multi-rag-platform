"""
RAG 准确率评估套件

用于评估 RAG 系统的检索准确率和回答质量
"""
import asyncio
import httpx
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class TestCase:
    """测试用例"""
    query: str
    expected_keywords: List[str]  # 期望在答案中出现的关键词
    expected_permissions: List[str]  # 期望的权限名称
    category: str  # 测试类别


class RAGAccuracyEvaluator:
    """RAG 准确率评估器"""

    # 测试用例集
    TEST_CASES = [
        TestCase(
            query="读剪贴板需要什么权限？",
            expected_keywords=["READ_PASTEBOARD", "剪贴板", "权限"],
            expected_permissions=["ohos.permission.READ_PASTEBOARD"],
            category="permission"
        ),
        TestCase(
            query="写剪贴板需要申请什么权限？",
            expected_keywords=["WRITE_PASTEBOARD", "剪贴板", "权限"],
            expected_permissions=["ohos.permission.WRITE_PASTEBOARD"],
            category="permission"
        ),
        TestCase(
            query="使用网络需要申请什么权限？",
            expected_keywords=["网络", "INTERNET", "getNetScroller"],
            expected_permissions=["ohos.permission.INTERNET"],
            category="permission"
        ),
        TestCase(
            query="UIAbility 的生命周期有哪些回调？",
            expected_keywords=["onCreate", "onStart", "onForeground", "onBackground", "onDestroy"],
            expected_permissions=[],
            category="lifecycle"
        ),
        TestCase(
            query="如何创建一个 UIAbility？",
            expected_keywords=["UIAbility", "AbilityStage", "onCreate"],
            expected_permissions=[],
            category="ability"
        ),
        TestCase(
            query="HarmonyOS 如何申请权限？",
            expected_keywords=["requestPermissionsFromUser", "AbilityContext", "user_grant"],
            expected_permissions=[],
            category="permission"
        ),
        TestCase(
            query="如何获取相机权限？",
            expected_keywords=["CAMERA", "相机"],
            expected_permissions=["ohos.permission.CAMERA"],
            category="permission"
        ),
        TestCase(
            query="如何获取位置权限？",
            expected_keywords=["LOCATION", "位置"],
            expected_permissions=["ohos.permission.APPROXIMATELY_LOCATION", "ohos.permission.LOCATION"],
            category="permission"
        ),
        TestCase(
            query="如何读取系统设置？",
            expected_keywords=["SYSTEM_SETTINGS", "设置"],
            expected_permissions=["ohos.permission.SYSTEM_SETTINGS"],
            category="permission"
        ),
        TestCase(
            query="Page 和 UIAbility 的区别是什么？",
            expected_keywords=["Page", "UIAbility", "窗口", "页面"],
            expected_permissions=[],
            category="concept"
        ),
    ]

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[Dict[str, Any]] = []

    async def evaluate_query(self, test_case: TestCase) -> Dict[str, Any]:
        """评估单个查询"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/query",
                json={"query": test_case.query, "context_length": 5}
            )

            if response.status_code != 200:
                return {
                    "query": test_case.query,
                    "category": test_case.category,
                    "error": f"HTTP {response.status_code}",
                    "answer": None,
                    "keyword_match": 0,
                    "permission_match": 0,
                }

            data = response.json()
            answer = data.get("answer", "")
            sources = data.get("sources", [])

            # 检查关键词匹配
            keyword_hits = sum(1 for kw in test_case.expected_keywords if kw in answer)
            keyword_match_score = keyword_hits / len(test_case.expected_keywords) if test_case.expected_keywords else 1.0

            # 检查权限名称匹配
            permission_hits = 0
            for perm in test_case.expected_permissions:
                if perm in answer:
                    permission_hits += 1

            # 检查是否有错误的权限名称（幻觉检测）
            has_hallucination = self._check_permission_hallucination(answer, test_case.expected_permissions)

            permission_match_score = permission_hits / len(test_case.expected_permissions) if test_case.expected_permissions else 1.0

            return {
                "query": test_case.query,
                "category": test_case.category,
                "answer": answer[:200] + "..." if len(answer) > 200 else answer,
                "sources_count": len(sources),
                "keyword_hits": keyword_hits,
                "keyword_total": len(test_case.expected_keywords),
                "keyword_score": round(keyword_match_score * 100, 1),
                "permission_hits": permission_hits,
                "permission_total": len(test_case.expected_permissions),
                "permission_score": round(permission_match_score * 100, 1),
                "has_hallucination": has_hallucination,
                "pass": keyword_match_score >= 0.5 and permission_match_score >= 0.5 and not has_hallucination,
            }

    def _check_permission_hallucination(self, answer: str, expected_permissions: List[str]) -> bool:
        """检查是否有权限名称幻觉"""
        import re

        # 提取答案中的所有权限名称
        permission_pattern = r'ohos\.permission\.[a-zA-Z_]+'
        found_permissions = set(re.findall(permission_pattern, answer))

        # 如果期望的权限列表为空，只检查是否有明显错误的权限
        if not expected_permissions:
            # 常见的错误权限名称（Android 等）
            wrong_patterns = [
                'android.permission',
                'READ_EXTERNAL_STORAGE',
                'WRITE_EXTERNAL_STORAGE',
                'ACCESS_FINE_LOCATION',
                'CAMERA',
                'INTERNET',
            ]
            return any(wrong in answer for wrong in wrong_patterns)

        # 检查是否有不在期望列表中的权限
        # 注意：这里我们允许一些额外的相关权限，但要检测明显错误的
        allowed_extra = {
            'ohos.permission.WRITE_PASTEBOARD',  # 如果问读权限，提到写权限也是相关的
            'ohos.permission.READ_PASTEBOARD',   # 反之亦然
        }
        for perm in found_permissions:
            if perm not in expected_permissions and perm not in allowed_extra:
                return True

        return False

    async def run_evaluation(self):
        """运行完整评估"""
        print("="*60)
        print("RAG 准确率评估测试")
        print("="*60)

        total = len(self.TEST_CASES)
        passed = 0
        failed = []

        results = []

        for i, test_case in enumerate(self.TEST_CASES, 1):
            print(f"\n[{i}/{total}] 测试: {test_case.query}")
            print(f"  类别: {test_case.category}")

            result = await self.evaluate_query(test_case)
            results.append(result)

            if result.get("error"):
                print(f"  ❌ 错误: {result['error']}")
                failed.append((test_case.query, "Error"))
            elif result["pass"]:
                print(f"  ✅ 通过")
                print(f"     关键词: {result['keyword_hits']}/{result['keyword_total']} ({result['keyword_score']}%)")
                print(f"     权限: {result['permission_hits']}/{result['permission_total']} ({result['permission_score']}%)")
                passed += 1
            else:
                print(f"  ❌ 未通过")
                print(f"     关键词: {result['keyword_hits']}/{result['keyword_total']} ({result['keyword_score']}%)")
                print(f"     权限: {result['permission_hits']}/{result['permission_total']} ({result['permission_score']}%)")
                if result.get("has_hallucination"):
                    print(f"     ⚠️  检测到权限名称幻觉！")
                print(f"     回答预览: {result.get('answer', 'N/A')[:100]}...")
                failed.append((test_case.query, "Failed"))

        self._print_summary(results, passed, total, failed)

    def _print_summary(self, results: List[Dict], passed: int, total: int, failed: List):
        """打印评估摘要"""
        print("\n" + "="*60)
        print("评估摘要")
        print("="*60)

        print(f"\n总测试用例: {total}")
        print(f"通过: {passed} ({passed/total*100:.1f}%)")
        print(f"失败: {len(failed)} ({len(failed)/total*100:.1f}%)")

        # 按类别统计
        categories = {}
        for r in results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0}
            categories[cat]["total"] += 1
            if r.get("pass"):
                categories[cat]["passed"] += 1

        print(f"\n按类别统计:")
        for cat, stats in categories.items():
            rate = stats["passed"] / stats["total"] * 100
            print(f"  {cat}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")

        # 平均得分
        avg_keyword_score = sum(r["keyword_score"] for r in results) / len(results)
        avg_permission_score = sum(r["permission_score"] for r in results) / len(results)

        print(f"\n平均得分:")
        print(f"  关键词匹配: {avg_keyword_score:.1f}%")
        print(f"  权限匹配: {avg_permission_score:.1f}%")

        if failed:
            print(f"\n失败的测试:")
            for query, reason in failed:
                print(f"  - {query} [{reason}]")

        print("="*60)

        # 保存详细结果
        self._save_results(results)

    def _save_results(self, results: List[Dict]):
        """保存测试结果到文件"""
        import json
        from datetime import datetime

        output = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(results),
            "passed": sum(1 for r in results if r.get("pass")),
            "results": results,
        }

        with open("test_results.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n详细结果已保存到: test_results.json")


async def main():
    """主函数"""
    evaluator = RAGAccuracyEvaluator()
    await evaluator.run_evaluation()


if __name__ == "__main__":
    asyncio.run(main())

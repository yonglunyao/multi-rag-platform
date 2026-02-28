"""
RAG API 基准测试脚本

不依赖 locust 的简单性能测试
"""
import asyncio
import time
import statistics
from typing import List, Dict, Any
import httpx
import json


class RAGBenchmark:
    """RAG API 基准测试"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[Dict[str, Any]] = []

    async def single_request(self, client: httpx.AsyncClient, endpoint: str, data: dict = None) -> Dict[str, Any]:
        """执行单个请求"""
        start_time = time.time()

        try:
            if data:
                response = await client.post(f"{self.base_url}{endpoint}", json=data, timeout=60.0)
            else:
                response = await client.get(f"{self.base_url}{endpoint}", timeout=10.0)

            elapsed = time.time() - start_time

            return {
                "endpoint": endpoint,
                "status_code": response.status_code,
                "response_time_ms": round(elapsed * 1000, 2),
                "success": response.status_code == 200,
                "response_length": len(response.content),
            }

        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "endpoint": endpoint,
                "status_code": 0,
                "response_time_ms": round(elapsed * 1000, 2),
                "success": False,
                "error": str(e),
            }

    async def run_concurrent_test(self, concurrency: int = 10, total_requests: int = 100):
        """运行并发测试"""
        print(f"\n{'='*50}")
        print(f"并发测试: {concurrency} 并发, {total_requests} 总请求")
        print(f"{'='*50}\n")

        test_queries = [
            {"query": "读剪贴板需要什么权限？", "context_length": 3},
            {"query": "UIAbility 的生命周期回调有哪些？", "context_length": 5},
            {"query": "如何申请网络权限？", "context_length": 3},
            {"query": "HarmonyOS 应用开发入门", "context_length": 5},
        ]

        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_request(client, query):
            async with semaphore:
                return await self.single_request(client, "/api/v1/query", query)

        start_time = time.time()

        async with httpx.AsyncClient() as client:
            tasks = []
            for i in range(total_requests):
                query = test_queries[i % len(test_queries)]
                tasks.append(bounded_request(client, query))

            self.results = await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # 统计结果
        self._print_statistics(total_time)

    def _print_statistics(self, total_time: float):
        """打印统计信息"""
        successful = [r for r in self.results if r["success"]]
        failed = [r for r in self.results if not r["success"]]

        response_times = [r["response_time_ms"] for r in successful]

        print(f"\n{'='*50}")
        print("测试结果")
        print(f"{'='*50}")
        print(f"总请求数: {len(self.results)}")
        print(f"成功: {len(successful)} ({len(successful)/len(self.results)*100:.1f}%)")
        print(f"失败: {len(failed)} ({len(failed)/len(self.results)*100:.1f}%)")
        print(f"\n总耗时: {total_time:.2f} 秒")
        print(f"吞吐量: {len(self.results)/total_time:.2f} RPS")
        print(f"\n响应时间统计 (仅成功请求):")
        if response_times:
            print(f"  平均: {statistics.mean(response_times):.2f} ms")
            print(f"  中位数: {statistics.median(response_times):.2f} ms")
            print(f"  最小: {min(response_times):.2f} ms")
            print(f"  最大: {max(response_times):.2f} ms")
            if len(response_times) > 1:
                print(f"  标准差: {statistics.stdev(response_times):.2f} ms")
            percentiles = [50, 90, 95, 99]
            for p in percentiles:
                value = statistics.quantiles(response_times, n=100)[p-1] if len(response_times) > 1 else response_times[0]
                print(f"  P{p}: {value:.2f} ms")

        # 错误统计
        if failed:
            print(f"\n错误详情:")
            error_counts = {}
            for r in failed:
                error = r.get("error", f"HTTP {r['status_code']}")
                error_counts[error] = error_counts.get(error, 0) + 1
            for error, count in error_counts.items():
                print(f"  {error}: {count}")

        print(f"{'='*50}\n")

    async def run_endpoints_test(self):
        """测试各端点性能"""
        print(f"\n{'='*50}")
        print("端点性能测试")
        print(f"{'='*50}\n")

        endpoints = [
            ("/api/v1/health", None, 20),
            ("/api/v1/documents/stats", None, 20),
            ("/api/v1/agent/search", {"query": "权限", "top_k": 5}, 10),
        ]

        all_results = []

        for endpoint, data, count in endpoints:
            print(f"测试: {endpoint}")
            results = []
            async with httpx.AsyncClient() as client:
                for _ in range(count):
                    result = await self.single_request(client, endpoint, data)
                    results.append(result["response_time_ms"])

            times = [r for r in results if r > 0]
            if times:
                print(f"  平均: {statistics.mean(times):.2f} ms")
                print(f"  中位数: {statistics.median(times):.2f} ms")
                print(f"  最小: {min(times):.2f} ms")
                print(f"  最大: {max(times):.2f} ms")
            print()

        print(f"{'='*50}\n")


async def main():
    """主函数"""
    benchmark = RAGBenchmark()

    # 测试健康检查
    print("检查服务状态...")
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/v1/health")
        if response.status_code != 200:
            print("错误: 服务不可用")
            return
        print(f"服务状态: {response.json()['status']}")

    # 运行端点测试
    await benchmark.run_endpoints_test()

    # 运行并发测试 (不同并发级别)
    for concurrency in [1, 5, 10]:
        await benchmark.run_concurrent_test(concurrency=concurrency, total_requests=50)


if __name__ == "__main__":
    asyncio.run(main())

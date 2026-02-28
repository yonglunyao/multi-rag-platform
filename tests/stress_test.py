"""
RAG API 性能压力测试

使用 locust 进行并发压力测试
运行方式: locust -f tests/stress_test.py --host=http://localhost:8000
"""
import time
import json
from locust import HttpUser, task, between, events


class RAGUser(HttpUser):
    """模拟 RAG API 用户"""

    wait_time = between(1, 3)  # 请求间隔 1-3 秒

    def on_start(self):
        """用户启动时执行"""
        # 先检查服务健康状态
        self.client.get("/api/v1/health")

    @task(3)
    def health_check(self):
        """健康检查（权重 3）"""
        with self.client.get("/api/v1/health", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    response.success()
                else:
                    response.failure(f"Unhealthy status: {data}")
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(2)
    def query_clipboard_permission(self):
        """查询剪贴板权限（权重 2）"""
        query_data = {
            "query": "读剪贴板需要什么权限？",
            "context_length": 3,
        }
        with self.client.post(
            "/api/v1/query",
            json=query_data,
            catch_response=True,
            timeout=30
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "answer" in data and "sources" in data:
                    # 检查答案是否包含正确的权限名称
                    if "ohos.permission.READ_PASTEBOARD" in data["answer"]:
                        response.success()
                    else:
                        response.failure("Incorrect permission in answer")
                else:
                    response.failure("Missing answer or sources")
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(1)
    def query_uiability(self):
        """查询 UIAbility（权重 1）"""
        query_data = {
            "query": "UIAbility 的生命周期回调有哪些？",
            "context_length": 5,
        }
        with self.client.post(
            "/api/v1/query",
            json=query_data,
            catch_response=True,
            timeout=30
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "answer" in data and len(data["sources"]) > 0:
                    response.success()
                else:
                    response.failure("Invalid response format")
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(1)
    def agent_search(self):
        """Agent 搜索接口（权重 1）"""
        query_data = {
            "query": "如何申请权限",
            "top_k": 3,
        }
        with self.client.post(
            "/api/v1/agent/search",
            json=query_data,
            catch_response=True,
            timeout=10
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "results" in data and len(data["results"]) > 0:
                    response.success()
                else:
                    response.failure("No results returned")
            else:
                response.failure(f"Status code: {response.status_code}")

    @task(1)
    def document_stats(self):
        """文档统计（权重 1）"""
        with self.client.get("/api/v1/documents/stats", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "total_documents" in data:
                    response.success()
                else:
                    response.failure("Missing total_documents")
            else:
                response.failure(f"Status code: {response.status_code}")


# 测试事件处理
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """记录请求事件"""
    if exception:
        print(f"Request failed: {name} - {exception}")
    elif response_time > 5000:  # 超过 5 秒警告
        print(f"Slow request: {name} - {response_time}ms")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时的统计"""
    print("\n" + "="*50)
    print("测试完成！统计信息：")
    print(f"总请求数: {environment.stats.total.num_requests}")
    print(f"失败请求数: {environment.stats.total.num_failures}")
    print(f"平均响应时间: {environment.stats.total.avg_response_time}ms")
    print(f"中位数响应时间: {environment.stats.total.median_response_time}ms")
    print(f"95分位响应时间: {environment.stats.total.get_response_time_percentile(0.95)}ms")
    print(f"RPS: {environment.stats.total.total_rps}")
    print("="*50)

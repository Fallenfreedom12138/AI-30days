import os
from tavily import TavilyClient

# 初始化 Tavily 客户端
api_key = os.getenv("TAVILY_API_KEY")
if api_key:
    tavily_client = TavilyClient(api_key=api_key)
else:
    tavily_client = None


def execute_web_search(query):
    """调用 Tavily 进行全网实时搜索"""
    if not tavily_client:
        return "错误：未配置 TAVILY_API_KEY，无法联网。"
    try:
        # 限制返回 3 条，提高速度
        response = tavily_client.search(query=query, search_depth="basic", max_results=3)
        results = response.get("results", [])

        if not results:
            return "未搜到相关最新信息。"

        text = "【全网实时检索结果】：\n"
        for i, r in enumerate(results):
            text += f"{i + 1}. 来源：{r.get('url', '')}\n标题：{r['title']}\n摘要：{r['content']}\n\n"
        return text
    except Exception as e:
        return f"搜索报错：{e}"
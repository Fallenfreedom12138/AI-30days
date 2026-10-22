import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# 1. 加载环境变量并初始化客户端
load_dotenv()
client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)

# 2. 定义工具列表 (注意：这里原封不动复制之前的)
tools = [
    {
        "type": "function",
        "function": {
            "name": "filter_data",
            "description": "根据数值条件遍历筛选品牌数据。比如找同比下滑的品牌、找抽成大于20万的品牌。",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {
                        "type": "string",
                        "description": "要筛选的列名，例如 '营业额同比' 或 '抽成'"
                    },
                    "operator": {
                        "type": "string",
                        "enum": ["<", ">", "=="],
                        "description": "比较运算符"
                    },
                    "value": {
                        "type": "number",
                        "description": "用于比较的数值"
                    }
                },
                "required": ["column", "operator", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_trend",
            "description": "在文档段落中查找特定品牌的背景、原因、后续措施，并给出诊断分析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_name": {
                        "type": "string",
                        "description": "要分析的品牌名称，例如 'FILA'"
                    },
                    "question": {
                        "type": "string",
                        "description": "具体要分析的问题，例如 '为什么下滑'"
                    }
                },
                "required": ["brand_name", "question"]
            }
        }
    }
]

# 3. 用户输入
user_input = input("请提问（例如：帮我找一下有没有抽成大于20万的品牌）：")

# 4. 发起带 tools 的请求
print("\n正在请求大模型分析意图...")
response = client.chat.completions.create(
    model=os.getenv("MODEL_NAME"),
    messages=[{"role": "user", "content": user_input}],
    tools=tools
)

# 5. 查看并解析模型的返回
message = response.choices[0].message

if message.tool_calls:
    # 模型决定调用工具
    tool_call = message.tool_calls[0]
    function_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments)

    print(f"\n--- 模型决定调用工具 ---")
    print(f"工具名: {function_name}")
    print(f"提取的参数: {arguments}")
    print(f"列名: {arguments['column']} | 比较符: {arguments['operator']} | 阈值: {arguments['value']}")
else:
    # 模型决定直接回答
    print(f"\n--- 模型直接回答 ---")
    print(message.content)


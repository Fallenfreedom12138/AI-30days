import os
import json
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# 🌟 引入我们自己写的模块
from rag_service import init_rag, search_docs

load_dotenv()
client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)

EXCEL_PATH = r"C:\Users\40321\PycharmProjects\pythonProject6\docs"
EXCEL_FILE = r"C:\Users\40321\PycharmProjects\pythonProject6\docs\brands.xlsx"
# 如果你这里 EXCEL_PATH 是指向 brands.xlsx 具体文件，请改传所在文件夹
# 因为 rag_service 里的 load_document 是用 glob 匹配文件夹的

# 启动时，初始化 RAG
init_rag(EXCEL_PATH)

# ================= 3. 定义工具 =================
tools = [
    {
        "type": "function",
        "function": {
            "name": "filter_data",
            "description": "根据多个数值条件筛选品牌数据。注意：数据库里的营业额和抽成单位均为'元'（比如30万要传300000）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "conditions": {
                        "type": "array",
                        "description": "筛选条件列表，可以包含多个条件",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string", "description": "列名，如'营业额','抽成'"},
                                "operator": {"type": "string", "enum": ["<", ">", "=="]},
                                "value": {"type": "number", "description": "数值阈值"}
                            },
                            "required": ["column", "operator", "value"]
                        }
                    }
                },
                "required": ["conditions"]
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
                    "brand_name": {"type": "string", "description": "要分析的品牌名称，例如 'FILA'"},
                    "question": {"type": "string", "description": "具体要分析的问题，例如 '为什么下滑'"}
                },
                "required": ["brand_name", "question"]
            }
        }
    }
]


# ================= 4. 定义本地执行函数 =================
def execute_filter_data(conditions):
    # 这里用 EXCEL_FILE（文件绝对路径），不要用 DOCS_DIR
    if not os.path.exists(EXCEL_FILE):
        return "找不到数据库文件。"

    df = pd.read_excel(EXCEL_FILE)

    for cond in conditions:
        col = cond["column"]
        op = cond["operator"]
        val = cond["value"]

        if col not in df.columns:
            return f"错误：表格中不存在列名 '{col}'。"

        if op == ">":
            df = df[df[col] > val]
        elif op == "<":
            df = df[df[col] < val]
        elif op == "==":
            df = df[df[col] == val]

    if df.empty: return "没有找到符合条件的品牌。"

    result_text = "符合条件的品牌有：\n"
    for _, row in df.head(10).iterrows():
        result_text += f"- {row['品牌']}：营业额 {row['营业额']}，抽成 {row['抽成']}\n"
    if len(df) > 10:
        result_text += f"...等共 {len(df)} 个品牌。"
    return result_text


# ================= 5. Agent 主循环 =================
messages = [
    {"role": "system", "content": "你是一个商业地产数据分析助手多多，你可以查询数据，也可以分析文档。"}
]

print("\n" + "=" * 40)
print("🤖 商业地产智能 Agent 多多 已启动")
print("输入 /clear 清空对话历史")
print("输入 /exit 退出程序")
print("=" * 40)

while True:
    # 1. 外层：接收用户输入
    user_input = input("\n你：")

    if user_input == "/exit":
        print("再见！")
        break

    if user_input == "/clear":
        messages = [{"role": "system", "content": "你是一个商业地产数据分析助手多多，你可以查询数据，也可以分析文档。"}]
        print("🧹 对话历史已清空")
        continue

    if user_input == "":
        continue

    # 把用户的话加入历史
    messages.append({"role": "user", "content": user_input})

    # 2. 内层：Agent 的思考与行动循环
    while True:
        response = client.chat.completions.create(
            model=os.getenv("MODEL_NAME"),
            messages=messages,
            tools=tools
        )

        message = response.choices[0].message
        messages.append(message)

        # 如果不需要调工具，说明本轮结束，跳出内层循环，等待用户下一次输入
        if not message.tool_calls:
            print(f"\n🤖 Agent：{message.content}")
            break

            # 如果需要调工具，执行工具
        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            print(f"\n[Agent 后台运行]：调用工具 {function_name}...")

            try:
                if function_name == "filter_data":
                    tool_result = execute_filter_data(**arguments)
                elif function_name == "analyze_trend":
                    tool_result = execute_analyze_trend(**arguments)
                else:
                    tool_result = "没有找到该工具"
            except Exception as e:
                tool_result = f"工具执行报错：{str(e)}。"

            # 把工具结果追加到历史中
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": tool_result
            })
            # 内层循环会继续，模型看到结果后会决定是继续调工具，还是输出最终回答
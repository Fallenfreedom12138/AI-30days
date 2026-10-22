import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import json
import faiss
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ================= 1. 初始化与全局路径 =================
load_dotenv()
client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)

# 🚨 核心：统一这里的数据路径！确保文件真实存在！
EXCEL_PATH = r"C:\Users\40321\PycharmProjects\pythonProject6\week 2\docs\brands.xlsx"

print("正在加载嵌入模型...")
model = SentenceTransformer("BAAI/bge-base-zh-v1.5")


# ================= 2. 构建 RAG 索引 =================
def load_document(file_path):
    documents = []
    if not os.path.exists(file_path):
        print(f"❌ 找不到文件：{file_path}")
        return documents

    df = pd.read_excel(file_path)
    for _, row in df.iterrows():
        parts = []
        for col in df.columns:
            parts.append(f'{col}:{row[col]}')
        text = "，".join(parts)
        documents.append({"content": text, "source": "brands.xlsx"})
    return documents


def split_documents(documents):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    all_chunks = []
    for doc in documents:
        chunks = text_splitter.split_text(doc["content"])
        for chunk in chunks:
            all_chunks.append({"text": chunk, "source": doc["source"]})
    return all_chunks


print("正在读取文档并建立向量索引...")
docs = load_document(EXCEL_PATH)
chunks = split_documents(docs)

if len(chunks) > 0:
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts)
    vectors = np.array(embeddings).astype("float32")
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)
    print(f"✅ 索引建立完成，共 {index.ntotal} 个块！")
else:
    print("⚠️ 警告：没有读取到任何文本，RAG功能将不可用！")

# ================= 3. 定义工具 =================
tools = [
    {
        "type": "function",
        "function": {
            "name": "filter_data",
            "description": "根据数值条件筛选品牌数据。注意：数据库里的营业额和抽成单位均为'元'（比如20万要传200000）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string", "description": "列名，如'营业额','抽成','营业额同比'"},
                    "operator": {"type": "string", "enum": ["<", ">", "=="]},
                    "value": {"type": "number", "description": "数值阈值"}
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
                    "brand_name": {"type": "string", "description": "要分析的品牌名称，例如 'FILA'"},
                    "question": {"type": "string", "description": "具体要分析的问题，例如 '为什么下滑'"}
                },
                "required": ["brand_name", "question"]
            }
        }
    }
]


# ================= 4. 定义本地执行函数 =================
def execute_filter_data(column, operator, value):
    if not os.path.exists(EXCEL_PATH):
        return "找不到数据库文件。"
    df = pd.read_excel(EXCEL_PATH)

    if operator == ">":
        result_df = df[df[column] > value]
    elif operator == "<":
        result_df = df[df[column] < value]
    elif operator == "==":
        result_df = df[df[column] == value]
    else:
        return "不支持的运算符"

    if result_df.empty: return f"没有找到 {column} {operator} {value} 的品牌。"

    result_text = "符合条件的品牌有：\n"
    for _, row in result_df.head(10).iterrows():  # 截取前10个防撑爆
        result_text += f"- {row['品牌']}：{column}为 {row[column]}\n"
    if len(result_df) > 10:
        result_text += f"...等共 {len(result_df)} 个品牌。"
    return result_text


def execute_analyze_trend(brand_name, question):
    if len(chunks) == 0: return "本地文档库为空，无法分析。"

    query = f"{brand_name} {question}"
    query_vector = model.encode(query).astype("float32").reshape(1, -1)
    distances, indices = index.search(query_vector, k=3)
    retrieved_chunks = [chunks[idx]["text"] for idx in indices[0]]
    context = "\n\n".join(retrieved_chunks)

    response = client.chat.completions.create(
        model=os.getenv("MODEL_NAME"),
        messages=[
            {"role": "system", "content": "你是一名商业地产分析师，只根据资料回答问题。如果资料中没有，请说'未提及'。"},
            {"role": "user", "content": f"资料：\n{context}\n\n问题：{question}"}
        ]
    )
    return response.choices[0].message.content


# ================= 5. Agent 主循环 =================
user_input = input("请提问：")
messages = [{"role": "user", "content": user_input}]

while True:
    response = client.chat.completions.create(
        model=os.getenv("MODEL_NAME"),
        messages=messages,
        tools=tools
    )

    message = response.choices[0].message
    messages.append(message)

    # 模型不再调工具，输出最终答案
    if not message.tool_calls:
        print("\n--- 最终回答 ---")
        print(message.content)
        break

    # 模型要求调工具
    for tool_call in message.tool_calls:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        print(f"\n[Agent 调用工具]：{function_name}，参数：{arguments}")

        if function_name == "filter_data":
            tool_result = execute_filter_data(**arguments)
        elif function_name == "analyze_trend":
            tool_result = execute_analyze_trend(**arguments)
        else:
            tool_result = "没有找到该工具"

        print(f"[本地执行结果]：{tool_result[:150]}...\n")

        # 将结果追加到 messages 里，循环继续
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": function_name,
            "content": tool_result
        })
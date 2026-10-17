import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from openai import OpenAI

def load_document(folder_path):
    documents = []

    # 读 excel
    for file in Path(folder_path).glob("*.xlsx"):
        df = pd.read_excel(file)

        for _, row in df.iterrows():
            parts = []
            for col in df.columns:
                value = row[col]
                if col in ["营业额同比", "抽成同比"]:
                    value = f'{value * 100:.1f}%'
                if col in ["营业额", "抽成"]:
                    value= f'{value:.2f}元'
                parts.append(f'{col}:{value}')
            text = "，".join(parts)
            documents.append({
                "content": text,
                "source": file.name
            })
    return documents


# for d in docs:
# print(f"来源：{d['source']}")
# print(f"内容：{d['content']}")
# print()

def split_documents(documents, chunk_size=500, chunk_overlap=50):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
    )

    all_chunks = []
    for doc in documents:
        chunks = text_splitter.split_text(doc["content"])
        for chunk in chunks:
            all_chunks.append({
                "text": chunk,
                "source": doc["source"]
            })
    return all_chunks


docs = load_document("docs/")
chunks = split_documents(docs)

print(f'共{len(chunks)}个块\n')
for i, c in enumerate(chunks):
    print(f'=====块{i + 1}({len(c["text"])}字)=====')
    print(f'来源{c["source"]}')
    print(c["text"])
    print()

# 加载模型
print("="*60)
print("加载模型")
print("="*60)

model=SentenceTransformer("BAAI/bge-base-zh-v1.5")
print("模型加载完成")

#转成向量
texts=[c["text"]for c in chunks]
embeddings=model.encode(texts)
print(f'向量形状：{embeddings.shape}')

vectors=np.array(embeddings).astype("float32")

#建立索引
index=faiss.IndexFlatL2(vectors.shape[1])
index.add(vectors)
print(f'索引建立完成，共{index.ntotal}个向量\n')

#---LLM客户端
load_dotenv()
client=OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)

# RAG 函数

SYSTEM_PROMPT="你是一名商业地产分析师，只根据提供的上下文回答问题。没有相关信息就说'资料中未提及'。"

def search(query, chunks, index, model, k=3):
    query_vectors=model.encode(query).astype("float32").reshape(1,-1)
    distances, indices=index.search(query_vectors,k)
    results=[]
    for i,idx in enumerate(indices[0]):
        results.append({
            "text":chunks[idx]["text"],
            "source":chunks[idx]["source"],
            "distance": float(distances[0][i])
             })
    return results

def build_rag_prompt(query, retrieved):
    context_parts=[]
    for i, item in enumerate(retrieved):
        context_parts.append(f'---资料{i+1}(来自：{item["source"]})---\n{item["text"]}')
    context= "\n\n".join(context_parts)
    return f"""以下是资料：F
    {context}
    
    请根据以上资料回答{query}
    """
def ask_rag(query):
    retrieved=search(query,chunks,index,model)
    prompt=build_rag_prompt(query,retrieved)
    messages=[
        {"role":"system","content":SYSTEM_PROMPT},
        {"role":"user","content":prompt}
    ]
    response=client.chat.completions.create(
        model=os.getenv("MODEL_NAME"),
        messages=messages
    )
    return response.choices[0].message.content
# 交互式问答
print("="*60)
print(f'交互式问答')
print("="*60)

while True:
    user_input=input("你：")
    if user_input=="":
        print(f"请重新输入")
        continue
    if user_input=="/exit":
        break
    answer=ask_rag(user_input)
    print(f"回答：{answer}")

import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import faiss
import numpy as np
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 让模型、chunks和index变成全局变量，供外面调用
model = None
chunks = []
index = None


def load_document(folder_path):
    documents = []
    for file in Path(folder_path).glob("*.xlsx"):
        df = pd.read_excel(file)
        for _, row in df.iterrows():
            parts = []
            for col in df.columns:
                parts.append(f'{col}:{row[col]}')
            text = "，".join(parts)
            documents.append({"content": text, "source": file.name})
    return documents


def split_documents(documents):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    all_chunks = []
    for doc in documents:
        texts = text_splitter.split_text(doc["content"])
        for t in texts:
            all_chunks.append({"text": t, "source": doc["source"]})
    return all_chunks


def init_rag(folder_path):
    """初始化 RAG 系统：加载模型、读文档、建索引"""
    global model, chunks, index
    print("正在加载嵌入模型...")
    model = SentenceTransformer("BAAI/bge-base-zh-v1.5")

    print("正在读取文档并建立向量索引...")
    docs = load_document(folder_path)
    chunks = split_documents(docs)

    if len(chunks) > 0:
        texts = [c["text"] for c in chunks]
        embeddings = model.encode(texts)
        vectors = np.array(embeddings).astype("float32")
        index = faiss.IndexFlatL2(vectors.shape[1])
        index.add(vectors)
        print(f"✅ 索引建立完成，共 {index.ntotal} 个块！")
    else:
        print("⚠️ 警告：没有读取到任何文本！")


def search_docs(query, k=3):
    """提供给外部调用的检索函数"""
    if index is None or len(chunks) == 0:
        return "本地文档库为空，无法检索。"

    query_vector = model.encode(query).astype("float32").reshape(1, -1)
    distances, indices = index.search(query_vector, k)

    results = []
    for i, idx in enumerate(indices[0]):
        results.append(chunks[idx]["text"])
    return "\n\n".join(results)
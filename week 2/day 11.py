import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-base-zh-v1.5")

texts = [
     "客单价下降",
    "产品价格下降",
    "今天天气很好"
]
embeddings = model.encode(texts)
print(embeddings.shape)# (3, 768)

vectors=np.array(embeddings).astype("float32")
dimension=vectors.shape[1]

index=faiss.IndexFlatL2(dimension)
index.add(vectors)

query = "客人消费下降"
query_embedding = model.encode(query).astype('float32').reshape(1,-1)

distances, indices = index.search(query_embedding, k=3)

print(f'\nquery:{query}\n')
for i, idx in enumerate(indices[0]):
    print(f'第{i+1}相似:{texts[idx]}')
    print(f'距离：{distances[0][i]:.4f}')
    print()

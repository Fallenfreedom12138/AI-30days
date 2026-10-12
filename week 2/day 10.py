import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from sentence_transformers import SentenceTransformer
from sentence_transformers import util

model = SentenceTransformer("BAAI/bge-base-zh-v1.5")

texts = [
     "客单价下降",
    "每位顾客平均消费减少",
    "今天天气很好"
]
embeddings = model.encode(texts)
print(embeddings.shape)# (3, 512)

query = "耐克销售下降"
query_embedding = model.encode(query)

similarities = util.cos_sim(query_embedding, embeddings)

scores=util.cos_sim(embeddings,embeddings)
print(f'{scores}')

for i in range(len(texts)):
    for j in range(i+1,len(texts)):
        print(f'{texts[i]} vs {texts[j]}:{scores[i][j]:.4f}')


print(similarities)

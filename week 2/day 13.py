#配置环境
import os
os.environ["HF_ENDPOINT"]="https://hf-mirror.com"

#导入库
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from  dotenv import load_dotenv

load_dotenv()
client=OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)


# 准备原始文档
document="""1、整体取高：本期93家/抽成383.25万/营业额16998.62万，同比同期84家/347.05万/16737.59万。品牌数+9家（+10.7%），营业额+1.6%（+261.03万）而抽成+10.4%（+36.20万），主要原因：① 新进品牌（共计27个品牌，涉及金额104.4万）：几勺、大疆、SALOMON 等；② 品牌翻新或移位调整后提升（共计8个品牌，涉及金额48.5万），全新固租下降+扣点上升，如FILA：抽成临界值 96.7万→26.1万、抽成比例10%→12%，抽成收入+15.52w；滨寿司：抽成临界值82万→78.7万、抽成比例11%→11.5%，营业额因翻新期损失195万但总体抽成仍+4.17w；其他翻新移位品牌：爱婴室、balabala、争鲜等；③ 营业额提升增量（共计30个品牌，涉及金额51.8万）：如布歌（营业额提升296w，抽成+16.4w）、大米先生（营业额提升120w，抽成+4.3w）、林清轩（营业额提升57.7w，抽成+4.3w）

2、稳定达抽：本期每月达抽品牌10家/抽成共计154.40万/营业额共计5031.22万，同期7家/抽成97.34万/营业额3376.50万，品牌数+3、抽成+58.6%。① 本期每月稳定达抽品牌：大米先生(抽32.93/营722.28)、泡泡玛特(抽21.26/营1016.43）、布歌(抽19.52/营379.65)、小杨生煎(21.88/492.85)、FILA(17.73/355.57)、新发现(17.95/1144.30)、大疆(18.39/891.96)、SALOMON(10.84/328.73)、江南布衣(10.62/180.97)、CLMX(7.36/202.17)；② 两年每月均达抽品牌2家：小杨生煎、新发现；③ 本期较同期新增稳定抽成品牌：大米先生、泡泡玛特、布歌、FILA、大疆、SALOMON、江南布衣、CLMX；同期每月达抽而本期仅部分月份达抽的品牌：左庭右院、霸王茶姬、西贝、老乡鸡、欢囍花生，以上需重点关注。其中老乡鸡本期仅3个月达抽、抽成仅0.7万，较同期10.7万下降93.6%、降幅最大；西贝、霸王茶姬本期未再达抽。

3、可同比品牌：数量共计41家，本期抽成262.89万/同期234.19万，同比+12.3%（+28.70万）；可同比品牌抽成占比由同期2.02%提升至本期2.68%。其中，抽成增长品牌18家、下降品牌23家。抽成增长较多品牌：FILA（+16.64，17.66 vs 1.01）、布歌（+16.4，20.6 vs 4.1）、大米先生（+4.3，27.6 vs 23.3）、滨寿司（+9.64，17.92 vs 8.28）、林清轩（+4.3，10.7 vs 5.6）等；抽成下降较多品牌：① 固租提升，营业额降低：老乡鸡 -9.61万、了岚 -3.8万；② 营业额下降：新发现 -8.8万、西塔老太太 -3.3万；③ 营业额提升，同时固租提升：泡泡玛特 -5.8万（计租方式变化导致，全品类抽成10%→分品类抽成）；

4、新增/撤铺品牌：新增达抽46家，新增抽成合计132.36万，为本期主要增量（其中26年新开/新进27家贡献104.4万）：几勺（19.02）、大疆（18.27）、SALOMON（10.82）、柳真真（10.79）、江南布衣（10.59）、CLMX（7.36）等。撤铺13家，较同期损失抽成43.93万：琦王（17.52）、Colorlab by Watsons（14.12）、海澜之家（2.95）、彪马（1.91）、LESS IS MORE（0.98）等。

5、后续措施：重点跟进稳定达抽（10家，抽成177.46万）与可同比高增长品牌（FILA、布歌、大米先生、滨寿司等），持续提升营业额带来增量；对老乡鸡、新发现、西塔老太太、了岚等下滑品牌，以及左庭右院、霸王茶姬、欢囍花生等同期稳定达抽而本期抽成降级品牌，开展重点监控及进行业绩帮扶。"""

#文本分割
print("="*60)
print("第二步:文本分割")
print("="*60)

text_splitter=RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
)

chunks=text_splitter.split_text(document)
last_chunk=chunks[-1]
if "5、后续措施" in last_chunk:
    parts=last_chunk.split("5、后续措施",1)
    chunks[-1]=parts[0].strip()
    chunks.append("5、后续措施"+parts[1])

print(f'分割成{len(chunks)}个块\n')
for i,chunk in enumerate(chunks):
    print(f'-----块{i+1}({len(chunk)}字-----')
    print(chunk)
    print()

#加载模型
print("="*60)
print("第三步:加载模型")
print("="*60)

model=SentenceTransformer("BAAI/bge-base-zh-v1.5")
print("模型加载完成\n")

#转变向量

print("="*60)
print("第四步:转变向量")
print("="*60)

embeddings= model.encode(chunks)
print(f'向量形状：{embeddings.shape}\n')

vectors=np.array(embeddings).astype('float32')
dimension=vectors.shape[1]

#faiss 索引
print("="*60)
print("第五步:建立FAISS索引")
print("="*60)

index=faiss.IndexFlatL2(dimension)
index.add(vectors)
print(f'索引建立完成，共{index.ntotal}个向量\n')

# day 13 RAG

SYSTEM_PROMPT="""你是商业地产数据分析师,名字叫多多。如果上下文中没有相关信息，回答"资料中未提及"。不要凭记忆补充。"""

def build_rag_prompt(query,retrieved_chunks):
    context_parts=[]
    for i, chunk in enumerate(retrieved_chunks):
        context_parts.append(f"---资料{i+1}---\n{chunk}")
    context="\n\n".join(context_parts)
    return f"""以下是资料:

{context}
    
请根据以上资料回答{query}"""

def ask_rag(query):
    #1. 检索
    query_vector= model.encode(query).astype("float32").reshape(1,-1)
    distance, indices=index.search(query_vector,k=3)
    retrieved_chunks=[chunks[idx] for idx in indices[0]]

    #2. 构造
    prompt= build_rag_prompt(query,retrieved_chunks)

    #3. 调用LLM
    messages=[
        {"role":"system","content":SYSTEM_PROMPT},
        {"role":"user","content":prompt}
    ]

    response=client.chat.completions.create(
        model=os.getenv("MODEL_NAME"),
        messages=messages
    )

    return response.choices[0].message.content

#交互式问答
print("=" * 60)
print("第六步：RAG 问答")
print("=" * 60)

while True:
    query=input("\n你的问题（输入 /exit 退出）：")

    if query=="/exit":
        break

    if query=="":
        print(f'请重新输入')
        continue

    answer=ask_rag(query)
    print(f'\n回答：{answer}')

    log_path=os.path.join(os.path.dirname(__file__),"chat_log.txt")
    with open(log_path, 'a', encoding="utf-8") as f:
        f.write(f'用户：{query}\n')
        f.write(f'多多：{answer}\n\n')

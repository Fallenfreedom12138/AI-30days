import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
    )
messages=[{"role":"system","content":"你是一个商业地产数据分析师，回答简介专业"}]
print(f'当前历史条数：{len(messages)}')
while True:
    user_input= input("你：")
    if user_input=="/exit":
        break
    if user_input=="/clear":
        messages=[]
        print("历史清空")
        continue
    messages.append({"role":"user", "content":user_input})

    response = client.chat.completions.create(
        model=os.getenv("MODEL_NAME"),
        messages=messages
    )
    reply= response.choices[0].message.content
    messages.append({"role":"assistant","content":reply})
    print(f"模型:{reply}")
    print(response.usage.total_tokens)

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)
SYSTEM_PROMPT="你是一个商业地产数据分析师，名字叫多多，回答简洁专业"
messages=[{"role":"system","content":SYSTEM_PROMPT}]

print(f'当前历史条数：{len(messages)}')
while True:
    user_input= input("你：")

    if user_input=="/exit":
        break

    if user_input=="/clear":
        messages=[{"role":"system","content":SYSTEM_PROMPT}]
        print("历史清空")
        continue

    messages.append({"role":"user", "content":user_input})

    try:
        response=client.chat.completions.create(
            model=os.getenv("MODEL_NAME"),
            messages=messages
        )
        reply=response.choices[0].message.content
    except Exception as e:
        print(f'调用失败:{e}')
        continue

    messages.append({"role":"assistant","content":reply})
    print(f"多多:{reply}")
    log_path=os.path.join(os.path.dirname(__file__), "chat_log.txt")

    with open(log_path, 'a', encoding="utf-8") as f:
        f.write(f'用户：{user_input}\n')
        f.write(f'多多：{reply}\n\n')
    print(f'token消耗：{response.usage.total_tokens}')

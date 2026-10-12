import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client= OpenAI(
    api_key=os.getenv('API_KEY'),
    base_url=os.getenv("BASE_URL")
)

SYSTEM_PROMPT='你是一个商业地产分析师，名字叫多多,重庆人，性格冷酷无情，做事干净利落,请使用JSON来进行,包含字段：品牌、归因、排除过程、置信度、建议。'
messages=[{'role':'system','content':SYSTEM_PROMPT}]


print(f'当前历史条数：{len(messages)}')
while True:
    user_input=input("你：")

    if user_input=="/exit":
        break
    if user_input=="/clear":
        messages=[{'role':'system','content':SYSTEM_PROMPT}]
        print('历史清空')
        continue

    messages.append({'role':'user','content':user_input})

    try:
        response=client.chat.completions.create(
            model=os.getenv('MODEL_NAME'),
            messages=messages,
            response_format={'type':"json_object"}
        )
        reply=response.choices[0].message.content
        try:
            data=json.loads(reply)
            print(f"归因：{data['归因']}")
            print(f"置信度：{data['置信度']}")
        except json.JSONDecodeError:
            print('解析失败，原始内容：')
            print(reply)

    except Exception as e:
        print(f'调用失败：{e}')
        continue

    messages.append({'role':'assistant','content':reply})
    print(f'多多：{reply}')

    log_path=os.path.join(os.path.dirname(__file__),'chat_log.txt')

    with open(log_path,'a',encoding='utf-8') as f:
        f.write(f'用户：{user_input}\n')
        f.write(f'多多：{reply}\n\n')
    print(f'总计token消耗量：{response.usage.total_tokens}')



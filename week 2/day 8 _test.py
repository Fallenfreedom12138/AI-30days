import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)

messages = [
    {"role": "system", "content": "你是商业地产数据分析师。直接分析数据，不要自我介绍，不要反问。"},
    {"role": "user", "content": "品牌A：同比-18%，同业态-3%，人员变动=1，货品正常，施工=0。请归因。"}
]

response = client.chat.completions.create(
    model=os.getenv("MODEL_NAME"),
    messages=messages
)

print(response.choices[0].message.content)
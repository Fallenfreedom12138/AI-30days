import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)

response = client.chat.completions.create(
    model=os.getenv("MODEL_NAME"),
    messages=[
        {"role": "user", "content": "用一句话解释什么是商业地产的客单价"}
    ]
)
print(response)
print(response.choices[0].message.content)
print(response.usage.total_tokens)
 
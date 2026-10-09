import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client=OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("BASE_URL")
)
def ask(label, system_prompt, user_message):
    messages= [
        {"role":'system', 'content':system_prompt},
        {'role':'user','content':user_message}
    ]
    response= client.chat.completions.create(
        model=os.getenv('MODEL_NAME'),
        messages=messages
    )
    reply=response.choices[0].message.content

    with open('day8_result.txt','a',encoding='utf-8') as f:
        f.write(f'==={label}===\n')
        f.write(reply)
        f.write('\n\n')
    print(f'{label}完成')
    print(f'本次消耗：{response.usage.total_tokens}')
# 第一组
ask(
    "zero_shot",
    """你是商业地产数据分析师。任务是：根据用户提供的品牌数据，直接输出归因分析。
输出格式：归因结论 + 排除过程。不要自我介绍，不要反问。""",
    "请分析：品牌A，同比-18%，同业态-3%，人员变动=1，货品正常，施工=0。分析下滑原因。"
)
# 第二组
ask(
    'few_shot',
    "你是商业地产数据分析师，按示例格式输出归因分析。",
     """品牌X：同比-10%，同业态-9%，人员=0，货品=0，施工=0
归因：共性问题。同业态-9%接近品牌-10%，商场整体下滑。

现在请分析：品牌A：同比-18%，同业态-3%，人员变动=1，货品正常，施工=0"""
)

# 第三组
ask(
    'COT',
    "你是商业地产数据分析师。",
    """品牌A：同比-18%，同业态-3%，人员变动=1，货品正常，施工=0。

请严格按以下步骤分析，不要自我介绍：
第一步：同业态对比，判断共性问题还是个体问题
第二步：检查人员、货品、动线
第三步：给出归因结论

先输出推理，再输出结论。"""
)
print()


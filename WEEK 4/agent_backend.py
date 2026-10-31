import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import json
import glob # 👈 确保文件最上面有 import glob
import re
import argparse  # 👈 确保这里导入了
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient

# 👇 引入底层引擎
from report_engine import build_report, render_html, get_core_summary_for_ai

load_dotenv()
client = OpenAI(api_key=os.getenv("API_KEY"), base_url=os.getenv("BASE_URL"))

tavily_api_key = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=tavily_api_key) if tavily_api_key else None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULE_FILE = os.path.join(BASE_DIR, "docs", "management_rules.txt")
HISTORY_DIR = os.path.join(BASE_DIR, "docs", "history") # 👈 历史记录路径
os.makedirs(HISTORY_DIR, exist_ok=True)


# 👇 新增：读取上一次的洞察报告
def load_previous_insight():
    """读取上一次的洞察报告（按时间倒序找最近的一期）"""
    files = glob.glob(os.path.join(HISTORY_DIR, "*_运营洞察.md"))
    if not files:
        return "无历史报告记录（这是系统首次生成或清空了记录）。"

    files.sort(reverse=True)
    latest_file = files[0]

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            content = f.read()
            return f"【上一次历史报告（{os.path.basename(latest_file)}）】\n{content}"
    except Exception as e:
        return f"读取历史记录失败: {e}"


# 👇 新增：保存报告
def save_insight_to_history(year, month, content, intervention="无"):
    filename = f"{year}年{month:02d}月_运营洞察.md"
    filepath = os.path.join(HISTORY_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"### 本月干预举措记录：\n{intervention}\n\n---\n\n")
            f.write(content)
    except Exception as e:
        print(f"保存历史记录失败: {e}")
# ================= 1. 底层数据桥接 =================
def generate_report_backend(year, month, target):
    DATA_DIR = os.path.join(BASE_DIR, "data_storage")
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    yoy_y, yoy_m = year - 1, month

    cur_file = os.path.join(DATA_DIR, f"{year}年{month}月.xlsx")
    prev_file = os.path.join(DATA_DIR, f"{prev_y}年{prev_m}月.xlsx")
    yoy_file = os.path.join(DATA_DIR, f"{yoy_y}年{yoy_m}月.xlsx")

    missing = []
    if not os.path.exists(cur_file): missing.append(f"{year}年{month}月")
    if not os.path.exists(prev_file): missing.append(f"{prev_y}年{prev_m}月(环比)")
    if not os.path.exists(yoy_file): missing.append(f"{yoy_y}年{yoy_m}月(同比)")

    if missing:
        return None, f"❌ 缺数据，请先上传：{', '.join(missing)}。当前路径：{DATA_DIR}"

    # 👇 构造参数，确保所有变量都不缺失
    args = argparse.Namespace(
        year=year, month=month, project='',
        cur_file=cur_file, prev_file=prev_file, yoy_file=yoy_file,
        prev_ym=(prev_y, prev_m), yoy_ym=(yoy_y, yoy_m),
        target=target, normalize=True, daily_avg=True,
        exclude_dates=[], boost=[], boost_name='促销日',
        comm_file=None, increment=None
    )

    try:
        r = build_report(args)
        summary = get_core_summary_for_ai(r)
        html = render_html(r, args)
        return html, summary
    except Exception as e:
        return None, f"引擎报错：{e}"


# ================= 2. 工具函数 =================
def get_expert_rules():
    try:
        with open(RULE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "未找到业务规则库。"


def execute_web_search(query):
    if not tavily_client: return "未配置 TAVILY_API_KEY。"
    try:
        response = tavily_client.search(query=query, search_depth="basic", max_results=3, timeout=15)
        results = response.get("results", [])
        if not results: return "未搜到相关最新信息。"
        text = "【全网实时检索结果】：\n"
        for i, r in enumerate(results):
            text += f"{i + 1}. 标题：{r['title']}\n摘要：{r['content']}\n\n"
        return text
    except Exception as e:
        return f"搜索报错：{e}"


def execute_update_rule_book(new_rule):
    try:
        os.makedirs(os.path.dirname(RULE_FILE), exist_ok=True)
        with open(RULE_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n\n{new_rule}\n")
        return f"✅ 成功！规则已永久写入本地：\n{new_rule}"
    except Exception as e:
        return f"❌ 写入规则失败：{e}"


def execute_generate_management_doc(doc_type, target_brand, context):
    prompt = f"""
    你是一名极其严厉的商场运营总监。请基于以下背景数据：
    {context}
    针对品牌：{target_brand}，生成一份【{doc_type}】。
    要求：语气正式、强硬，引用数据准确。直接输出文档内容，不要废话。
    """
    response = client.chat.completions.create(
        model=os.getenv("MODEL_NAME"),
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def get_industry_benchmark(cat2_name):
    """调用 Tavily 搜索特定业态的行业健康坪效基准"""
    if not tavily_client:
        return "未配置 TAVILY_API_KEY，无法查询行业基准。"

    # 构造精准的搜索词
    query = f"{cat2_name} 购物中心 健康坪效 行业基准 元/平米/月"
    try:
        response = tavily_client.search(query=query, search_depth="advanced", max_results=2, timeout=15)
        results = response.get("results", [])
        if not results:
            return f"未搜到【{cat2_name}】的相关行业坪效数据。"

        text = f"【{cat2_name} 行业坪效参考】：\n"
        for r in results:
            # 只截取前300个字符，避免上下文过长
            text += f"- {r['content'][:300]}...\n"
        return text
    except Exception as e:
        return f"搜索行业基准失败：{e}"


tools = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "当需要查询最新资讯、竞品动态时调用。",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_rule_book",
            "description": "当用户要求记住新规则时调用。",
            "parameters": {"type": "object", "properties": {"new_rule": {"type": "string"}}, "required": ["new_rule"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_management_doc",
            "description": "当用户要求写整改通知、巡场任务单时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_type": {"type": "string", "enum": ["整改通知函", "早会巡场任务单", "品牌约谈提纲"]},
                    "target_brand": {"type": "string"},
                    "context": {"type": "string"}
                },
                "required": ["doc_type", "target_brand", "context"]
            }
        }
    }
]


# ================= 3. 左侧报告：带反思机制 =================
def generate_targeted_insights(summary_context, activity_text="", project_name="本项目", project_city="",
                               intervention_text="暂无记录", site_status_text="暂无动态", year=2024, month=1):
    expert_rules = get_expert_rules()

    # 👇 核心：获取历史记忆
    history_context = load_previous_insight()

    month_match = re.search(r"(\d{4}年\d{1,2}月)", summary_context)
    target_month = month_match.group(1) if month_match else "近期"

    # 1. 搜索外部情报
    search_query = f"{project_city} 实体购物中心 竞品 营销活动"
    external_intel = execute_web_search(search_query)

    # 2. 搜索品牌动态
    brand_search_results = ""
    bad_brands = re.findall(r"\| (\w+.*?) \| .*? \| .*? \|", summary_context)
    valid_brands = [b.strip() for b in bad_brands if b.strip() not in ["品牌", "---"]][:3]

    for brand in valid_brands:
        print(f"🔍 正在自动检索品牌动态: {brand}")
        brand_query = f"{brand} {target_month} 品牌动态 新品发布 闭店"
        brand_res = execute_web_search(brand_query)
        brand_search_results += f"\n【{brand} 外部动态检索】：\n{brand_res}\n"

    # 3. 起草者 Prompt
    draft_prompt = f"""
你是一台冷酷无情的商业地产高级操盘手机器，同时兼任最严苛的绩效复盘官。

【历史诊断报告（上期）】：
{history_context}

【🚨 经理上期以来的干预举措】：
{intervention_text}

【🚧 现场客关与工程动态（极重要）】：
{site_status_text}

【本期最新数据摘要】：{summary_context}
【外部竞品情报】：{external_intel}
【品牌外部动态】：{brand_search_results}
【专家规则库】：{expert_rules}

【🚫 违禁词】：各位、我们、长话短说、废话少说、趴在、溜溜、拉出来、散会、立即执行、核实状态、排查导视、发质询函。

【⚠️ 绝对死命令（最高优先级）】：
1. 【现场动态交叉豁免】：必须结合【现场客关与工程动态】。如果数据中某品牌出单天数少或业绩暴跌，且现场动态中明确提到“该品牌正在装修/移位”，严禁判定为“经营不善/吸血”，必须定性为“物理施工期，正常波动”。如果是公区施工影响了特定楼层的客流，必须把原因归咎于“工程干扰”，而不是品牌自身。
2. 【举措有效性审判】：必须结合【干预举措】和【本期最新数据】进行复盘。如果上期说“约谈某品牌”，这期该品牌依然暴跌，必须严厉指出“前期干预失败，常规手段已失效”，并直接给出“强制切铺、扣罚保证金”等雷霆手段。
3. 【历史持续恶化追踪】：对比历史报告，揪出那些“屡教不改”的品牌。
4. 【地理围栏封锁】：本项目位于【{project_city}】，严禁提及跨区商圈！
5. 【数量强制要求】：按二级业态分类，至少挑出 10-15 个品牌进行审判。
6. 【🚨 数据异常校验与防瞎编（极其关键）】：
   - 严禁凭空捏造“行业均值”！如果必须对比，只能使用【数据摘要】里提供的“业态平均坪效”。如果你引用了外部的行业数据，必须在括号内注明来源（如：某行业报告）；如果外部情报没搜到可靠数据，直接写“缺乏外部权威对标，仅做内部横向对比”。
   - 对于营业额极低（如低于5000元）但出单天数很少的品牌（如贝佳颜），不要直接判定为“吸血”，必须定性为“【疑似异常/停业】需核实POS机是否故障、是否私下收银未入系统，或确认是否已物理闭店”。
   - 对于大面积且满勤，但总营业额极低（如乐刻仅1.1万）的品牌，必须提出“底层数据存疑，要求财务稽查流水真实性与POS机连接状态”。

【输出格式（必须冷血、直接）】：
### 一、 现场动态与干预举措【有效性复盘】
（直接点名：哪些是受工程/装修影响的无辜受害者？哪些是约谈后依然摆烂的“老赖”？）
### 二、 品牌下滑【历史对比、物理状态与坪效审判】
### 三、 核心品牌【断腕与止损方案】
### 四、 外部截流【真实商战评估】
### 五、 【高阶操盘指令】
（增加针对工程部/客关部的指令，如：要求施工围挡美化、增加指引牌、催促工期等）
"""
    draft_res = client.chat.completions.create(
        model=os.getenv("MODEL_NAME"), messages=[{"role": "user", "content": draft_prompt}], timeout=120
    ).choices[0].message.content

    # 4. 审查员 Prompt
    review_prompt = f"""
你是一名严苛的质检员。审查下面的分析报告：
{draft_res}

【审查铁律】：
1. 【零容忍废话】：有没有“各位”、“散会”等戏精词汇？有则打回！
2. 【现场动态豁免】：如果报告中把一个已知在“装修”的品牌判成了“吸血”，直接打回！要求重新评估！
3. 【零容忍宏观借口】：不能用全市宏观新闻解释本地数据。

如果完全合格，只输出：`[PASS]`。否则指出具体错误。
"""
    review_res = client.chat.completions.create(
        model=os.getenv("MODEL_NAME"), messages=[{"role": "user", "content": review_prompt}], timeout=120
    ).choices[0].message.content

    # 5. 最终处理与保存
    if "[PASS]" in review_res:
        final_report = draft_res
    else:
        print(f"⚠️ 触发自我反思机制，审查意见：\n{review_res}")
        revise_prompt = f"""
报告被质检员驳回。
【驳回意见】：{review_res}
【原报告】：{draft_res}
请立即修改：删除戏精废话，严格按照现场动态给装修品牌豁免，删掉宏观借口。直接输出最终报告。
"""
        final_report = client.chat.completions.create(
            model=os.getenv("MODEL_NAME"), messages=[{"role": "user", "content": revise_prompt}], timeout=120
        ).choices[0].message.content

    # 👇 核心：保存本次生成的报告到本地记忆库
    save_insight_to_history(year, month, final_report, intervention_text)

    return final_report

# ================= 4. 右侧对话框：流式输出 =================
def chat_agent_stream(user_input, chat_history, summary_context):
    expert_rules = get_expert_rules()
    system_prompt = f"""你是一名商业地产运营总监。
【当前数据摘要】：{summary_context}
【专家规则库】：{expert_rules}
【工具使用】：遇到外部资讯调用 web_search；要求写公文调用 generate_management_doc；有好经验调用 update_rule_book。
严禁捏造数据。"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": user_input})

    max_iterations = 3
    iteration = 0

    while True:
        if iteration >= max_iterations:
            yield "\n\n[系统提示：思考次数过多，已强制终止]"
            return
        iteration += 1

        try:
            response = client.chat.completions.create(
                model=os.getenv("MODEL_NAME"), messages=messages, tools=tools, stream=True, timeout=60
            )
        except Exception as e:
            yield f"调用大模型失败：{e}"
            return

        tool_calls_data = {}
        content_buffer = ""

        for chunk in response:
            delta = chunk.choices[0].delta
            if hasattr(delta, "content") and delta.content:
                content_buffer += delta.content
                yield delta.content
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {"id": tc.id, "name": tc.function.name, "arguments": ""}
                    if tc.function.arguments:
                        tool_calls_data[idx]["arguments"] += tc.function.arguments

        message_dict = {"role": "assistant", "content": content_buffer}
        if tool_calls_data:
            message_dict["tool_calls"] = [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls_data.values()
            ]
        messages.append(message_dict)

        if not tool_calls_data:
            break

        for idx_str, tc in tool_calls_data.items():
            fn = tc["name"]
            yield f"\n\n*(⚙️ 系统正在调用后台工具：{fn}...)*\n\n"
            try:
                args = json.loads(tc["arguments"])
                if fn == "web_search":
                    res = execute_web_search(**args)
                elif fn == "update_rule_book":
                    res = execute_update_rule_book(**args)
                elif fn == "generate_management_doc":
                    if "context" not in args or not args["context"]:
                        args["context"] = summary_context
                    res = execute_generate_management_doc(**args)
                else:
                    res = "无此工具"
            except Exception as e:
                res = f"报错：{e}"
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": fn, "content": res})
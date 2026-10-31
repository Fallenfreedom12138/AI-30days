import pandas as pd
import streamlit as st
import re
import json


def generate_monthly_report_data():
    if "current_excel" not in st.session_state:
        return "错误：请先在左侧侧边栏上传本月的业绩 Excel 表。"

    uploaded_file = st.session_state["current_excel"]

    try:
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        return f"读取 Excel 失败：{e}"

    # 1. 基础列校验
    required_cols = ["品牌", "业态", "营业额", "营业额同比"]
    if not all(c in df.columns for c in required_cols):
        return "❌ 格式错误：缺少必须的列（品牌、业态、营业额、营业额同比）。"

    # ================= 🔥 AI 智能品牌名清洗 =================
    # 提取 Excel 里所有不重复的品牌名
    raw_brands = df["品牌"].dropna().astype(str).unique().tolist()

    # 如果品牌特别多，为了防止 Token 爆炸，可以限制只传前 100 个
    brands_sample = raw_brands[:100]

    # 让大模型进行归一化映射
    prompt = f"""你是一个专业的数据清洗员。请把以下这些品牌名称进行归一化。
要求：将同一个品牌的不同写法（如包含中英文、带括号、带空格、简写等）合并为【一个最规范、最简短】的名称。
请以纯 JSON 格式返回一个映射字典，键是原始名称，值是清洗后的标准名称。

【原始品牌列表】
{json.dumps(brands_sample, ensure_ascii=False)}
"""
    try:
        # 调用大模型进行一次极速翻译（不带工具）
        res = client.chat.completions.create(
            model=os.getenv("MODEL_NAME"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=20
        )
        mapping_json = json.loads(res.choices[0].message.content)

        # 用大模型给的字典，替换掉原本的列
        df["品牌"] = df["品牌"].astype(str).map(lambda x: mapping_json.get(x, x))
    except Exception as e:
        # 如果大模型挂了，不影响主流程，继续用原始名字
        print(f"AI 清洗品牌名失败，使用原始数据: {e}")

    # ================= 数据格式清洗 =================
    def clean_number(val):
        if pd.isna(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        val_str = str(val).strip()
        try:
            if '%' in val_str: return float(val_str.replace('%', '')) / 100
            val_str = re.sub(r'[^\d.-]', '', val_str)
            return float(val_str)
        except:
            return 0.0

    df["营业额"] = df["营业额"].apply(clean_number)
    df["营业额同比"] = df["营业额同比"].apply(clean_number)
    if "抽成" in df.columns:
        df["抽成"] = df["抽成"].apply(clean_number)

    # 品牌名替换后，可能会有同一个品牌的多行数据（比如不同门店/不同月份），我们合并一下
    df = df.groupby(["品牌", "业态"], as_index=False).agg({
        "营业额": "sum",
        "抽成": "sum",
        "营业额同比": "mean"  # 同比取平均
    })

    # ================= 数据计算 =================
    total_revenue = df["营业额"].sum()
    total_commission = df["抽成"].sum() if "抽成" in df.columns else 0

    problem_brands = []
    for _, row in df.iterrows():
        yoy = row["营业额同比"]
        if yoy < -0.10:
            problem_brands.append({
                "品牌": row["品牌"],
                "业态": row["业态"],
                "营业额": row["营业额"],
                "同比": f"{yoy * 100:.1f}%",
            })

    # ================= 生成文本 =================
    report_context = f"""
    【数据清洗报告】
    - 原始数据共 {len(raw_brands)} 个品牌名称，经 AI 归并清洗后为 {len(df)} 个标准品牌。

    【本月大盘数据】
    - 全月总营业额：{total_revenue:,.2f} 元
    - 全月总抽成：{total_commission:,.2f} 元

    【需要重点关注的问题品牌（共 {len(problem_brands)} 个）】
    """
    for pb in problem_brands:
        report_context += f"- {pb['品牌']}（{pb['业态']}）：营业额 {pb['营业额']:,.2f}，同比下滑 {pb['同比']}\n"

    report_context += """
    \n【指令】：请根据以上大盘数据和问题品牌列表，结合你的专家规则库，生成一份专业的《月度经营分析报告》。
    """
    return report_context


def generate_targeted_insights(summary_context, activity_text=""):
    """专项洞察：业态TOP5、服装零售明细、活动通告"""
    expert_rules = get_expert_rules()

    system_prompt = f"""你是一名顶级的商业地产运营总监。
请严格基于系统提供的【数据摘要】，结合【专家规则库】，完成三大专项分析任务。

【专家规则库】：
{expert_rules}
"""

    user_prompt = f"""
【系统数据摘要】：
{summary_context}

【当月活动补充】：
{activity_text if activity_text else "暂无活动录入"}

请严格按照以下格式输出，要求使用 Markdown，语言精炼、直击痛点：

### 1. 一级业态：同比下滑品牌 TOP 5 及归因
（请从数据中提取各主要业态同比跌幅最大的前 5 名，并结合规则库给出可能的原因排查方向）

### 2. 服装零售：同环比下滑明细及调查分析
（重点筛查数据中的零售/服饰品牌，列出同环比双降的品牌，给出具体的陈列、货品、竞品等调查建议）

### 3. 当月大型活动预告及联动策略
（如果用户录入了活动，请包装成标准的商场通告，并建议场内哪些业态可以借此联动引流；如果没有录入，直接输出“暂无活动排期”）
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model=os.getenv("MODEL_NAME"),
            messages=messages,
            timeout=120
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 生成洞察失败：{e}"
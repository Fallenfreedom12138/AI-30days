import streamlit as st
import pandas as pd
import os
import datetime
import sys
import subprocess
import streamlit.components.v1 as components
from agent_backend import generate_report_backend, chat_agent_stream, generate_targeted_insights

# ================= 升级 1：页面配置与自定义 CSS =================
st.set_page_config(page_title="商业地产 AI 运营中心", page_icon="🏢", layout="wide")

# 自定义 CSS：隐藏右上角菜单，美化标题和边距，但保留侧边栏控制按钮
st.markdown("""
<style>
    /* 隐藏右上角的主菜单和部署按钮 */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display: none;}
    [data-testid="stStatusWidget"] {visibility: hidden;}
    footer {visibility: hidden;}

    /* 保留顶部栏，但为了美观把它背景变透明 */
    header {background: transparent !important;}

    /* 页面边距调整 */
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}

    /* 标题美化 */
    h1 { color: #1e3a8a; font-weight: 700; }
    h2, h3 { color: #1e293b; }

    /* 按钮圆角 */
    .stButton>button { border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("🏢 商业地产 AI 运营中心")
st.caption("深度融合业财数据、坪效审判与联网竞品监测的智能操盘手")

# ================= 核心：绝对路径计算 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data_storage")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
RULE_FILE = os.path.join(DOCS_DIR, "management_rules.txt")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# ================= 状态初始化 =================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "report_summary" not in st.session_state:
    st.session_state.report_summary = None
if "html_report" not in st.session_state:
    st.session_state.html_report = None
if "insight_report" not in st.session_state:
    st.session_state.insight_report = None

# ================= 左侧侧边栏：指挥中心 =================
with st.sidebar:
    st.header("⚙️ 控制台")

    # 1. 项目定位
    st.subheader("📍 项目定位")
    project_name = st.text_input("项目名称", value="宝山天街")
    project_city = st.text_input("所在城市/商圈", value="上海宝山刘行")

    st.divider()

    # 2. 选择分析月份
    now = datetime.datetime.now()
    col_year, col_month = st.columns(2)
    with col_year:
        sel_year = st.number_input("年份", min_value=2020, max_value=2035, value=now.year)
    with col_month:
        sel_month = st.selectbox("月份", options=list(range(1, 13)), index=now.month - 1)

    # 3. 目标额配置
    target_amt_wan = st.number_input("月度目标额 (万元)", min_value=0.0, value=11050.0, step=100.0)

    # 4. 活动预告
    activity_text = st.text_area(
        "📝 当月活动预告（供AI结合分析）",
        placeholder="例如：7月15日-20日，一楼中庭举办三体VR快闪店...",
        height=80
    )

    st.divider()

    # 5. 数据记忆库导入
    st.subheader("📁 数据记忆库导入")
    if st.button("📂 打开本地数据文件夹", use_container_width=True):
        try:
            if sys.platform == "win32":
                os.startfile(DATA_DIR)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", DATA_DIR])
            else:
                subprocess.Popen(["xdg-open", DATA_DIR])
        except Exception as e:
            st.error(f"无法打开文件夹，请手动前往：{DATA_DIR}")

    file_cur = st.file_uploader(f"1. 补传 {sel_year}年{sel_month}月 流水表", type=["xlsx"])
    if file_cur:
        save_path = os.path.join(DATA_DIR, f"{sel_year}年{sel_month}月.xlsx")
        with open(save_path, "wb") as f:
            f.write(file_cur.getbuffer())
        st.success(f"✅ 已存入：流水表")

        # 财务报表上传
    file_finance = st.file_uploader(f"2. 补传 {sel_year}年{sel_month}月 财务表(主合同)", type=["xlsx"])
    if file_finance:
        save_path_fin = os.path.join(DATA_DIR, f"{sel_year}年{sel_month}月_财务.xlsx")
        with open(save_path_fin, "wb") as f:
            f.write(file_finance.getbuffer())
        st.success(f"✅ 已存入：财务表")

    st.divider()

    # 👇 新增：干预举措记录
    intervention_text = st.text_area(
        "🛠️ 上期以来的干预举措（供AI评估是否有效）",
        placeholder="例如：上个月约谈了西贝店长；给森马发了解约函...",
        height=80
    )

    # 👇 新增：现场客关与工程动态
    site_status_text = st.text_area(
        "🚧 现场客关/工程动态（帮助AI排查外部影响）",
        placeholder="例如：一楼中庭正在做美陈升级；A区某品牌在重装；附近路段修地铁导致客流下降...",
        height=80
    )

    # 6. 一键生成逻辑
    if st.button("🚀 一键生成看板及AI洞察", type="primary", use_container_width=True):
        with st.spinner("重型引擎运转中，AI正在同步深度诊断并检索竞品..."):
            html, summary = generate_report_backend(sel_year, sel_month, target_amt_wan * 10000)

            if html:
                st.session_state.html_report = html
                st.session_state.report_summary = summary

                insight_answer = generate_targeted_insights(
                    summary_context=summary,
                    activity_text=activity_text,
                    project_name=project_name,
                    project_city=project_city,
                    intervention_text=intervention_text,
                    site_status_text=site_status_text,  # 👈 新增传参
                    year=sel_year,
                    month=sel_month
                )
                st.session_state.insight_report = insight_answer
                st.success("✅ 看板与洞察生成成功！")
            else:
                st.error(summary)

    if st.session_state.html_report:
        st.download_button(
            label="⬇️ 下载完整 HTML 报表",
            data=st.session_state.html_report,
            file_name=f"{sel_year}年{sel_month}月预测报告.html",
            mime="text/html",
            use_container_width=True
        )

# ================= 主界面：分页显示 =================
tab1, tab2 = st.tabs(["📊 智能看板与问答", "📚 专家规则库管理"])

# --- 标签页 1：看板与问答 ---
with tab1:
    # ================= 顶部：看板与洞察 =================
    st.subheader("📈 预测图表看板")

    if st.session_state.html_report:
        # 渲染 HTML 看板 (高度调整为800，视野更开阔)
        components.html(st.session_state.html_report, height=800, scrolling=True)

        st.divider()

        # ================= 升级 2：洞察报告下载功能 =================
        col_insight_title, col_insight_btn = st.columns([4, 1])
        with col_insight_title:
            st.subheader("🔍 AI 专项运营洞察")
        with col_insight_btn:
            if st.session_state.insight_report:
                st.download_button(
                    label="⬇️ 下载洞察报告 (Markdown)",
                    data=st.session_state.insight_report,
                    file_name=f"{sel_year}年{sel_month}月_AI运营洞察.md",
                    mime="text/markdown",
                    use_container_width=True
                )

        if st.session_state.insight_report:
            # 用一个漂亮的容器包裹 AI 报告
            with st.container(border=True):
                st.markdown(st.session_state.insight_report)
        else:
            st.info("正在等待洞察报告生成...")
    else:
        st.info("👈 请在左侧配置参数并点击【一键生成看板及AI洞察】。")

    # ================= 底部：在线问答 =================
    st.divider()
    st.subheader("💬 在线咨询与诊断")

    chat_container = st.container(height=500)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if user_input := st.chat_input("例如：结合上面的坪效数据，帮我起草一份森马的整改通知函。"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.chat_message("assistant"):
                summary_context = st.session_state.report_summary if st.session_state.report_summary else "用户尚未生成看板数据。"
                response_stream = chat_agent_stream(
                    user_input,
                    st.session_state.messages[:-1],
                    summary_context
                )
                full_answer = st.write_stream(response_stream)

        st.session_state.messages.append({"role": "assistant", "content": full_answer})

# --- 标签页 2：规则库管理 UI ---
with tab2:
    st.subheader("📚 专家规则库管理")
    st.info(f"💡 当前正在读取的规则文件：\n\n`{RULE_FILE}`")

    upload_rule = st.file_uploader("上传你的历史规则 txt 文件 (可选)", type=["txt"])
    if upload_rule:
        with open(RULE_FILE, "wb") as f:
            f.write(upload_rule.getbuffer())
        st.success("老规则文件已成功导入！")
        st.rerun()

    try:
        with open(RULE_FILE, "r", encoding="utf-8") as f:
            rules_text = f.read()
    except FileNotFoundError:
        rules_text = "暂无规则，请在此处输入你的第一条经验：\n\n【规则1】：如果..."

    edited_rules = st.text_area("规则内容", value=rules_text, height=600)

    if st.button("💾 保存规则修改", type="primary"):
        with open(RULE_FILE, "w", encoding="utf-8") as f:
            f.write(edited_rules)
        st.success("✅ 规则库已更新！下次提问时 AI 将立即生效。")
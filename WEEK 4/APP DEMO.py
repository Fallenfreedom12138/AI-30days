import streamlit as st

#网页标题
st.title("🧪 我的第一个多多 AI 聊天网页")

#初始化聊天标题
if "messages" not in st.session_state:
    st.session_state.messages=[]

#遍历历史聊天信息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

#接收输入
user_input=st.chat_input("多多：说点什么吧")

if user_input:
    # 1. 把用户消息显示在页面并存入历史
    st.session_state.messages.append({"role":"user", "content":user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 2. 假装 AI 在思考（模拟响应）
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            reply=f"你刚刚说了{user_input}"
            st.write(reply)
            st.session_state.messages.append({"role":"assistant","content":reply})
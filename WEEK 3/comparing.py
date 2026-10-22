# 1. 用户输入
user_input = input("请提问：")
messages = [{"role": "user", "content": user_input}]

# 2. 第一次请求模型
response = client.chat.completions.create(
    model=os.getenv("MODEL_NAME"),
    messages=messages,
    tools=tools
)

message = response.choices[0].message
messages.append(message)  # 必须把模型的响应追加到历史

# 3. 检查是否需要调用工具
if message.tool_calls:
    tool_call = message.tool_calls[0]
    function_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments)

    print(f"模型决定调用工具: {function_name}，参数: {arguments}")

    # 4. 执行本地函数
    if function_name == "filter_data":
        tool_result = execute_filter_data(
            arguments["column"],
            arguments["operator"],
            arguments["value"]
        )
        print(f"本地执行结果：\n{tool_result}")

        # 5. 把工具执行结果回喂给模型 (极其重要！)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,  # 必须带上模型的 call_id
            "name": function_name,
            "content": tool_result
        })

        # 6. 第二次请求模型，让它基于数据生成最终回答
        print("\n正在让模型总结最终答案...")
        second_response = client.chat.completions.create(
            model=os.getenv("MODEL_NAME"),
            messages=messages
        )

        print("\n--- 最终回答 ---")
        print(second_response.choices[0].message.content)
else:
    print("模型直接回答：", message.content)
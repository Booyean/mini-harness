ASK_USER_TOOL = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": "遇到歧义需用户决策时提问，暂停等待回答。不要问可自行判断的问题",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "要问用户的问题",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选选项列表（可选）",
                },
            },
            "required": ["question"],
        },
    },
}


def execute_ask_user(arguments):
    question = str(arguments.get("question", "")).strip()
    if not question:
        return "错误：问题为空"
    options = [str(o) for o in arguments.get("options", [])]

    print(f"\n[Agent 提问] {question}")
    if options:
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        print("输入序号或直接回答：", end="", flush=True)
    else:
        print("你的回答：", end="", flush=True)

    try:
        answer = input().strip()
    except (EOFError, KeyboardInterrupt):
        return "用户没有回答"

    if options and answer.isdigit() and 1 <= int(answer) <= len(options):
        answer = options[int(answer) - 1]
    return f"用户回答：{answer}"

from agent.context import build_chatml, count_messages_tokens, count_tokens


def main():
    print("=== 1. 中英文 token 对比 ===")
    samples = [
        ("hello world", "常见英文短语"),
        ("unbelievable", "一个英文单词"),
        ("你好世界", "4 个汉字"),
        ("人工智能正在改变世界", "10 个汉字"),
    ]
    for text, label in samples:
        print(f"{label:12} | '{text}' = {count_tokens(text)} tokens")

    print("\n=== 2. messages 数组 -> ChatML 纯文本 ===")
    messages = [
        {"role": "system", "content": "你是一个简洁的助手"},
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮你？"},
    ]
    rendered = build_chatml(messages)
    print(rendered)

    print("=== 3. 整段对话的 token 数 ===")
    total = count_messages_tokens(messages)
    print(f"messages 数组共 {total} tokens（含角色标记）")


if __name__ == "__main__":
    main()

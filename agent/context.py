import json

import tiktoken

DEFAULT_ENCODING = "cl100k_base"


def count_tokens(text, encoding_name=DEFAULT_ENCODING):
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))


def build_chatml(messages):
    parts = []
    for msg in messages:
        role = msg["role"]
        content = msg.get("content") or ""
        if msg.get("tool_calls"):
            content += json.dumps(msg["tool_calls"], ensure_ascii=False)
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    parts.append("<|im_start|>assistant\n")
    return "\n".join(parts)


def count_messages_tokens(messages, encoding_name=DEFAULT_ENCODING):
    return count_tokens(build_chatml(messages), encoding_name)


def trim_messages(messages, max_tokens, headroom_ratio=0.1):
    if len(messages) <= 1:
        return messages
    system = messages[:1]
    rest = list(messages[1:])
    target = int(max_tokens * (1 - headroom_ratio))

    while rest and count_messages_tokens(system + rest) > target:
        dropped = rest.pop(0)
        if dropped.get("tool_calls"):
            while rest and rest[0].get("role") == "tool":
                rest.pop(0)

    return system + rest

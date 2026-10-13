def stream_chat(client, messages, temperature=0, max_tokens=1024):
    stream = client.create_stream(
        messages, temperature=temperature, max_tokens=max_tokens
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        finish_reason = chunk.choices[0].finish_reason
        yield delta.content, finish_reason


def stream_chat_full(client, messages, temperature=0, max_tokens=1024, tools=None):
    stream = client.create_stream(
        messages, temperature=temperature, max_tokens=max_tokens, tools=tools
    )
    content_parts = []
    tool_calls_acc = {}
    finish_reason = None

    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        chunk_finish = chunk.choices[0].finish_reason
        if chunk_finish:
            finish_reason = chunk_finish

        if delta.content:
            content_parts.append(delta.content)
            yield "text", delta.content

        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {"id": None, "name": None, "arguments": ""}
                acc = tool_calls_acc[idx]
                if tc_delta.id:
                    acc["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        acc["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        acc["arguments"] += tc_delta.function.arguments

    tool_calls = None
    if tool_calls_acc:
        tool_calls = [
            {
                "id": acc["id"],
                "name": acc["name"],
                "arguments": acc["arguments"],
            }
            for _, acc in sorted(tool_calls_acc.items())
        ]

    yield "done", {
        "content": "".join(content_parts),
        "tool_calls": tool_calls,
        "finish_reason": finish_reason,
    }

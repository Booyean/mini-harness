import difflib
import json
import os

from agent import permissions
from agent.context import count_messages_tokens, trim_messages
from agent.events import DEFAULT_BUS
from model.streaming import stream_chat_full
from tools import registry, todo
from tools.filesystem import _safe_path


def _read_file_content(path_str):
    path = _safe_path(path_str)
    if not path or not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _strip_history_images(msgs):
    last_img_idx = None
    for i in range(len(msgs) - 1, -1, -1):
        content = msgs[i].get("content")
        if isinstance(content, list) and any(
            c.get("type") == "image_url" for c in content
        ):
            last_img_idx = i
            break

    stripped = []
    for i, m in enumerate(msgs):
        content = m.get("content")
        if isinstance(content, list):
            keep = i == last_img_idx
            new_content = []
            for c in content:
                if c.get("type") == "image_url" and not keep:
                    new_content.append(
                        {
                            "type": "text",
                            "text": "[图片已卸载，需要时用 read_image 重新加载]",
                        }
                    )
                else:
                    new_content.append(c)
            m2 = dict(m)
            m2["content"] = new_content
            stripped.append(m2)
        else:
            stripped.append(m)
    return stripped


def _compact(client, messages_to_summarize, temperature=0.3):
    response = client.chat(
        [
            {
                "role": "system",
                "content": "你是对话压缩器。把下面这段对话历史压缩成简洁的摘要，"
                "必须保留：1) 已完成的任务；2) 关键文件及其内容要点；"
                "3) 未完成事项；4) 重要结论和用户偏好。中文，300 字以内。",
            },
            {
                "role": "user",
                "content": json.dumps(
                    [
                        {"role": m.get("role"), "content": str(m.get("content", ""))[:2000]}
                        for m in messages_to_summarize
                        if m.get("role") != "system"
                    ],
                    ensure_ascii=False,
                ),
            },
        ],
        max_tokens=600,
        temperature=temperature,
    )
    return response["content"]


def run_loop(
    client,
    messages,
    max_iterations=5,
    max_context_tokens=None,
    max_tokens=4096,
    temperature=0.3,
    verbose=False,
    events=None,
    stall_limit=5,
):
    bus = events or DEFAULT_BUS
    stall_count = 0
    last_content = None
    silent_rounds = 0

    for i in range(max_iterations):
        if verbose:
            print(f"\n=== 第 {i + 1} 轮 ===")

        if max_context_tokens is not None:
            trimmed = trim_messages(messages, max_context_tokens)
            if len(trimmed) < len(messages):
                bus.emit("compact_start")
                dropped_count = len(messages) - len(trimmed)
                dropped = messages[1 : 1 + dropped_count]
                try:
                    summary = _compact(client, dropped)
                    compacted = (
                        [messages[0]]
                        + [{"role": "user", "content": f"（历史对话摘要）\n{summary}"}]
                        + trimmed[1:]
                    )
                    messages[:] = compacted
                    bus.emit(
                        "context_trimmed",
                        before=len(trimmed) + dropped_count,
                        after=len(compacted),
                        compacted=True,
                    )
                except Exception:
                    messages[:] = trimmed
                    bus.emit(
                        "context_trimmed",
                        before=len(messages),
                        after=len(trimmed),
                        compacted=False,
                    )
                if verbose:
                    print(f"[上下文压缩] -> {len(messages)} 条")

        content_parts = []
        while True:
            final = None
            retry_temp = temperature + 0.5 if stall_count > 0 else temperature

            todo_text = todo.format_todos(todo.load_todos())
            call_messages = _strip_history_images(messages) + [
                {
                    "role": "system",
                    "content": f"当前任务清单：\n{todo_text}\n"
                    "（处理多步骤任务时用 update_todo 维护此清单）",
                }
            ]

            for kind, payload in stream_chat_full(
                client,
                call_messages,
                tools=registry.get_tool_schemas(),
                max_tokens=max_tokens,
                temperature=retry_temp,
            ):
                if kind == "text":
                    content_parts.append(payload)
                    bus.emit("text", content=payload)
                    if verbose:
                        print(payload, end="", flush=True)
                elif kind == "done":
                    final = payload

            if verbose:
                print(f"\n[finish_reason={final['finish_reason']}]")

            content = "".join(content_parts)

            if final["finish_reason"] == "tool_calls" and final["tool_calls"]:
                break

            if final["finish_reason"] == "length":
                stall_count += 1
                messages.append(
                    {
                        "role": "user",
                        "content": "（系统提示：你的输出被截断了。请直接继续，"
                        "需要操作文件或执行命令就直接调用工具，不要重复之前的话。）",
                    }
                )
                if stall_count >= stall_limit:
                    return _abort(
                        bus, "连续多次输出被截断，任务中止。请换一种说法重试。", i, messages
                    )
                continue

            if not content.strip():
                stall_count += 1
                messages.append(
                    {
                        "role": "user",
                        "content": "（系统提示：你刚才没有生成任何内容。"
                        "如果任务需要操作文件或执行命令，请直接调用工具；"
                        "否则请直接回答。）",
                    }
                )
                if stall_count >= stall_limit:
                    return _abort(
                        bus, "检测到连续空转，任务中止。请换一种说法重试。", i, messages
                    )
                continue

            break

        if final["finish_reason"] == "tool_calls" and final["tool_calls"]:
            stall_count = 0
            if not content.strip():
                silent_rounds += 1
            else:
                silent_rounds = 0
            if silent_rounds >= 2:
                silent_rounds = 0
                messages.append(
                    {
                        "role": "user",
                        "content": "（系统提示：你已连续多轮静默执行工具。"
                        "请在下一轮先用一句话向用户说明"
                        "当前在做什么、为什么这么做，再调用工具。）",
                    }
                )
            tool_call_dicts = []
            for tc in final["tool_calls"]:
                tool_call_dicts.append(
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    }
                )
                bus.emit("tool_call", name=tc["name"], arguments=tc["arguments"])
                if verbose:
                    print(f"[点单] {tc['name']} 参数={tc['arguments']}")

            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_call_dicts,
                }
            )

            tool_infos = []
            for tc in final["tool_calls"]:
                try:
                    args = json.loads(tc["arguments"])
                except json.JSONDecodeError:
                    args = {}
                tool_infos.append((tc["name"], args))

            decisions = permissions.check_permissions_batch(tool_infos)
            if decisions is None:
                bus.emit("text", content="用户中止了任务。\n")
                return "用户中止了任务", i + 1

            pending_images = []
            for tc, (name, args), allowed in zip(
                final["tool_calls"], tool_infos, decisions
            ):
                old_text = _read_file_content(str(args.get("path", "")))

                if allowed:
                    result = registry.execute_tool(name, args)
                else:
                    result = "用户拒绝了此操作"

                if name == "read_image" and result.startswith('{"__image__"'):
                    try:
                        img_info = json.loads(result)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": f"图像已加载：{img_info['path']}",
                            }
                        )
                        pending_images.append(img_info)
                        continue
                    except json.JSONDecodeError:
                        pass

                new_text = _read_file_content(str(args.get("path", "")))

                diff_text = None
                if (
                    name in ("write_file", "edit_file")
                    and not result.startswith("错误")
                    and not result.startswith("用户拒绝")
                ):
                    old_lines = (old_text or "").splitlines(keepends=True)
                    new_lines = (new_text or "").splitlines(keepends=True)
                    diff_text = "".join(
                        difflib.unified_diff(old_lines, new_lines, n=1)
                    )

                bus.emit(
                    "tool_result",
                    name=name,
                    result=result,
                    diff=diff_text,
                )
                if verbose:
                    print(f"[结果] {result}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

            for img_info in pending_images:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"[read_image 结果：{img_info['path']}] 请观察图片内容并回答",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": img_info["data_uri"]},
                            },
                        ],
                    }
                )
            continue

        if content.strip() == last_content:
            stall_count += 1
        else:
            stall_count = 0
        last_content = content.strip()

        if stall_count >= stall_limit:
            return _abort(
                bus, "检测到连续重复输出，任务中止。请换一种说法重试。", i, messages
            )

        bus.emit(
            "assistant_done",
            content=content,
            rounds=i + 1,
            context_tokens=count_messages_tokens(messages),
        )
        return content, i + 1

    bus.emit(
        "assistant_done",
        content="达到最大循环次数，任务中止",
        rounds=max_iterations,
        context_tokens=count_messages_tokens(messages),
    )
    return "达到最大循环次数，任务中止", max_iterations


def _abort(bus, msg, rounds, messages):
    bus.emit("text", content=msg + "\n")
    bus.emit(
        "assistant_done",
        content=msg,
        rounds=rounds + 1,
        context_tokens=count_messages_tokens(messages),
    )
    return msg, rounds + 1

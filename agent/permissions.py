import json

READONLY_TOOLS = {
    "read_file",
    "list_files",
    "grep",
    "calculator",
    "web_search",
    "webfetch",
    "update_todo",
    "ask_user",
    "read_image",
    "ocr_image",
}

_session_rules = {}


def set_rule(tool_name, allowed):
    _session_rules[tool_name] = allowed


def get_rules():
    return dict(_session_rules)


def _safe_input(prompt):
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None


def check_permission(tool_name, arguments):
    if tool_name in READONLY_TOOLS or tool_name.startswith("mcp_"):
        return True
    if tool_name in _session_rules:
        return _session_rules[tool_name]

    print("\n[approval required]")
    print(f"工具: {tool_name}")
    print(f"参数: {json.dumps(arguments, ensure_ascii=False)}")

    while True:
        answer = _safe_input("Allow? [y/n/q=中止任务] ")
        if answer is None:
            return False
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        if answer == "q":
            return None
        print("请输入 y / n / q")


def check_permissions_batch(tool_calls):
    decisions = []
    pending = []

    for i, (name, args) in enumerate(tool_calls):
        if name in READONLY_TOOLS or name.startswith("mcp_"):
            decisions.append(True)
        elif name in _session_rules:
            decisions.append(_session_rules[name])
        else:
            pending.append((i, name, args))
            decisions.append(False)

    if not pending:
        return decisions

    print(f"\n[approval required] 本轮 {len(pending)} 个操作：")
    for j, (_, name, args) in enumerate(pending, 1):
        desc = json.dumps(args, ensure_ascii=False)
        if len(desc) > 100:
            desc = desc[:100] + "..."
        print(f"  {j}. {name}  {desc}")

    while True:
        answer = _safe_input(
            "Allow? [y=全部执行 / n=全部拒绝 / s=逐个确认 / q=中止任务] "
        )
        if answer is None:
            return None
        if answer in ("y", "yes"):
            for i, _, _ in pending:
                decisions[i] = True
            return decisions
        if answer in ("n", "no"):
            for i, _, _ in pending:
                decisions[i] = False
            return decisions
        if answer == "q":
            return None
        if answer == "s":
            for j, (i, name, args) in enumerate(pending, 1):
                sub = _safe_input(f"  {j}. {name}? [y/n] ")
                decisions[i] = sub in ("y", "yes")
            return decisions
        print("请输入 y / n / s / q")

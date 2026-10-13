import json
import os

from tools.filesystem import WORK_DIR

TODO_PATH = os.path.join(WORK_DIR, ".mini-harness-todo.json")

STATUS_ICONS = {"pending": "☐", "in_progress": "▶", "completed": "☑"}

UPDATE_TODO_TOOL = {
    "type": "function",
    "function": {
        "name": "update_todo",
        "description": "更新任务清单。多步任务用它记录进度，支持主任务+子任务两层结构，每完成一步更新状态",
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "主任务描述",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "任务状态（有子任务时自动推导）",
                            },
                            "subtasks": {
                                "type": "array",
                                "description": "子任务列表（可选）",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "content": {
                                            "type": "string",
                                            "description": "子任务描述",
                                        },
                                        "status": {
                                            "type": "string",
                                            "enum": ["pending", "in_progress", "completed"],
                                        },
                                    },
                                    "required": ["content", "status"],
                                },
                            },
                        },
                        "required": ["content", "status"],
                    },
                    "description": "完整任务清单（整体覆盖旧清单）",
                }
            },
            "required": ["todos"],
        },
    },
}


def load_todos():
    if not os.path.exists(TODO_PATH):
        return []
    try:
        with open(TODO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def save_todos(todos):
    with open(TODO_PATH, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)


def _derive_parent_status(subtasks):
    statuses = {s.get("status", "pending") for s in subtasks}
    if statuses <= {"completed"}:
        return "completed"
    if "in_progress" in statuses or "completed" in statuses:
        return "in_progress"
    return "pending"


def _normalize(todos):
    result = []
    for t in todos:
        content = str(t.get("content", "")).strip()
        if not content:
            continue
        subs = [
            s
            for s in t.get("subtasks", [])
            if str(s.get("content", "")).strip()
        ]
        if subs:
            t["subtasks"] = subs
            t["status"] = _derive_parent_status(subs)
        result.append(t)
    return result


def format_todos(todos):
    if not todos:
        return "（空）"
    lines = []
    for t in todos:
        status = t.get("status", "pending")
        subs = t.get("subtasks", [])
        if subs:
            status = _derive_parent_status(subs)
        lines.append(f"{STATUS_ICONS.get(status, '☐')} {t.get('content', '')}")
        for s in subs:
            s_status = s.get("status", "pending")
            lines.append(
                f"    {STATUS_ICONS.get(s_status, '☐')} {s.get('content', '')}"
            )
    return "\n".join(lines)


def execute_update_todo(arguments):
    todos = arguments.get("todos", [])
    todos = _normalize(todos)
    save_todos(todos)
    return f"任务清单已更新：\n{format_todos(todos)}"

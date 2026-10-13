import json
import os
from datetime import datetime

SESSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions"
)


def new_session_id():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def session_path(session_id):
    return os.path.join(SESSIONS_DIR, f"{session_id}.json")


def tmp_session_path(session_id):
    return os.path.join(SESSIONS_DIR, f".tmp_{session_id}.json")


def _strip_images(messages):
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            new_content = []
            for c in content:
                if c.get("type") == "image_url":
                    new_content.append(
                        {"type": "text", "text": "[历史图片已移除]"}
                    )
                else:
                    new_content.append(c)
            m["content"] = new_content
    return messages


def sanitize_messages(messages):
    cleaned = []
    i = 0
    while i < len(messages):
        m = messages[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            ids = {tc.get("id") for tc in m["tool_calls"]}
            j = i + 1
            found = set()
            while j < len(messages) and messages[j].get("role") == "tool":
                found.add(messages[j].get("tool_call_id"))
                j += 1
            if ids and ids <= found:
                cleaned.extend(messages[i:j])
            i = j
            continue
        cleaned.append(m)
        i += 1
    return _strip_images(cleaned)


def save_session(session_id, messages, model, title=None, todo_snapshot=None):
    data = {
        "session_id": session_id,
        "model": model,
        "title": title,
        "todo_snapshot": todo_snapshot,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "messages": sanitize_messages(messages),
    }
    with open(tmp_session_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def commit_session(session_id):
    tmp = tmp_session_path(session_id)
    if os.path.exists(tmp):
        os.replace(tmp, session_path(session_id))
        return True
    return False


def discard_session(session_id):
    tmp = tmp_session_path(session_id)
    if os.path.exists(tmp):
        os.remove(tmp)
        return True
    return False


def load_session(session_id):
    path = session_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_sessions():
    if not os.path.isdir(SESSIONS_DIR):
        return []
    results = []
    for f in os.listdir(SESSIONS_DIR):
        if f.endswith(".json") and not f.startswith(".tmp_"):
            session_id = f[:-5]
            try:
                with open(os.path.join(SESSIONS_DIR, f), "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                title = data.get("title") or "（未命名）"
            except (OSError, json.JSONDecodeError):
                title = "（未命名）"
            results.append((session_id, title))
    return sorted(results)


def find_session_by_title(keyword):
    keyword = keyword.lower()
    for s_id, s_title in list_sessions():
        if s_title and keyword in s_title.lower():
            return s_id
        if keyword in s_id.lower():
            return s_id
    return None

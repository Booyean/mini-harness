import os

WORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LIMIT = 150
MAX_LIMIT = 300


def set_work_dir(path):
    global WORK_DIR
    WORK_DIR = os.path.abspath(path)

READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "分段读取文件内容，返回带行号的文本。默认从第 1 行读 150 行；"
        "文件很长时，用 offset 参数继续读取后续部分",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对工作目录的文件路径，如 'main.py'",
                },
                "offset": {
                    "type": "integer",
                    "description": "起始行号（从 1 开始），默认 1",
                },
                "limit": {
                    "type": "integer",
                    "description": "读取行数，默认 150，最大 300",
                },
            },
            "required": ["path"],
        },
    },
}

LIST_FILES_TOOL = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "列出目录中的文件和子目录名。用于了解项目结构，"
        "不显示文件内容（看内容用 read_file）",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对工作目录的路径，如 '.' 或 'src'，默认 '.'",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出子目录（默认 false）",
                },
            },
        },
    },
}

DELETE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "delete_file",
        "description": "删除工作目录内的指定文件（仅单文件，不支持目录）。"
        "用于清理临时文件、脚本残留",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对工作目录的文件路径，如 '_probe.py'",
                },
            },
            "required": ["path"],
        },
    },
}

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "创建新文件或覆盖已有文件的全部内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对工作目录的文件路径，如 'hello.py'",
                },
                "content": {
                    "type": "string",
                    "description": "文件的完整内容",
                },
            },
            "required": ["path", "content"],
        },
    },
}

EDIT_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": "精确修改文件内容。修改前必须先 read_file。"
        "首选方式：old_string 提供文件中要替换的原文片段（必须唯一匹配），"
        "new_string 为新内容。找不到或匹配多处会报错，此时重新读文件再试。"
        "兼容方式：用 line 行号定位（不推荐，行号可能漂移）",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对工作目录的文件路径",
                },
                "old_string": {
                    "type": "string",
                    "description": "文件中要替换的原文片段（必须与文件内容完全一致且唯一）",
                },
                "new_string": {
                    "type": "string",
                    "description": "替换后的新内容",
                },
                "line": {
                    "type": "integer",
                    "description": "兼容模式：要修改的行号（不推荐）",
                },
                "content": {
                    "type": "string",
                    "description": "兼容模式：该行的新内容",
                },
            },
            "required": ["path"],
        },
    },
}


def _safe_path(path):
    full = os.path.abspath(os.path.join(WORK_DIR, path))
    if not full.startswith(WORK_DIR):
        return None
    return full


def execute_read_file(arguments):
    path = _safe_path(str(arguments.get("path", "")))
    if path is None:
        return "错误：路径超出工作目录范围"
    if not os.path.exists(path):
        return f"错误：文件不存在: {arguments.get('path')}"
    if os.path.isdir(path):
        return f"错误：{arguments.get('path')} 是目录，不是文件"

    try:
        offset = int(arguments.get("offset", 1))
        limit = int(arguments.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        offset, limit = 1, DEFAULT_LIMIT
    offset = max(1, offset)
    limit = min(max(1, limit), MAX_LIMIT)

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    total = len(lines)
    if total == 0:
        return f"文件 {arguments.get('path')} 为空（0 行）"
    if offset > total:
        return f"错误：起始行 {offset} 超出文件总行数（共 {total} 行）"

    end = min(offset + limit - 1, total)
    shown = lines[offset - 1 : end]
    numbered = [
        f"{offset + i}: {line.rstrip()}" for i, line in enumerate(shown)
    ]

    header = (
        f"[文件 {arguments.get('path')}，共 {total} 行，"
        f"显示第 {offset}-{end} 行]"
    )
    text = header + "\n" + "\n".join(numbered)

    if end < total:
        text += f"\n[剩余 {total - end} 行未显示，可用 offset={end + 1} 继续读取]"
    return text


def execute_list_files(arguments):
    path_str = str(arguments.get("path", "") or ".")
    recursive = bool(arguments.get("recursive", False))

    path = _safe_path(path_str)
    if path is None:
        return "错误：路径超出工作目录范围"
    if not os.path.isdir(path):
        return f"错误：目录不存在: {path_str}"

    lines = []
    if recursive:
        for root, dirs, files in os.walk(path):
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d not in ("node_modules", ".git", "__pycache__", "dist", "build")
            ]
            rel = os.path.relpath(root, path)
            prefix = "" if rel == "." else rel + os.sep
            for name in sorted(dirs):
                lines.append(f"{prefix}{name}/")
            for name in sorted(files):
                if not name.startswith("."):
                    lines.append(f"{prefix}{name}")
    else:
        for name in sorted(os.listdir(path)):
            if name.startswith("."):
                continue
            full = os.path.join(path, name)
            lines.append(name + "/" if os.path.isdir(full) else name)

    if not lines:
        return f"目录 {path_str} 为空"
    return f"[{path_str} 目录内容，{len(lines)} 项]\n" + "\n".join(lines)


PROTECTED_NAMES = {".mini-harness.md", ".gitignore", "user_memory.md"}


def execute_delete_file(arguments):
    path = _safe_path(str(arguments.get("path", "")))
    if path is None:
        return "错误：路径超出工作目录范围"
    name = os.path.basename(path)
    if name.startswith(".") or name in PROTECTED_NAMES:
        return f"错误：拒绝删除受保护文件: {name}"
    if not os.path.exists(path):
        return f"错误：文件不存在: {arguments.get('path')}"
    if os.path.isdir(path):
        return "错误：不支持删除目录，只支持单文件"
    try:
        os.remove(path)
    except Exception as e:
        return f"错误：删除失败: {e}"
    return f"已删除 {arguments.get('path')}"


def execute_write_file(arguments):
    path = _safe_path(str(arguments.get("path", "")))
    if path is None:
        return "错误：路径超出工作目录范围"
    content = str(arguments.get("content", ""))
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        return f"错误：目录不存在: {parent}"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"错误：写入失败: {e}"
    return f"已写入 {arguments.get('path')}（{content.count(chr(10)) + 1} 行）"


def execute_edit_file(arguments):
    path = _safe_path(str(arguments.get("path", "")))
    if path is None:
        return "错误：路径超出工作目录范围"
    if not os.path.exists(path):
        return f"错误：文件不存在: {arguments.get('path')}"

    old_string = arguments.get("old_string")
    if old_string is not None:
        return _edit_by_string(path, arguments, str(old_string))

    line = arguments.get("line")
    if line is not None:
        return _edit_by_line(path, arguments)

    return "错误：必须提供 old_string（或兼容的 line 行号）。修改前请先 read_file"


def _edit_by_string(path, arguments, old_string):
    new_string = str(arguments.get("new_string", ""))
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    count = content.count(old_string)
    if count == 0:
        return (
            "错误：文件中找不到 old_string 的原文。"
            "文件可能已被修改，请先 read_file 获取当前内容再试"
        )
    if count > 1:
        return (
            f"错误：old_string 在文件中出现 {count} 次，不唯一。"
            "请提供更长、更精确的原文片段"
        )

    new_content = content.replace(old_string, new_string, 1)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return f"错误：写入失败: {e}"
    return f"已修改 {arguments.get('path')}（原文定位替换）"


def _edit_by_line(path, arguments):
    try:
        line = int(arguments.get("line", 0))
        new_content = str(arguments.get("content", ""))
    except (TypeError, ValueError):
        return "错误：行号无效"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    if line < 1 or line > len(lines):
        return f"错误：行号 {line} 不存在（文件共 {len(lines)} 行）"
    lines[line - 1] = new_content.rstrip("\n") + "\n"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        return f"错误：写入失败: {e}"
    return f"已修改 {arguments.get('path')} 第 {line} 行"

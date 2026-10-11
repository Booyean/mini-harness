import fnmatch
import html
import os
import re

import requests

from tools.filesystem import _safe_path

SEARCH_URL = "https://serpapi.com/search.json"

WEBFETCH_TOOL = {
    "type": "function",
    "function": {
        "name": "webfetch",
        "description": "读取网页内容并转换为纯文本。用于查看网页文档、在线文章、API 文档",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要读取的网页 URL，如 'https://example.com/page'",
                },
            },
            "required": ["url"],
        },
    },
}

GREP_TOOL = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": "在项目文件中搜索匹配的文本。返回文件路径、行号和匹配行。"
        "用于查找函数定义、变量引用、配置项等。支持正则表达式",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "要搜索的文本或正则表达式",
                },
                "path": {
                    "type": "string",
                    "description": "搜索的目录，默认工作目录",
                },
                "include": {
                    "type": "string",
                    "description": "文件类型过滤，如 '*.py'（可选）",
                },
            },
            "required": ["pattern"],
        },
    },
}

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "用 Google 搜索网页，返回相关结果的标题、链接和摘要。用于查询事实、最新信息、百科知识等",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如 'Python 教程'",
                },
                "num": {
                    "type": "integer",
                    "description": "返回结果数量，默认 5",
                },
            },
            "required": ["query"],
        },
    },
}


def execute_web_search(arguments):
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        return "错误：缺少 SERPAPI_API_KEY 环境变量"

    query = str(arguments.get("query", "")).strip()
    if not query:
        return "错误：缺少搜索关键词"

    try:
        num = int(arguments.get("num", 5))
    except (TypeError, ValueError):
        num = 5

    try:
        response = requests.get(
            SEARCH_URL,
            params={
                "q": query,
                "api_key": api_key,
                "num": num,
                "hl": "zh-cn",
            },
            timeout=15,
        )
        data = response.json()
    except requests.Timeout:
        return "错误：搜索请求超时"
    except Exception as e:
        return f"错误：搜索失败: {e}"

    if data.get("error"):
        return f"错误：{data['error']}"

    organic = data.get("organic_results", [])
    if not organic:
        return f"没有找到与 '{query}' 相关的结果"

    lines = []
    for i, item in enumerate(organic[:num], 1):
        title = item.get("title", "无标题")
        link = item.get("link", "")
        snippet = (item.get("snippet") or "").strip()
        lines.append(f"{i}. {title}\n   {link}\n   {snippet}")

    return "\n".join(lines)


IGNORED_DIRS = {".git", "node_modules", "__pycache__", "dist", "build", ".venv"}


def execute_grep(arguments):
    pattern = str(arguments.get("pattern", ""))
    if not pattern:
        return "错误：缺少搜索模式"
    path_str = str(arguments.get("path", "") or ".")
    include = str(arguments.get("include", "") or "")

    base = _safe_path(path_str)
    if base is None:
        return "错误：路径超出工作目录范围"
    if not os.path.isdir(base):
        return f"错误：目录不存在: {path_str}"

    try:
        regex = re.compile(pattern)
    except re.error:
        regex = None

    matches = []
    max_matches = 100

    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        for name in sorted(files):
            if name.startswith("."):
                continue
            if include and not fnmatch.fnmatch(name, include):
                continue
            full = os.path.join(root, name)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        hit = regex.search(line) if regex else pattern in line
                        if hit:
                            matches.append(
                                f"{os.path.relpath(full, base)}:{lineno}: "
                                f"{line.rstrip()[:120]}"
                            )
            except OSError:
                continue
            if len(matches) >= max_matches:
                break
        if len(matches) >= max_matches:
            break

    if not matches:
        return f"在 {path_str} 中没有找到 '{pattern}'"
    result = f"[找到 {len(matches)} 处匹配]\n" + "\n".join(matches[:max_matches])
    if len(matches) > max_matches:
        result += "\n[匹配过多，已截断]"
    return result


def execute_webfetch(arguments):
    url = str(arguments.get("url", "")).strip()
    if not url:
        return "错误：缺少 URL"

    try:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; mini-harness)"},
        )
        response.raise_for_status()
    except Exception as e:
        return f"错误：抓取失败: {e}"

    text = response.text
    text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()

    if len(text) > 4000:
        text = text[:4000] + "\n...[内容过长，已截断]"
    if not text:
        return "错误：页面内容为空（可能是动态渲染的网页）"
    return text

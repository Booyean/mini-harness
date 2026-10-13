import base64
import json
import os

from agent.context import clean_output
from tools.filesystem import _safe_path

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_SIZE = 2 * 1024 * 1024
MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_client = None


def set_client(client):
    global _client
    _client = client


def _load_image(path_str):
    path = _safe_path(path_str)
    if path is None:
        return None, "错误：路径超出工作目录范围"
    if not os.path.exists(path):
        return None, f"错误：文件不存在: {path_str}"
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXTS:
        return None, f"错误：不支持的图片格式 {ext}（支持 png/jpg/webp/gif）"
    size = os.path.getsize(path)
    if size > MAX_SIZE:
        return None, f"错误：图片过大（{size // 1024}KB，上限 2MB），请先压缩"
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    return {
        "path": path_str,
        "data_uri": f"data:{MIME_MAP[ext]};base64,{b64}",
    }, None


READ_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_image",
        "description": "查看图片内容（整图视觉理解）。用于看懂截图、UI 设计图、图表等非纯文字图片",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "图片路径（相对工作目录），如 'screenshot.png'",
                },
            },
            "required": ["path"],
        },
    },
}

OCR_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "ocr_image",
        "description": "提取图片中的全部文字（OCR）。只关心图中文字时用它，比 read_image 省得多",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "图片路径（相对工作目录）",
                },
            },
            "required": ["path"],
        },
    },
}


def execute_read_image(arguments):
    img, err = _load_image(str(arguments.get("path", "")))
    if err:
        return err
    return json.dumps(
        {"__image__": True, "path": img["path"], "data_uri": img["data_uri"]},
        ensure_ascii=False,
    )


def execute_ocr_image(arguments):
    img, err = _load_image(str(arguments.get("path", "")))
    if err:
        return err
    if _client is None:
        return "错误：OCR 未配置"
    try:
        response = _client.chat(
            [
                {
                    "role": "system",
                    "content": "你是 OCR 提取器。提取图片中的全部文字，"
                    "保持原有格式和顺序。图中没有文字就回复「（图中无文字）」。",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "提取这张图片中的所有文字："},
                        {
                            "type": "image_url",
                            "image_url": {"url": img["data_uri"]},
                        },
                    ],
                },
            ],
            max_tokens=2000,
            temperature=0.2,
        )
    except Exception as e:
        return f"错误：OCR 失败: {e}"
    return clean_output(response["content"] or "") or "（图中无文字）"

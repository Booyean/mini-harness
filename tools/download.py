import os
import tarfile
import zipfile

import requests

from tools.filesystem import _safe_path

DOWNLOAD_TOOL = {
    "type": "function",
    "function": {
        "name": "download_file",
        "description": "从 URL 下载文件到工作目录，zip/tar.gz 自动解压",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "下载地址",
                },
                "path": {
                    "type": "string",
                    "description": "保存路径（相对工作目录），默认用 URL 文件名",
                },
            },
            "required": ["url"],
        },
    },
}


def _extract_archive(path):
    directory = os.path.splitext(path)[0]
    if path.endswith(".tar.gz") or path.endswith(".tgz"):
        directory = path[:-7] if path.endswith(".tar.gz") else path[:-4]
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            zf.extractall(directory)
        return directory
    if path.endswith(".tar.gz") or path.endswith(".tgz"):
        with tarfile.open(path) as tf:
            tf.extractall(directory)
        return directory
    return None


def execute_download_file(arguments):
    url = str(arguments.get("url", "")).strip()
    if not url:
        return "错误：缺少 URL"

    default_name = os.path.basename(url.split("?")[0]) or "download.bin"
    path = _safe_path(str(arguments.get("path", "") or default_name))
    if path is None:
        return "错误：路径超出工作目录范围"

    try:
        response = requests.get(
            url,
            timeout=120,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; mini-harness)"},
        )
        response.raise_for_status()
    except Exception as e:
        return f"错误：下载失败: {e}"

    try:
        total = 0
        with open(path, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                f.write(chunk)
                total += len(chunk)
    except Exception as e:
        return f"错误：写入失败: {e}"

    result = f"已下载 {os.path.basename(path)}（{total} 字节）"

    try:
        extracted = _extract_archive(path)
    except Exception as e:
        return result + f"\n（解压失败: {e}，文件已保留）"
    if extracted:
        result += f"\n已自动解压到 {os.path.basename(extracted)}/"
    return result

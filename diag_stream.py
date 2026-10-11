import json
import os

import yaml

from model.client import Client
from tools import registry

cfg = yaml.safe_load(open("config/config.yaml", encoding="utf-8"))
client = Client(
    api_key=os.environ["OPENAI_API_KEY"],
    model=cfg["model"]["name"],
    base_url=cfg["openai"].get("base_url"),
)

msgs = [
    {"role": "system", "content": "你是助手，使用工具完成文件操作。"},
    {
        "role": "user",
        "content": "创建一个 layout.html 文件，内容是一个完整的 HTML 页面，"
        "包含导航栏、暗色模式切换按钮、SEO meta 标签，大约 150 行。",
    },
]

stream = client.create_stream(
    msgs, tools=registry.get_tool_schemas(), max_tokens=8192
)
acc = {}
for chunk in stream:
    if not chunk.choices:
        continue
    delta = chunk.choices[0].delta
    fr = chunk.choices[0].finish_reason
    if fr:
        print("finish_reason:", fr)
    if delta.content:
        print("TEXT:", repr(delta.content[:60]))
    if delta.tool_calls:
        for tc in delta.tool_calls:
            i = tc.index
            if i not in acc:
                acc[i] = {"id": None, "name": None, "args": ""}
            if tc.id:
                acc[i]["id"] = tc.id
            if tc.function and tc.function.name:
                acc[i]["name"] = tc.function.name
            if tc.function and tc.function.arguments:
                piece = tc.function.arguments
                acc[i]["args"] += piece
                print(f"ARG piece[{i}] len={len(piece)}: {repr(piece[:60])}")

for i, a in sorted(acc.items()):
    print(f"=== tool {i}: {a['name']}, args total len={len(a['args'])}")
    try:
        parsed = json.loads(a["args"])
        print("JSON OK, keys:", list(parsed.keys()))
        print("content len:", len(parsed.get("content", "")))
    except Exception as e:
        print("JSON FAIL:", e)
        print("raw head:", repr(a["args"][:300]))

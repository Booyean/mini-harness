import json
import os

import yaml

from model.client import Client
from tools import registry


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    config = load_config()
    model_cfg = config["model"]
    api_key = os.environ.get(config["openai"]["api_key_env"])
    if not api_key:
        print(f"缺少 API Key，请设置环境变量 {config['openai']['api_key_env']}")
        return

    client = Client(
        api_key=api_key,
        model=model_cfg["name"],
        base_url=config["openai"].get("base_url"),
    )

    messages = [
        {"role": "system", "content": "你是一个简洁的助手，需要计算时使用 calculator 工具"},
        {"role": "user", "content": "3 加 5 乘以 2 等于多少？"},
    ]

    print("=== 第 1 轮：递菜单，模型决定是否点单 ===")
    r1 = client.chat(
        messages,
        tools=registry.get_tool_schemas(),
        temperature=model_cfg["temperature"],
        max_tokens=model_cfg["max_tokens"],
    )
    print(f"[finish_reason={r1['finish_reason']}]")

    if r1["finish_reason"] != "tool_calls" or not r1["tool_calls"]:
        print(f"模型直接回答：{r1['content']}")
        return

    tool_call = r1["tool_calls"][0]
    name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments)
    print(f"[模型点单] 工具: {name} | 参数: {arguments}")

    messages.append(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            ],
        }
    )

    print("\n=== 第 2 步：我们真正执行工具 ===")
    result = registry.execute_tool(name, arguments)
    print(f"[工具结果] {result}")

    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result,
        }
    )

    print("\n=== 第 2 轮：上菜，模型总结 ===")
    r2 = client.chat(
        messages,
        temperature=model_cfg["temperature"],
        max_tokens=model_cfg["max_tokens"],
    )
    print(f"[finish_reason={r2['finish_reason']}]")
    print(r2["content"])


if __name__ == "__main__":
    main()

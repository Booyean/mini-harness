import os

import yaml

from model.client import Client


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ask(client, tools, label):
    messages = [
        {"role": "system", "content": "你是一个助手，需要时使用工具"},
        {"role": "user", "content": "3+5 等于多少？"},
    ]
    r = client.chat(messages, tools=tools, temperature=0, max_tokens=512)
    print(f"--- {label} ---")
    print(f"finish_reason = {r['finish_reason']}")
    if r["tool_calls"]:
        for tc in r["tool_calls"]:
            print(f"模型调用了: {tc.function.name}，参数 = {tc.function.arguments}")
    else:
        print(f"模型直接回答: {r['content']}")
    print()


def main():
    config = load_config()
    model_cfg = config["model"]
    api_key = os.environ.get(config["openai"]["api_key_env"])
    if not api_key:
        print("缺少 API Key")
        return

    client = Client(
        api_key=api_key,
        model=model_cfg["name"],
        base_url=config["openai"].get("base_url"),
    )

    meaningful = {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    }
    meaningless = {
        "type": "function",
        "function": {
            "name": "tool_xyz",
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {"arg": {"type": "string"}},
                "required": ["arg"],
            },
        },
    }

    ask(client, [meaningless, meaningful], "场景 A：两个工具都没描述，看模型选谁")
    ask(client, [meaningless], "场景 B：只有无意义名字的工具")


if __name__ == "__main__":
    main()

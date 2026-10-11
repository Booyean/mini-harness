import os

import yaml

from agent.loop import run_loop
from model.client import Client


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

    print("########## 任务 1：多轮计算 ##########")
    messages = [
        {"role": "system", "content": "你是一个助手，需要计算时使用 calculator 工具"},
        {"role": "user", "content": "请计算 12*3 和 12+3 的结果，然后告诉我它们的差，尽量多调用工具"},
    ]
    content, rounds = run_loop(client, messages, max_iterations=5, verbose=True)
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")

    print("\n########## 任务 2：错误自纠 ##########")
    messages = [
        {"role": "system", "content": "你是一个助手，需要计算时使用 calculator 工具"},
        {"role": "user", "content": "帮我计算 abc+3 等于多少"},
    ]
    content, rounds = run_loop(client, messages, max_iterations=5, verbose=True)
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")


if __name__ == "__main__":
    main()

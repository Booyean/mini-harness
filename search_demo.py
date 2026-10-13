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

    print("########## 任务：搜索并总结 ##########")
    messages = [
        {"role": "system", "content": "你是一个助手，需要时使用工具，用中文回答"},
        {"role": "user", "content": "搜索一下 目前游戏文明七的价格，和史低，用一两句话总结"},
    ]
    content, rounds = run_loop(client, messages, max_iterations=5, verbose=True)
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")


if __name__ == "__main__":
    main()

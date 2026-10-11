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

    print("########## 任务 1：只读工具（应自动放行，无审批） ##########")
    messages = [
        {"role": "system", "content": "你是一个助手，需要时使用工具"},
        {"role": "user", "content": "读一下 config/config.yaml"},
    ]
    content, rounds = run_loop(client, messages, max_iterations=5, verbose=True)
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")

    print("\n########## 任务 2：写文件（弹审批，管道输入 y） ##########")
    messages = [
        {"role": "system", "content": "你是一个助手，需要时使用工具"},
        {"role": "user", "content": "创建 approval_test.txt，内容为 hello"},
    ]
    content, rounds = run_loop(client, messages, max_iterations=5, verbose=True)
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")

    print("\n########## 任务 3：写文件被拒绝（管道输入 n） ##########")
    messages = [
        {"role": "system", "content": "你是一个助手，需要时使用工具"},
        {"role": "user", "content": "把 approval_test.txt 的内容改成 world"},
    ]
    content, rounds = run_loop(client, messages, max_iterations=5, verbose=True)
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")


if __name__ == "__main__":
    main()

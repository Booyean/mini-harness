import os

import yaml

from agent.loop import run_loop
from model.client import Client
from tools.shell import execute_run_bash


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

    print("########## 任务 0：高危命令黑名单演示（不经过模型） ##########")
    print(execute_run_bash({"command": "rm -rf ."}))
    print(execute_run_bash({"command": "shutdown /s"}))
    print()

    print("########## 任务 1：列出目录 ##########")
    messages = [
        {"role": "system", "content": "你是一个助手，需要时使用工具"},
        {"role": "user", "content": "列出当前项目目录下有哪些文件和文件夹"},
    ]
    content, rounds = run_loop(client, messages, max_iterations=5, verbose=True)
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")

    print("\n########## 任务 2：查看 Python 版本 ##########")
    messages = [
        {"role": "system", "content": "你是一个助手，需要时使用工具"},
        {"role": "user", "content": "用命令查看 python 版本"},
    ]
    content, rounds = run_loop(client, messages, max_iterations=5, verbose=True)
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")

    print("\n########## 任务 3：运行 hello.py ##########")
    messages = [
        {"role": "system", "content": "你是一个助手，需要时使用工具"},
        {"role": "user", "content": "运行 hello.py 并告诉我输出了什么"},
    ]
    content, rounds = run_loop(client, messages, max_iterations=5, verbose=True)
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")


if __name__ == "__main__":
    main()

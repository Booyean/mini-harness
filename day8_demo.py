import os

import yaml

from agent.context import count_messages_tokens, trim_messages
from agent.loop import run_loop
from model.client import Client


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def demo_pure_function():
    print("########## 演示 1：纯函数裁剪（不调 API） ##########")
    messages = [{"role": "system", "content": "你是助手"}]
    for i in range(20):
        messages.append({"role": "user", "content": f"第 {i} 轮问题 " + "x" * 80})
        messages.append({"role": "assistant", "content": "y" * 60})

    before = count_messages_tokens(messages)
    print(f"裁剪前：{len(messages)} 条消息，{before} tokens")

    trimmed = trim_messages(messages, max_tokens=500)
    after = count_messages_tokens(trimmed)
    print(f"裁剪后：{len(trimmed)} 条消息，{after} tokens")
    print(f"system 保留：{trimmed[0] == messages[0]}")
    print(f"剩余第一条用户消息：'{trimmed[1]['content'][:20]}...'")
    print()


def demo_real_loop():
    print("########## 演示 2：真实 loop 里自动裁剪 ##########")
    config = load_config()
    model_cfg = config["model"]
    api_key = os.environ.get(config["openai"]["api_key_env"])
    if not api_key:
        print("缺少 API Key，跳过")
        return

    client = Client(
        api_key=api_key,
        model=model_cfg["name"],
        base_url=config["openai"].get("base_url"),
    )

    messages = [{"role": "system", "content": "你是助手，需要时使用工具"}]
    for i in range(10):
        messages.append({"role": "user", "content": f"历史问题 {i} " + "z" * 100})
        messages.append({"role": "assistant", "content": "w" * 80})

    print(f"构造了 {len(messages)} 条历史消息，"
          f"共 {count_messages_tokens(messages)} tokens")
    print(f"预算设为 500 tokens，观察裁剪：\n")

    messages.append({"role": "user", "content": "用工具计算 3+5"})
    content, rounds = run_loop(
        client,
        messages,
        max_iterations=3,
        max_context_tokens=500,
        verbose=True,
    )
    print(f"\n[共 {rounds} 轮] 最终回答：{content}")
    print(f"裁剪后主列表剩余 {len(messages)} 条消息")


if __name__ == "__main__":
    demo_pure_function()
    demo_real_loop()

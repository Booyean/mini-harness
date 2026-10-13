import time

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

MAX_RETRIES = 3
RETRIABLE_ERRORS = (APITimeoutError, APIConnectionError, RateLimitError)


class Client:
    def __init__(self, api_key, model, base_url=None, max_retries=MAX_RETRIES):
        self.model = model
        self.max_retries = max_retries
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages, temperature=0, max_tokens=4096, tools=None):
        for attempt in range(self.max_retries):
            try:
                return self._chat_once(messages, temperature, max_tokens, tools)
            except RETRIABLE_ERRORS:
                if attempt == self.max_retries - 1:
                    raise
                wait = 2 ** attempt
                print(f"[网络重试] 第 {attempt + 1} 次失败，{wait} 秒后重试...")
                time.sleep(wait)

    def create_stream(self, messages, temperature=0, max_tokens=1024, tools=None):
        for attempt in range(self.max_retries):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                if tools is not None:
                    kwargs["tools"] = tools
                return self._client.chat.completions.create(**kwargs)
            except RETRIABLE_ERRORS:
                if attempt == self.max_retries - 1:
                    raise
                wait = 2 ** attempt
                print(f"[网络重试] 第 {attempt + 1} 次失败，{wait} 秒后重试...")
                time.sleep(wait)

    def _chat_once(self, messages, temperature, max_tokens, tools):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools is not None:
            kwargs["tools"] = tools
        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        return {
            "content": choice.message.content,
            "tool_calls": choice.message.tool_calls,
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

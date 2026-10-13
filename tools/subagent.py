SUBAGENT_PROMPT = (
    "你是 mini-harness 的子代理，负责完成一个独立的子任务。"
    "你可以使用工具：读文件（read_file）、写文件（write_file）、"
    "修改文件（edit_file）、执行命令（run_bash）、联网搜索（web_search）、"
    "维护任务清单（update_todo）。"
    "多步骤任务先用 update_todo 建清单，逐步完成。"
    "完成后简洁汇报：做了什么、改了哪些文件、结果如何。中文回复。"
)

RUN_SUBTASK_TOOL = {
    "type": "function",
    "function": {
        "name": "run_subtask",
        "description": "把独立子任务交给子代理（干净上下文执行），完成后返回结果摘要。"
        "适合需读多文件的多步子任务，避免主上下文被细节撑爆",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "子任务的详细描述（含目标、涉及的文件、完成标准）",
                },
            },
            "required": ["task"],
        },
    },
}

_client = None
_depth = 0


class _SilentBus:
    def on(self, *args, **kwargs):
        pass

    def emit(self, *args, **kwargs):
        pass


def set_client(client):
    global _client
    _client = client


def execute_run_subtask(arguments):
    global _depth
    task = str(arguments.get("task", "")).strip()
    if not task:
        return "错误：子任务描述为空"
    if _client is None:
        return "错误：子代理未配置"
    if _depth >= 1:
        return "错误：子任务中不能再次派生子任务"

    _depth += 1
    try:
        from agent.loop import run_loop
        from tools import todo

        main_todos = todo.load_todos()

        try:
            sub_messages = [
                {"role": "system", "content": SUBAGENT_PROMPT},
                {"role": "user", "content": task},
            ]
            content, rounds = run_loop(
                _client,
                sub_messages,
                max_iterations=30,
                max_context_tokens=64000,
                max_tokens=65536,
                temperature=0.3,
                events=_SilentBus(),
                stall_limit=5,
            )
        finally:
            todo.save_todos(main_todos)
        return f"子任务完成（{rounds} 轮）：\n{content}"
    except Exception as e:
        return f"子任务失败: {e}"
    finally:
        _depth -= 1

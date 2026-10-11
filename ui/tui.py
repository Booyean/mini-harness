from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from agent.events import DEFAULT_BUS

console = Console()


def setup_console():
    DEFAULT_BUS.on("text", _on_text)
    DEFAULT_BUS.on("tool_call", _on_tool_call)
    DEFAULT_BUS.on("tool_result", _on_tool_result)
    DEFAULT_BUS.on("context_trimmed", _on_context_trimmed)
    DEFAULT_BUS.on("compact_start", _on_compact_start)
    DEFAULT_BUS.on("assistant_done", _on_assistant_done)


def render_banner(model, session_id, work_dir=None, title=None):
    console.print("=" * 50)
    console.print("[bold cyan]mini-harness[/] 已启动")
    if title:
        console.print(f"会话标题: [bold green]{title}[/]")
    console.print(f"模型: [yellow]{model}[/] | 会话: [yellow]{session_id}[/]")
    if work_dir:
        console.print(f"工作目录: [yellow]{work_dir}[/]")
    console.print("输入 [bold]exit[/] / [bold]quit[/] 退出（自动保存）")
    console.print("=" * 50)


def render_user_prompt():
    console.print("\n[bold blue]You:[/] ", end="")


def render_agent_prompt():
    console.print("\n[bold magenta]Agent:[/] ", end="")


def clear_screen():
    console.clear()


def render_slash_help():
    console.print("[bold]可用命令：[/]")
    console.print("  [cyan]/help[/]      显示本帮助")
    console.print("  [cyan]/list[/]      列出存档会话（含标题）")
    console.print("  [cyan]/name[/]      给当前会话命名，如 /name 博客改造")
    console.print("  [cyan]/model[/]     显示/切换模型")
    console.print("  [cyan]/allow[/]     会话放行某工具（如 /allow write_file）")
    console.print("  [cyan]/deny[/]      会话禁止某工具")
    console.print("  [cyan]/tokens[/]    显示当前上下文 token 数")
    console.print("  [cyan]/memory[/]    查看长期记忆（add 追加偏好）")
    console.print("  [cyan]/clear[/]     清屏")
    console.print("  [cyan]!![/]         重放上次输入")
    console.print("  [cyan]exit[/]       退出（询问是否保存）")


def _on_text(content):
    console.print(content, end="", highlight=False, markup=False)


def _on_tool_call(name, arguments):
    console.print()
    console.print(
        Panel(
            f"[bold cyan]工具调用[/] [yellow]{name}[/]\n参数: {arguments}",
            border_style="cyan",
            padding=(0, 1),
        )
    )


def _on_tool_result(name, result, diff=None):
    if name == "update_todo":
        console.print(
            Panel(
                result,
                title="任务清单",
                border_style="blue",
                padding=(0, 1),
            )
        )
        return
    if diff:
        _render_diff(diff)
    console.print(
        Panel(
            f"[bold green]结果[/] {result}",
            border_style="green",
            padding=(0, 1),
        )
    )


def _render_diff(diff_text):
    text = Text()
    for line in diff_text.splitlines():
        if line.startswith("+"):
            style = "green"
        elif line.startswith("-"):
            style = "red"
        elif line.startswith("@@"):
            style = "cyan"
        else:
            style = "dim"
        text.append(line, style=style)
        text.append("\n")
    console.print(
        Panel(text, title="文件改动", border_style="yellow", padding=(0, 1))
    )


def _on_compact_start():
    console.print("[dim]正在压缩历史对话...[/]")


def _on_context_trimmed(before, after, compacted=False):
    action = "压缩" if compacted else "裁剪"
    console.print(f"[dim][上下文{action}] {before} -> {after} 条[/]")


def _on_assistant_done(content, rounds, context_tokens):
    console.print()
    console.print(
        f"[dim][共 {rounds} 轮 | 上下文约 {context_tokens} tokens][/]"
    )

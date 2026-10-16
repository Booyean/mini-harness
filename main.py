import os
import re
import sys

import yaml

from agent.loop import run_loop
from agent.session import (
    commit_session,
    discard_session,
    find_session_by_title,
    list_sessions,
    load_session,
    new_session_id,
    save_session,
)
from model.client import Client
from tools import mcp, registry, subagent, todo, vision
from tools.filesystem import _safe_path, set_work_dir
from ui import tui

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_PROMPT = (
    "你是 mini-harness，一个终端编程助手。"
    "你可以使用工具来：计算数学表达式（calculator）、"
    "读文件（read_file）、创建或覆盖文件（write_file）、"
    "修改文件某一行（edit_file）、执行 shell 命令（run_bash）、"
    "联网搜索（web_search）、维护任务清单（update_todo）、"
    "派生子代理执行独立子任务（run_subtask）、"
    "查看图片（read_image，整图理解）或提取图中文字（ocr_image，更省）。"
    "规则：需要操作文件或执行命令时，必须直接调用对应工具，"
    "不要只输出计划或承诺性文字（如“我这就动手”）。"
    "交互规则：调用工具前先输出一句话说明当前意图（简短，20 字内）；"
    "每批工具执行完成后，用一两句话播报进展和下一步，"
    "让用户能跟上你的思路，不要一直沉默地连续调用工具。"
    "修改文件用 edit_file 的 old_string 方式：先 read_file 拿到原文，"
    "再用唯一匹配的原文片段定位替换，不要凭记忆用行号。"
    "处理多步骤任务时，先用 update_todo 建立任务清单，"
    "大任务拆成主任务和子任务（subtasks）两层结构，"
    "每完成一步立即更新清单状态，防止遗忘进度。"
    "回答要简洁，中文回复。"
    "尽力去满足用户的需求，工具够用。"
    "重要止损规则："
    "1) 同一验证操作失败 3 次，必须停止重复尝试，"
    "用 ask_user 向用户汇报：已尝试什么、失败模式、你的诊断、"
    "建议用户在其真实环境验证什么。等待用户决定，不要自行穷举。"
    "2) 发现同一操作结果时好时坏（随机波动），"
    "立即判断为环境问题，停止测试，汇报现象并请求协助。"
    "交付门禁规则："
    "1) 声称任务完成前，必须实际运行验证（测试/构建/语法检查），"
    "验证通过才算完成；失败不能声称完成，继续修或如实汇报。"
    "2) 写进文档或总结的任何实测结论（文件大小、运行结果、验证记录），"
    "必须当场重新验证，禁止引用记忆中之前看到的状态。"
    "3) 多文件改动收尾时，派 run_subtask 子代理以全新上下文审查一遍："
    "语法错误、死代码、文档与实现矛盾、文档自相矛盾。"
    "审查发现的问题修完再交付。"
    "另外，本终端支持以下用户命令（由 harness 直接处理，不需要工具）："
    "/name <标题> 给会话命名、/model 切换模型、/list 列出会话、"
    "/tokens 查看上下文用量、/memory 查看记忆、/clear 清屏、"
    "exit 退出。用户提到「改会话名」时，引导他使用 /name 命令。"
    "环境说明：当前运行在 Windows，run_bash 的 shell 是 cmd.exe。"
    "命令必须用 Windows 语法：dir（不是 ls）、type（不是 cat）、"
    "findstr（不是 grep）、if exist（不是 test -f）。"
    "不要使用 bash 专属语法（head、tail、nohup、$()、&& 换行等不可用；"
    "可以用 & 顺序执行、| 管道）。"
)


def load_config(path=None):
    path = path or os.path.join(BASE_DIR, "config", "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_client(model_item, fallback_key_env, fallback_base_url):
    return Client(
        api_key=os.environ.get(model_item.get("api_key_env", fallback_key_env)),
        model=model_item["name"],
        base_url=model_item.get("base_url", fallback_base_url),
    )


MEMORY_FILE = ".mini-harness.md"
GLOBAL_MEMORY_FILE = os.path.join(BASE_DIR, "user_memory.md")


def load_memory(work_dir):
    path = os.path.join(work_dir, MEMORY_FILE)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def append_memory(work_dir, text):
    path = os.path.join(work_dir, MEMORY_FILE)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + text.strip() + "\n")


def load_global_memory():
    if not os.path.exists(GLOBAL_MEMORY_FILE):
        return ""
    with open(GLOBAL_MEMORY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def append_global_memory(text):
    with open(GLOBAL_MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + text.strip() + "\n")


def build_memory_block(work_dir):
    parts = []
    global_mem = load_global_memory()
    if global_mem:
        parts.append(f"用户偏好（全局记忆）：\n{global_mem}")
    project_mem = load_memory(work_dir)
    if project_mem:
        parts.append(f"项目约定（本目录 .mini-harness.md）：\n{project_mem}")
    return "\n\n".join(parts)


MEMORY_PROMPT = (
    "你是记忆提取器。分析对话，判断用户是否暴露了值得长期记住的"
    "【个人层面】偏好或习惯。"
    "只提炼：称呼偏好、语言偏好（中/英）、代码风格、命名习惯、"
    "工具偏好、回复风格偏好（简短/详细）、个人身份信息。"
    "绝对禁止提炼：项目任务内容、技术结论、开发理念、"
    "文件组织方式、工作流程建议——这些是任务信息，不是个人偏好。"
    "如果本次没有值得记住的个人偏好，只回复 NONE。"
    "有则用一行简洁中文（50 字内）描述，以「用户偏好：」开头。"
)


from agent.context import clean_output


def extract_preferences(client, user_msg, assistant_content):
    response = client.chat(
        [
            {"role": "system", "content": MEMORY_PROMPT},
            {
                "role": "user",
                "content": f"用户说：{user_msg[:1000]}\n\n"
                f"助手回答：{assistant_content[:800]}",
            },
        ],
        max_tokens=200,
        temperature=0.3,
    )
    return clean_output(response["content"] or "")


TITLE_PROMPT = (
    "给下面这段对话起一个简短的中文标题（3-12 字），"
    "概括对话主题。只返回标题本身，不要引号、不要解释。"
)


def generate_title(client, user_msg, assistant_content):
    response = client.chat(
        [
            {"role": "system", "content": TITLE_PROMPT},
            {
                "role": "user",
                "content": f"用户说：{user_msg[:500]}\n\n"
                f"助手回答：{assistant_content[:300]}",
            },
        ],
        max_tokens=200,
        temperature=0.3,
    )
    return clean_output(response["content"] or "")


AT_REF_PATTERN = re.compile(r"@([\w./\\-]+)")


def expand_at_refs(user_input):
    blocks = []
    refs = []

    def repl(m):
        name = m.group(1)
        path = _safe_path(name)
        if path and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                content = "".join(lines[:200])
                blocks.append(f"[引用文件 {name}]\n{content}\n[引用结束]")
                refs.append(name)
                return ""
            except OSError:
                pass
        return m.group(0)

    expanded = AT_REF_PATTERN.sub(repl, user_input)
    if blocks:
        expanded = "\n\n".join(blocks) + f"\n\n用户问题：{expanded.strip()}"
    return expanded, refs


def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print("用法: py -3.13 main.py [参数]")
        print("  （无参数）    开始新会话，在当前目录工作")
        print("  --dir 路径   指定工作目录（agent 只能操作该目录内文件）")
        print("  --list       列出已有会话")
        print("  --resume ID  恢复指定会话继续对话")
        print("  --help       显示本帮助")
        return

    if "--list" in args:
        sessions = list_sessions()
        if sessions:
            print("已有会话：")
            for s_id, s_title in sessions:
                print(f"  {s_id}  {s_title}")
        else:
            print("暂无存档会话")
        return

    work_dir = os.getcwd()
    if "--dir" in args:
        idx = args.index("--dir")
        if idx + 1 < len(args):
            work_dir = args[idx + 1]
    set_work_dir(work_dir)

    resume_id = None
    if "--resume" in args:
        idx = args.index("--resume")
        if idx + 1 < len(args):
            resume_id = args[idx + 1]

    config = load_config()
    model_cfg = config["model"]
    fallback_key_env = config["openai"]["api_key_env"]
    fallback_base_url = config["openai"].get("base_url")

    models_cfg = config.get("models") or [
        {
            "name": model_cfg["name"],
            "api_key_env": fallback_key_env,
            "base_url": fallback_base_url,
        }
    ]

    client = None
    first_model = models_cfg[0]
    key_env = first_model.get("api_key_env", fallback_key_env)
    if not os.environ.get(key_env):
        print("=" * 50)
        print("[错误] 缺少 API Key！")
        print(f"请在环境变量 {key_env} 中配置你的 DeepSeek Key：")
        print()
        print(f"  临时设置（仅当前终端窗口有效）：")
        print(f'  $env:{key_env} = "sk-你的Key"')
        print()
        print(f"  永久设置（重开终端窗口后生效）：")
        print(f'  setx {key_env} "sk-你的Key"')
        print()
        print("设置完成后重新运行：py -3.13 main.py")
        print("=" * 50)
        return

    client = build_client(first_model, fallback_key_env, fallback_base_url)
    subagent.set_client(client)
    vision.set_client(client)

    for server_cmd in config.get("mcp_servers", []):
        servers = mcp.load_servers([server_cmd])
        for cmd, server in servers.items():
            server_name = os.path.basename(cmd.split()[-1])
            server_name = server_name.replace(".py", "").replace("-", "_")
            for tool in server.tools:
                schema = mcp.mcp_tool_to_schema(server_name, tool)
                tool_name = schema["function"]["name"]
                registry.register_dynamic(
                    tool_name, mcp.make_executor(server, tool["name"]), schema
                )
                print(f"[MCP] 已注册工具: {tool_name} (来自 {cmd})")

    if resume_id:
        data = load_session(resume_id)
        if data is None:
            matched = find_session_by_title(resume_id)
            if matched:
                data = load_session(matched)
                resume_id = matched
        if data is None:
            print(f"会话 {resume_id} 不存在，可用 --list 查看")
            return
        session_id = resume_id
        session_title = data.get("title")
        messages = data["messages"]
        todo_snapshot = data.get("todo_snapshot")
        if todo_snapshot is not None:
            todo.save_todos(todo_snapshot)
            if todo_snapshot:
                print(f"[已恢复任务清单（{len(todo_snapshot)} 项）]")
        memory_block = build_memory_block(work_dir)
        if messages and messages[0]["role"] == "system":
            if memory_block and memory_block not in messages[0]["content"]:
                messages[0]["content"] += f"\n\n{memory_block}"
    else:
        session_id = new_session_id()
        session_title = None
        todo.save_todos([])
        memory_block = build_memory_block(work_dir)
        system_content = SYSTEM_PROMPT
        if memory_block:
            system_content += f"\n\n{memory_block}"
        messages = [{"role": "system", "content": system_content}]

    history = []
    stall_rounds = 0

    tui.setup_console()
    tui.render_banner(client.model, session_id, work_dir, session_title)

    while True:
        tui.render_user_prompt()
        try:
            user_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            save_session(
                session_id,
                messages,
                model_cfg["name"],
                session_title,
                todo.load_todos(),
            )
            commit_session(session_id)
            print(f"\n已保存会话 {session_id}，再见！")
            break

        if not user_input:
            continue

        if user_input == "!!":
            if history:
                user_input = history[-1]
                print(f"(重放: {user_input})")
            else:
                print("暂无输入历史")
                continue

        if user_input.startswith("/"):
            result = handle_slash_command(
                user_input,
                client,
                messages,
                work_dir,
                models_cfg,
                fallback_key_env,
                fallback_base_url,
                session_title,
            )
            if result:
                new_client, new_title = result
                if new_client is not None:
                    client = new_client
                    subagent.set_client(client)
                if new_title is not None:
                    session_title = new_title
                    save_session(
                        session_id,
                        messages,
                        model_cfg["name"],
                        session_title,
                        todo.load_todos(),
                    )
            continue

        if user_input.lower() in ("exit", "quit", "退出"):
            while True:
                answer = input("保存本次对话？(y/n) ").strip().lower()
                if answer in ("y", "yes"):
                    save_session(
                        session_id,
                        messages,
                        model_cfg["name"],
                        session_title,
                        todo.load_todos(),
                    )
                    commit_session(session_id)
                    print(f"已保存会话 {session_id}，再见！")
                    break
                if answer in ("n", "no"):
                    discard_session(session_id)
                    print("本次对话未保存，再见！")
                    break
                print("请输入 y 或 n")
            break

        expanded, refs = expand_at_refs(user_input)
        if refs:
            print(f"[已引用 {len(refs)} 个文件]")
        messages.append({"role": "user", "content": expanded})
        history.append(user_input)
        if len(history) > 50:
            history = history[-50:]

        tui.render_agent_prompt()
        agent_cfg = config.get("agent", {})
        before_len = len(messages)
        try:
            content, rounds = run_loop(
                client,
                messages,
                max_iterations=agent_cfg.get("max_iterations", 5),
                max_context_tokens=agent_cfg.get("max_context_tokens"),
                max_tokens=model_cfg.get("max_tokens", 4096),
                temperature=model_cfg.get("temperature", 0.3),
                verbose=False,
            )
        except KeyboardInterrupt:
            print("\n[已中断，可继续输入]")
            messages.append(
                {"role": "assistant", "content": "（生成被用户中断）"}
            )
            continue
        except Exception as e:
            print(f"\n[错误] 请求失败: {e}")
            print("请检查网络或 API Key，可继续输入重试")
            continue

        tool_msgs = [
            m
            for m in messages[before_len:]
            if m.get("role") == "tool"
        ]
        if tool_msgs:
            failed = [
                m
                for m in tool_msgs
                if str(m.get("content", "")).startswith(("错误", "用户拒绝"))
            ]
            if len(failed) == len(tool_msgs):
                stall_rounds += 1
            else:
                stall_rounds = 0
            if stall_rounds >= 3:
                stall_rounds = 0
                messages.append(
                    {
                        "role": "user",
                        "content": "（系统提示：你已经连续多轮没有实质进展。"
                        "停止当前思路，重新评估：是否环境问题？"
                        "是否该向用户汇报并询问方向？不要继续重复相同的尝试。）",
                    }
                )
                print("[提示] 检测到连续无进展，已提醒模型止损")

        messages.append({"role": "assistant", "content": content})

        if session_title is None and not refs:
            try:
                session_title = generate_title(client, user_input, content)
                if not session_title:
                    session_title = user_input[:15]
                print(f"[会话命名] {session_title}")
            except Exception:
                session_title = user_input[:15]
                print(f"[会话命名] {session_title}")

        if not refs and not user_input.startswith("!"):
            try:
                pref = extract_preferences(client, user_input, content)
                if pref and pref != "NONE" and "none" not in pref.lower():
                    current_memory = load_global_memory()
                    if pref not in current_memory:
                        append_global_memory(pref)
                        print(f"[已记忆] {pref}（下次会话生效）")
            except Exception:
                pass

        save_session(
            session_id,
            messages,
            model_cfg["name"],
            session_title,
            todo.load_todos(),
        )


def handle_slash_command(
    cmd,
    client,
    messages,
    work_dir,
    models_cfg,
    fallback_key_env,
    fallback_base_url,
    session_title,
):
    parts = cmd.strip().split()
    name = parts[0].lower()

    if name == "/help":
        tui.render_slash_help()
    elif name == "/name":
        text = cmd.split(maxsplit=1)[1].strip() if len(parts) > 1 else ""
        if text:
            tui.console.print(f"[green]会话已命名：[/]{text}")
            return None, text
        tui.console.print(
            f"[yellow]当前标题：{session_title or '（未命名）'}[/]"
        )
        tui.console.print("用法：/name <标题>")
    elif name == "/list":
        sessions = list_sessions()
        if sessions:
            tui.console.print("[bold]已有会话：[/]")
            for s_id, s_title in sessions:
                tui.console.print(f"  {s_id}  [yellow]{s_title}[/]")
        else:
            tui.console.print("暂无存档会话")
    elif name == "/model":
        if len(parts) >= 2:
            target = parts[1]
            for item in models_cfg:
                if item["name"] == target:
                    target_key_env = item.get("api_key_env", fallback_key_env)
                    if not os.environ.get(target_key_env):
                        tui.console.print(
                            f"[red]缺少环境变量 {target_key_env}，无法切换到 {target}[/]"
                        )
                        return None
                    new_client = build_client(
                        item, fallback_key_env, fallback_base_url
                    )
                    tui.console.print(
                        f"[green]已切换到模型：[/]{target}"
                    )
                    return new_client, None
            tui.console.print(f"[red]模型 {target} 不在配置中[/]")
            tui.console.print(
                "可用模型：" + "、".join(m["name"] for m in models_cfg)
            )
        else:
            tui.console.print(f"当前模型: [yellow]{client.model}[/]")
            tui.console.print(
                "可用模型：" + "、".join(m["name"] for m in models_cfg)
            )
            tui.console.print("切换：/model <模型名>")
    elif name == "/tokens":
        from agent.context import count_messages_tokens

        total = count_messages_tokens(messages)
        tui.console.print(
            f"当前上下文约 [yellow]{total}[/] tokens"
            f"（预算 {load_config().get('agent', {}).get('max_context_tokens', '无')}）"
        )
    elif name == "/memory":
        if len(parts) >= 3 and parts[1].lower() == "add":
            text = cmd.split(maxsplit=2)[2] if len(parts) > 2 else ""
            if text:
                append_memory(work_dir, text)
                tui.console.print(f"[green]已追加项目记忆：[/]{text}")
            else:
                tui.console.print("[red]用法：/memory add <内容>[/]")
        else:
            global_mem = load_global_memory()
            project_mem = load_memory(work_dir)
            if global_mem:
                tui.console.print("[bold]全局记忆（user_memory.md，跨项目）：[/]")
                tui.console.print(global_mem)
            if project_mem:
                tui.console.print(
                    f"[bold]项目记忆（{MEMORY_FILE}，本目录）：[/]"
                )
                tui.console.print(project_mem)
            if not global_mem and not project_mem:
                tui.console.print("暂无记忆。用 /memory add <内容> 添加项目偏好")
    elif name == "/clear":
        tui.clear_screen()
    elif name in ("/allow", "/deny"):
        from agent import permissions as perms

        if len(parts) >= 2:
            tool_name = parts[1]
            allowed = name == "/allow"
            perms.set_rule(tool_name, allowed)
            tui.console.print(
                f"[green]{tool_name} 本次会话{'放行' if allowed else '禁止'}[/]"
            )
        else:
            rules = perms.get_rules()
            if rules:
                tui.console.print("[bold]当前会话规则：[/]")
                for t, ok in rules.items():
                    tui.console.print(
                        f"  {t}: {'放行' if ok else '禁止'}"
                    )
            else:
                tui.console.print("暂无会话规则。用法：/allow <工具名> 或 /deny <工具名>")
    else:
        tui.console.print(f"[red]未知命令[/] {name}，输入 /help 查看可用命令")
    return None


if __name__ == "__main__":
    main()

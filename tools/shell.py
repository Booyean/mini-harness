import os
import re
import subprocess
import tempfile

from tools import filesystem

TIMEOUT = 30
MAX_OUTPUT = 4000

BLOCKED_PATTERN = re.compile(
    r"\b(rm|rmdir|del|erase|rd|format|shutdown|mkfs|diskpart)\b"
    r"|taskkill\b[^&|]*\/IM\s+(python|python3|node|cmd)\b",
    re.IGNORECASE,
)

LONG_RUNNING_PATTERNS = [
    r"npm\s+(run\s+)?(dev|start|preview|serve)",
    r"npx\s+\S+\s+(dev|preview)",
    r"pnpm\s+(dev|start|preview)",
    r"yarn\s+(dev|start|preview)",
    r"node\s+\S+\.(js|mjs|cjs)",
    r"python3?\s+-m\s+http\.server",
    r"py\s+-3\S*\s+-m\s+http\.server",
    r"\bvite\b",
    r"astro\s+dev",
    r"\buvicorn\b",
    r"flask\s+run",
    r"django\s+runserver",
    r"next\s+dev",
    r"\bgunicorn\b",
]


def _is_long_running(command):
    return any(
        re.search(pattern, command, re.IGNORECASE)
        for pattern in LONG_RUNNING_PATTERNS
    )

RUN_BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "run_bash",
        "description": "执行 shell 命令并返回输出（Windows cmd 语法）",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令",
                }
            },
            "required": ["command"],
        },
    },
}


def _decode_output(data):
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def execute_run_bash(arguments):
    command = str(arguments.get("command", ""))
    if not command.strip():
        return "错误：命令为空"
    if BLOCKED_PATTERN.search(command):
        return "错误：命令包含高危操作（删除/格式化/关机），已禁止执行"

    if _is_long_running(command):
        return _run_in_background(command)

    out_file = tempfile.TemporaryFile()
    err_file = tempfile.TemporaryFile()
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=filesystem.WORK_DIR,
        stdin=subprocess.DEVNULL,
        stdout=out_file,
        stderr=err_file,
    )
    try:
        proc.wait(timeout=TIMEOUT)
        out_file.seek(0)
        stdout = _decode_output(out_file.read())
        err_file.seek(0)
        stderr = _decode_output(err_file.read())
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        try:
            subprocess.run(
                f"taskkill /F /T /PID {proc.pid}",
                shell=True,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass
        return (
            f"错误：命令执行超时（超过 {TIMEOUT} 秒），"
            f"已按 PID 终止该命令及其子进程"
        )
    except KeyboardInterrupt:
        try:
            subprocess.run(
                f"taskkill /F /T /PID {proc.pid}",
                shell=True,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=10,
            )
        except Exception:
            pass
        raise
    except Exception as e:
        return f"错误：命令执行失败: {e}"
    finally:
        out_file.close()
        err_file.close()

    parts = []
    if stdout.strip():
        if len(stdout) > MAX_OUTPUT:
            stdout = stdout[:MAX_OUTPUT] + "\n[输出过长，已截断]"
        parts.append(f"[stdout]\n{stdout}")
    if stderr.strip():
        if len(stderr) > MAX_OUTPUT:
            stderr = stderr[:MAX_OUTPUT] + "\n[输出过长，已截断]"
        parts.append(f"[stderr]\n{stderr}")
    if not parts:
        return f"命令执行完成，无输出（退出码 {returncode}）"
    return "\n".join(parts) + f"\n[退出码 {returncode}]"


def _run_in_background(command):
    log_path = os.path.join(filesystem.WORK_DIR, "run_bash.log")
    log = open(log_path, "a", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=filesystem.WORK_DIR,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return (
        f"检测到长驻命令（开发服务器类），已后台启动，PID {proc.pid}。"
        f"日志追加到 run_bash.log，"
        f"可执行 'type run_bash.log' 查看运行状态"
    )

import json
import subprocess


class MCPServer:
    def __init__(self, command):
        self.command = command
        self.proc = subprocess.Popen(
            command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._request_id = 0
        self.initialize()
        self.tools = self.list_tools()

    def _request(self, method, params=None):
        self._request_id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        try:
            self.proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
            raw = self.proc.stdout.readline()
            if not raw:
                raise RuntimeError("MCP server 无响应")
            return json.loads(raw.decode("utf-8", errors="replace"))
        except Exception as e:
            raise RuntimeError(f"MCP 请求失败: {e}")

    def initialize(self):
        return self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mini-harness", "version": "0.1.0"},
            },
        )

    def list_tools(self):
        resp = self._request("tools/list", {})
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name, arguments):
        resp = self._request(
            "tools/call", {"name": name, "arguments": arguments}
        )
        result = resp.get("result", {})
        parts = []
        for c in result.get("content", []):
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
        text = "\n".join(parts)
        if result.get("isError"):
            return "错误：" + text
        return text or "（无输出）"


def mcp_tool_to_schema(server_name, tool):
    return {
        "type": "function",
        "function": {
            "name": f"mcp_{server_name}_{tool['name']}",
            "description": tool.get("description", ""),
            "parameters": tool.get(
                "inputSchema", {"type": "object", "properties": {}}
            ),
        },
    }


def make_executor(server, tool_name):
    def executor(arguments):
        return server.call_tool(tool_name, arguments)

    return executor


def load_servers(commands):
    servers = {}
    for cmd in commands:
        try:
            server = MCPServer(cmd)
            servers[cmd] = server
        except Exception as e:
            print(f"[MCP] 启动失败 {cmd}: {e}")
    return servers

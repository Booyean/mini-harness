# mini-harness

从零搭建的个人 AI 终端助手（harness）。基于 OpenAI 兼容 API（默认 DeepSeek），**不依赖 LangChain 等框架**。

## 功能特性

- **ReAct 工具循环**：15 个内置工具 + MCP 动态扩展，支持一轮多工具批量调用
- **终端界面**：基于 rich 的 TUI——流式输出、工具调用卡片、diff 高亮、todo 面板、状态栏
- **权限审批**：只读操作放行，写入/命令需确认；支持批量审批（y 全部 / n 全部 / s 逐个 / q 中止）与会话级放行规则
- **会话持久化**：会话存档、自动命名、按 ID/标题恢复，todo 清单随会话保存与还原
- **上下文工程**：token 实时计量、超预算自动 compact（模型自总结而非丢弃）、文件分段读取、子代理隔离上下文
- **两层记忆**：全局 `user_memory.md`（跨项目偏好）+ 项目 `.mini-harness.md`，每轮后自动提炼
- **健壮性**：网络重试退避、空转检测、截断重试、命令 30 秒超时、PID 级进程树清理、长驻命令自动后台化
- **安全防护**：防自杀命令黑名单、文件操作路径圈定、read-before-edit 强制
- **MCP 支持**：JSON-RPC over stdio 客户端，外加一个教学用极简 MCP server

## 快速开始

```powershell
# 1. 安装依赖
py -3.13 -m pip install openai pyyaml tiktoken requests rich

# 2. 配置 API Key（DeepSeek，缺失时程序会提示设置方法）
$env:OPENAI_API_KEY = "sk-..."

# 3. 启动
python main.py
```

可选环境变量：`SERPAPI_API_KEY`（联网搜索工具 web_search 使用）。

### 命令行参数

```powershell
python main.py                # 新会话，在当前目录工作
python main.py --dir <路径>   # 指定工作目录（agent 只能操作该目录内文件）
python main.py --list         # 列出会话存档（含标题）
python main.py --resume <ID或标题>  # 恢复会话（支持时间戳 ID 或标题关键词）
python main.py --help         # 帮助
```

## 交互方式

| 输入 | 说明 |
| --- | --- |
| 直接对话 | 模型自动调用工具完成任务 |
| `@file` 引用 | `@main.py 帮我改 bug`，自动注入文件内容 |
| `!!` | 重放上次输入 |
| `/help` `/list` | 帮助 / 会话列表 |
| `/name <标题>` | 会话命名（新会话首轮后也会自动命名） |
| `/model [名称]` | 查看 / 切换模型 |
| `/tokens` | 查看上下文用量 |
| `/memory [add <内容>]` | 查看记忆 / 追加项目记忆 |
| `/allow <工具>` `/deny <工具>` | 本次会话放行 / 禁止某工具 |
| `/clear` | 清屏 |
| `Ctrl+C` | 中断生成（不退出，同时清理子进程） |

退出时会询问是否保存会话（y 提交 / n 丢弃）。

## 工具一览（15 个内置 + MCP 动态注册）

| 工具 | 说明 | 权限 |
| --- | --- | --- |
| `calculator` | 数学计算 | 放行 |
| `read_file` | 分段读文件（150 行 + offset 续读） | 放行 |
| `list_files` | 列目录（递归可选） | 放行 |
| `grep` | 代码搜索（正则 + 类型过滤） | 放行 |
| `update_todo` | 层次化任务清单 | 放行 |
| `ask_user` | 结构化提问（带选项） | 放行 |
| `web_search` | 联网搜索（SerpAPI） | 放行 |
| `webfetch` | 抓网页转纯文本 | 放行 |
| `write_file` | 创建/覆盖文件 | 审批 |
| `edit_file` | 精准修改（old_string 原文定位，找不到/不唯一即报错） | 审批 |
| `delete_file` | 删除单文件（隐藏文件保护） | 审批 |
| `run_bash` | 执行命令（超时/防自杀黑名单/长驻命令后台化） | 审批 |
| `download_file` | 下载 + zip/tar.gz 自动解压 | 审批 |
| `run_subtask` | 子代理（独立上下文执行子任务） | 审批 |
| `mcp_*` | MCP 生态工具（动态注册） | 放行 |

## 目录结构

```
mini-harness/
├── main.py               # 入口：交互循环、@file 引用、自动命名/记忆、slash 命令
├── config/config.yaml    # 配置：多模型、agent 参数、MCP servers
├── model/
│   ├── client.py         # API 客户端（chat / 流式，重试退避）
│   └── streaming.py      # 流式解析（含 tool_calls 分片拼接）
├── agent/
│   ├── loop.py           # ReAct 循环：空转防护、截断重试、diff 捕获、todo 注入
│   ├── context.py        # token 计数、上下文裁剪
│   ├── session.py        # 会话存档（暂存/提交/丢弃，含标题与 todo 快照）
│   ├── permissions.py    # 权限审批
│   └── events.py         # 事件总线（loop 发事件，UI 订阅渲染）
├── tools/                # 15 个工具 + MCP 客户端 + 注册表
├── ui/tui.py             # rich 渲染：消息流、工具卡片、diff、todo 面板
├── test_mcp_server.py    # 教学用极简 MCP server
└── AGENTS.md             # 开发维护文档（设计细节、学习进度）
```

## 配置说明

`config/config.yaml`：

- `models`：可配置多个模型，运行时用 `/model` 切换
- 每个模型通过 `api_key_env` 指定读取哪个环境变量中的 Key，`base_url` 指向任意 OpenAI 兼容服务
- `mcp_servers`：MCP server 启动命令列表。**默认项是本地开发路径示例，使用前请改成自己的路径或移除**
- `agent.max_context_tokens`：上下文预算（默认 800K，为 1M 窗口留余量）

## 设计亮点

- **上下文工程**：层次化 todo + 随会话存档；compact 自总结；分段读取防撑爆；子代理主上下文只留摘要
- **两级止损机制**：单轮空转 5 次中止；连续 3 轮工具全失败自动注入提示；prompt 层"同一验证失败 3 次必须停下汇报"
- **交付门禁**：prompt 强制"声称完成前必须实际运行验证"、"文档结论必须当场重验"
- **read-before-edit 机制化**：edit_file 用原文片段定位，倒逼模型先读文件，消灭"凭记忆改文件"

更多设计细节与开发记录见 [AGENTS.md](AGENTS.md)。

## 说明

- `sessions/`、`user_memory.md`、`.mini-harness-todo.json` 为个人运行数据，已在 `.gitignore` 中排除；程序会在本机自动生成
- 本项目为个人学习实践：从 API 调用 → 工具循环 → 上下文管理 → 权限与持久化，逐步扩展而来

# mini-harness

从零搭建的个人 AI 终端助手（harness）。基于 OpenAI 兼容 API（DeepSeek），不依赖 LangChain 等框架。核心思想：模型无状态，harness 补全记忆、手脚、循环与安全。

## 运行

```powershell
# 依赖
py -3.13 -m pip install openai pyyaml tiktoken requests rich

# 环境变量
$env:OPENAI_API_KEY = "sk-..."     # DeepSeek Key（缺失时程序会给出设置提示）
$env:SERPAPI_API_KEY = "..."       # 可选，联网搜索用

# 启动（全局命令，任意目录）
mini-harness                        # 新会话，当前目录工作
mini-harness --dir <路径>           # 指定工作目录
mini-harness --list                 # 列出存档（含会话标题）
mini-harness --resume <ID或标题>    # 恢复会话（支持按时间戳 ID 或标题关键词）
mini-harness --help                 # 帮助

# 全局命令安装：mini-harness.cmd 已放在 Python Scripts 目录（PATH 内）
```

## 目录结构

```
main.py              入口：交互循环、@file 引用、自动命名/记忆、slash 命令
model/               模型层
  client.py            Client：chat / create_stream，重试退避（1s/2s/4s）
  streaming.py         流式解析（含 tool_calls 分片拼接）
agent/               大脑层
  loop.py              ReAct 循环：空转防护、截断重试、diff 捕获、todo 注入
  events.py            事件总线（loop 发事件，UI 订阅渲染）
  context.py           token 计数、上下文裁剪（留 10% 余量）
  session.py           会话存档（暂存/提交/丢弃，含标题字段）
  permissions.py       权限审批（只读/mcp_ 放行，写入/命令需确认）
tools/               手脚层
  registry.py          工具注册表 + MCP 动态注册
  calculator.py        数学计算
  filesystem.py        read_file(分段)/list_files/write/edit（路径圈定）
  shell.py             shell 执行（超时、防自杀黑名单、长驻命令后台化、PID 级进程树清理）
  search.py            web_search(SerpAPI) / grep / webfetch
  download.py          下载文件 + zip/tar.gz 自动解压
  todo.py              层次化任务清单（父状态自动推导）
  subagent.py          子代理（独立上下文执行子任务）
  ask_user.py          结构化提问（带选项）
  mcp.py               MCP 客户端（JSON-RPC over stdio，UTF-8 容错）
ui/
  tui.py               rich 渲染：消息流、工具卡片、diff 高亮、todo 面板、状态栏
config/config.yaml    配置（多模型、agent 参数、MCP servers）
sessions/             会话存档目录（含会话标题）
test_mcp_server.py    教学用极简 MCP server
user_memory.md        全局记忆（个人偏好，跨项目）
```

## 工具清单（15 个内置 + MCP 动态）

| 工具 | 说明 | 权限 |
|------|------|------|
| calculator | 数学计算 | 放行 |
| read_file | 分段读文件（150 行 + offset 续读） | 放行 |
| list_files | 列目录（递归可选） | 放行 |
| delete_file | 删除单文件（隐藏文件保护，shell 删除仍禁止） | 审批 |
| grep | 代码搜索（正则 + 类型过滤） | 放行 |
| write_file | 创建/覆盖文件 | 审批 |
| edit_file | 精准修改（old_string 原文定位，行号仅兼容；read-before-edit 强制化） | 审批 |
| run_bash | 执行命令（长驻命令自动后台化） | 审批 |
| web_search | 联网搜索（SerpAPI） | 放行 |
| webfetch | 抓网页转纯文本 | 放行 |
| download_file | 下载 + zip/tar.gz 自动解压 | 审批 |
| update_todo | 层次化任务清单 | 放行 |
| run_subtask | 子代理（独立上下文） | 审批 |
| ask_user | 结构化提问 | 放行 |
| mcp_* | MCP 生态工具（动态注册） | 放行 |

## 交互功能

- **slash 命令**：/help /list /name（会话命名）/model（切换）/tokens /memory /clear /allow（放行工具）/deny（禁止工具）
- **批量审批**：一轮多个工具操作合并为一次审批，支持 y=全部 / n=全部 / s=逐个 / q=中止任务
- **会话权限记忆**：/allow write_file 本次会话不再询问；/deny 一律拒绝
- **过程播报**：prompt 引导模型调用工具前先说意图、每批完成后播报进展；**loop 硬约束**：连续 2 轮纯点单自动注入「请说明你在做什么」
- **Windows 环境适配**：prompt 注入 cmd 语法说明（dir/type/findstr）；shell 输出自动 utf-8/gbk 双解码（中文不乱码）
- **子代理轮次**：30 轮上限（防复杂子任务过早中止）
- **Todo 清洗**：保存清单时自动过滤空任务项/空子任务
- **会话命名**：新会话首轮后模型自动生成标题；/name 手动覆盖；失败 fallback 用户输入
- **`!!`** 重放上次输入
- **@file 引用**：`@main.py 帮我改 bug` 自动注入文件内容
- **自动记忆**：每轮后静默提炼用户偏好存入全局 `user_memory.md`；项目约定存 `.mini-harness.md`（两层记忆）
- **模型知道元命令**：SYSTEM_PROMPT 注入 slash 命令说明，用户提「改会话名」时模型会引导用 /name
- **Ctrl+C** 中断生成不退出（同时清理子进程）
- 退出时询问是否保存会话（y 提交 / n 丢弃）；**退出保存前会先落盘当前完整消息**（含中断轮的内容，防止中断后直接 exit 丢数据）
- **消息清洗**：保存前自动删除「孤儿 tool_calls」（审批阶段被中断留下的无结果调用记录），防止恢复后 API 校验失败
- **存档目录自动创建**：每次保存会话前确保 `sessions/` 存在，首次运行或目录被删除后无需手动建目录。

## 上下文工程（长线任务不遗忘）

- 层次化 Todo：任务分解 + 父状态自动推导
- **Todo 随会话存档**：会话 JSON 含 todo_snapshot，resume 时自动恢复任务清单（跨目录不丢失，修复「任务状态分裂」）
- **子代理清单隔离**：run_subtask 执行前后快照/恢复主清单，子代理无法污染主任务清单
- Compact：上下文满时模型自总结历史（非丢弃）
- 分段读取：防止文件内容撑爆上下文
- 子代理：子任务独立上下文执行，主上下文只留摘要
- 800K 预算（deepseek-flash 1M 窗口留 20% 余量）
- 50 轮执行空间

## 健壮性与安全

- 网络：超时/连接/限流指数退避重试
- 空转：空输出/截断自动重试（不耗轮次），连续 5 次中止
- 输出：max_tokens 65536；ds_safety 服务端安全标签自动清洗
- 卡死防护：所有命令输出走临时文件（防孤儿进程管道死锁）；30 秒硬超时 + PID 级进程树清理
- 防自杀：taskkill /IM python/node 等杀宿主的命令被黑名单拦截
- 长驻命令（dev server 类）自动后台化 + 日志落盘
- 键盘中断时清理子进程
- 多模型：deepseek-flash / deepseek-v4-pro 运行时切换

## 防牛角尖机制（止损体系）

- **Prompt 止损规则**：同一验证失败 3 次必须停手并用 ask_user 汇报；同一操作结果随机波动即判断为环境问题、停止测试
- **任务级无进展检测**：连续 3 轮「工具调用全部失败」→ 自动注入系统提示，要求模型停止重复尝试、重新评估或向用户汇报
- 配合单轮空转检测（5 次中止），形成「单轮 → 跨轮」两级止损

## 交付质量体系（防迭代残留）

- **read-before-edit 强制化**：edit_file 首选 old_string 原文定位——找不到/不唯一就报错，逼模型先读当前文件，从机制上消灭「凭记忆改文件」
- **交付门禁（prompt）**：声称完成前必须实际运行验证（测试/构建/语法检查）；文档里的实测结论必须当场重验、禁止引用记忆中的旧状态
- **收尾审查（prompt）**：多文件改动交付前派 run_subtask 子代理以全新上下文审查（语法/死代码/文档矛盾）

## 学习进度

Day 1-2  API 调用与 token / Day 3-4 工具调用与 ReAct 循环
Day 5-6  文件与 shell 工具 / Day 7 交互式整合
Day 8    上下文裁剪 / Day 9 权限审批 / Day 10 会话持久化
Day 11   重试退避 / Day 12 rich TUI 与事件驱动 / Day 13 diff 与 slash
扩展：todo/compact/分段读取/subagent（长线任务体系）
扩展：list_files/grep/输入历史/长期记忆（体验升级）
扩展：webfetch/多模型切换/MCP（架构扩展）
扩展：自动记忆进化/会话命名（个性化）
实战：AstroPaper 改造 / 艾宾浩斯复习系统（SQLite + 遗忘曲线）

## 维护约定

每次代码更新后，必须同步更新本文件（AGENTS.md），保持文档与实际功能一致。

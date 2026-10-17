# 第 4 层 · 文件与 shell 工具 学习笔记

> 文件：tools/filesystem.py（320 行）、tools/shell.py（154 行）
> 对照脚本：day5_demo.py、day6_demo.py

## 一、_safe_path 路径圈定（filesystem.py:136-140）

```python
def _safe_path(path):
    full = os.path.abspath(os.path.join(WORK_DIR, path))
    if not full.startswith(WORK_DIR):
        return None
    return full
```

- 作用：一切文件操作的第一道关卡，防 `../..` 越界。
- **已知微妙漏洞（教学重点）**：裸字符串前缀比较无组件边界。
  WORK_DIR=C:\proj 时，`..\proj-evil\x` → C:\proj-evil\x 也能通过。
  修复：`full == WORK_DIR or full.startswith(WORK_DIR + os.sep)`。
- 通用教训：路径安全按"目录组件边界"比较，不是字符串前缀（CWE-22 类）。

## 二、read_file 分段读取

- DEFAULT_LIMIT=150 / MAX_LIMIT=300：防大文件撑爆上下文。
- 返回带行号；结尾提示"剩余 N 行，可用 offset=X 续读"——
  把用法说明写进工具输出，教模型正确使用方法。

## 三、edit_file：read-before-edit 强制化

- old_string 定位，**故意报错**：count==0（找不到）→ 提示先 read_file；
  count>1（不唯一）→ 要求更长片段。
- 不做模糊匹配容错的理由：**失败代价不对称**——
  报错可恢复，乱改不可恢复（悄悄改错位置）。
- line 行号模式仅为旧对话兼容，schema 明示"不推荐"。

## 四、删除与列目录防御

- delete_file：隐藏文件（.开头）全保护 + PROTECTED_NAMES
  （.mini-harness.md / .gitignore / user_memory.md）+ 不支持目录。
- list_files 递归忽略名单：node_modules/.git/__pycache__/dist/build——
  防垃圾路径塞爆上下文。

## 五、shell.py 五个坑的五个补丁

1. **防自杀黑名单**（shell.py:11-15）：shell 删除类命令全禁（rm/del/format/
   shutdown）；taskkill 杀 python/node/cmd 被拦截——防止助手杀掉宿主进程。
2. **长驻命令后台化**（shell.py:17-39,140-154）：识别 npm run dev/vite/
   uvicorn 等 → 后台启动 + 日志落盘 run_bash.log + 返回 PID。
   执行策略由命令语义决定。
3. **临时文件防管道死锁**（shell.py:79-87）：不用 PIPE——管道缓冲区
   写满后子进程阻塞、父进程 wait 等它退出，互相等待死锁。
   临时文件写磁盘无上限，wait 后 seek(0) 再读。
4. **超时 + PID 级进程树清理**（shell.py:95-119）：30 秒硬超时 →
   `taskkill /F /T /PID` 杀整棵树（shell=True 多一层 cmd.exe 会留孤儿）；
   KeyboardInterrupt 分支同样清理后 raise。
5. **编码双解码**（shell.py:60-66）：utf-8 → gbk → replace 兜底，
   处理 Windows 中文 cmd 输出。

## 六、思考题与答案

**Q1：_safe_path 的 startswith 检查存在什么漏洞？如何修复？**
A：字符串前缀比较没有目录组件边界。WORK_DIR=C:\proj 时，
路径 `..\proj-evil\x` 解析为 C:\proj-evil\x，startswith("C:\proj")
为 True——实际已越界到隔壁目录。修复：
`full == WORK_DIR or full.startswith(WORK_DIR + os.sep)`，
或用 os.path.commonpath 按组件比较。教训：安全校验要考虑
"字符串相似但语义不同"的边界情况（off-by-one 的空间版）。

**Q2：为什么命令输出用临时文件而不用 subprocess.PIPE？**
A：PIPE 是有限大小的内核缓冲区。子进程大量输出填满缓冲区后，
写操作被阻塞；父进程 proc.wait() 在等待子进程退出——双方互等，
永久死锁（经典管道死锁）。临时文件写磁盘不受此限，父进程 wait()
结束后 seek(0) 再读。这就是 AGENTS.md"卡死防护"的原理。

**Q3：dev server 类命令为什么要自动后台化，不能统一用 30 秒超时处理？**
A：dev server 设计上永不退出，"前台执行+超时"等于每次必然超时被误杀，
但这类命令的意图恰恰是"一直跑着"。所以 harness 做命令语义识别：
长驻类 → 后台启动 + 日志落盘 + 立刻返回 PID，模型可以后续
`type run_bash.log` 查状态。同一种工具按意图分派不同执行策略。

**Q4：edit_file 找不到 old_string 时直接报错是"缺陷"还是"特性"？**
A：特性。报错逼模型先 read_file 拿真实内容（read-before-edit 强制化），
从机制上消灭"凭记忆改文件"。不做模糊容错的原因是失败代价不对称：
报错可恢复（重读再改），乱改不可恢复（悄悄改错、几轮后才发现）。
防错机制的设计原则：宁可失败得明确，不可成功得可疑。

**Q5：taskkill 为什么要 /T，黑名单为什么禁止模型杀人宿主的命令？**
A：shell=True 的实际进程树是 cmd.exe → 命令（可能还有孙进程），
只杀 cmd.exe 会留下孤儿进程继续写文件/占端口，/T 杀整棵进程树。
黑名单防自杀：mini-harness 本身是 python 进程，
taskkill /IM python 会把宿主连同对话一起杀掉——助手执行命令把自己弄死，
用户侧表现为程序神秘崩溃。安全机制要包含"保护自身运行"这一维度。

## 七、动手实验（可选）

1. 写一个 3000 行的假文件，用 read_file 体验 offset 续读流程。
2. 构造 `..\..\..\Windows\win.ini` 参数测试 _safe_path 拦截效果；
   再试试 `..\erqi-evil\x` 观察漏洞是否真的存在（别真写文件）。
3. 改 shell.py 的 TIMEOUT=3，跑一个模拟 10 秒的命令，观察进程树
   清理行为（任务管理器确认无孤儿进程）。


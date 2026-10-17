# 给AI：接入当前项目

用户只需指定自己的项目并说明研究问题。不要要求用户复制长提示词、编辑配置、学习目录或运行终端命令。

1. 确认当前目录是用户的课题目录。读取它已有的项目说明，保留现有文件。不要把工具仓库或NOR示例当成用户的新课题。
2. 使用现有Python 3.10以上运行本文件旁的安装器：

   `python install.py --project "用户的课题文件夹" --client both`

   此命令由你执行，路径按真实环境填写。Codex指定codex，Claude Code指定claude，DeepSeek Harness指定deepseek；both仅安装Codex和Claude Code。WorkBuddy、Cowork及其他已装入skill的执行环境指定portable，只放本课题的工具与资料绑定，不冒充客户端自动发现。完整包自动绑定附带数据库；源码包没有资料库时，可用`--database`指定已有SQLite快照，也可以先从公开资料开始。
3. 阅读对应客户端目录中的SKILL.md，或`.fish-toxicology/skill/SKILL.md`，运行`.fish-toxicology/tools/research.py doctor`。安装新skill后，本轮直接读取它，不声称客户端已自动加载。需要运行网页／XLSX生成器时检查openpyxl；完整包已附该依赖，源码环境缺少时按`requirements.txt`装入项目`.venv`。需要运行现有科研绘图组件时另按`requirements-figures.txt`检查NumPy和Matplotlib，并核对中文字体；不要修改系统Python。
4. 接着处理用户的研究问题。AI整理课题输入，结果存`research/`，不预写结论；仅集中询问真正影响研究的缺失信息。用户尚未给课题时，用一句话请其描述物种、物质和关注效应。

只添加`.fish-toxicology/`和所选客户端skill目录。安装器不修改AGENTS.md、CLAUDE.md或既有研究；遇到同名内容冲突会停止覆盖。数据库保持只读，完整包应保留在稳定位置供各课题共用。只有工具源码也能接入，doctor会如实说明未连接数据库。

各客户端按[装载教程](../docs/装载教程.md)处理。Claude Desktop是应用入口，需区分其中Code、Cowork和普通聊天。ChatGPT亦区分本地执行与云端会话。云端环境不能凭Windows路径访问本地库：先确认文件可读，必要时在用户授权下上传本课题资料或快照，再绑定运行环境中的真实路径。API密钥只在客户端设置中填写，不索要聊天粘贴。

源码仓库：https://github.com/Accsy7/fish-toxicology-research。完整工作包从该仓库的Release下载。接入前先读README和本文件，按当前下载版本操作。

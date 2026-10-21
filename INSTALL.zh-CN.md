# 安装与更新

[English](INSTALL.en.md)

工作包版本：1.5.0。包内包含 skill、查询与渲染工具、默认 XLSX/HTML 模板、只读数据库快照和浏览前端。需要 Python 3.10 或以上；XLSX 所需库已随包提供。

## WorkBuddy

1. 完整解压 ZIP，将解压后的文件夹放在固定位置。数据库保存在这个文件夹中。
2. 新建空白课题文件夹，例如 `C:\Research\fish-study`。
3. 在解压后的工作包目录打开 PowerShell，运行：

```powershell
.\Install-WorkBuddy.ps1 -ProjectPath "C:\Research\fish-study" -ReplaceManaged
```

安装器会把同一版本的 skill 和工具放入课题目录，并同步 WorkBuddy 的技能发现入口。已有入口会先备份；研究文件和项目自定义配置保留在原处。`-ReplaceManaged` 用于更新已有的插件组件。运行时提示找不到 Python，可加 `-PythonPath "你的 python.exe 路径"`，也可让 WorkBuddy 使用其 Python 环境执行下一节的等效命令。

4. 在 WorkBuddy 打开这个新课题文件夹，新建对话。如技能列表仍显示旧版本，刷新列表或重启 WorkBuddy，再开始研究。
5. 可直接发送：

> 读取本项目 .fish-toxicology/skill/SKILL.md，先用 .fish-toxicology/tools/research.py doctor 核对版本，然后帮我开展“双酚家族通过BMP/Wnt通路致海水青鳉骨骼毒性的机制影响研究”。

`doctor` 输出中的 `bundle_version`、`components.skill`、`components.tools` 均应为 `1.5.0`，`errors` 和 `modified_files` 应为空。安装后工具与默认配置位于项目的 `.fish-toxicology/`，研究成果保存到 `research/`。

## Python 命令与其他客户端

```text
python -B toolkit/install.py --project "课题文件夹的绝对路径" --client workbuddy --replace-managed
python -B "课题文件夹/.fish-toxicology/tools/research.py" doctor
```

其他客户端可将 `--client` 改为 `codex`、`claude`、`deepseek`；`portable` 仅配置项目内入口。技能上传包位于 adapters；本地课题的工具和数据库仍通过安装器接入。

## 更新已有项目

```text
python -B toolkit/install.py --project "已有课题目录" --client workbuddy --update-tools --replace-managed
```

更新保留项目数据库绑定、research 目录和独立显示配置。旧组件备份于项目 `.fish-toxicology/backups/`，其中 index.json 记录原路径。新课题建议使用空白项目，并保存实际研究记录。

## 显示与配置

默认输出采用 00—07 工作簿及四入口网页。报告、图表与下载读取同一分析数据。物种、通路、物质和图形面板随课题填写；列映射、样式、入口和搜索字段可通过 profile 配置。细节见 [渲染输入](toolkit/skill/references/render-input.md)。

独立 SVG/PNG/PDF 批量导出可使用工具包的 export_figures.cjs，需要 Node.js、Playwright 与 Chromium/Edge；网页也提供图形下载和打印入口。图版对应数据使用同一筛选结果。

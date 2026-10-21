# 安装与更新

**1.5.1-rc.1 为科研试用预发布版。** 软件包包含 skill、查询与证据检查、报告工具、模板及 Excel 依赖；数据库和独立数据库前端单独提供。原 1.5.0 完整工作包保留在历史 Release。

## 接入课题

1. 下载[新版软件包](https://github.com/Accsy7/fish-toxicology-research/releases/download/v1.5.1-rc.1/fish-toxicology-research-software-1.5.1-rc.1.zip)，解压到固定位置，另建自己的课题目录。
2. 使用扩展资料库时，先把原 0.4.1 基线组件解压到自选的 `DATA_ROOT`，再将 `observations-0.4.2-local.1.sqlite3.zip` 解压到同一目录。修订文件位于 `revisions/0.4.2-local.1/`，不覆盖根目录旧 observations。
3. 把软件包的 `toolkit/INSTALL.md` 交给 AI，要求接入当前课题。由 AI 按实际客户端和路径执行，例如：

```text
python toolkit/install.py --project 课题目录 --client codex --catalog DATA_ROOT/revisions/0.4.2-local.1/catalog.json
```

其他客户端选 `claude`、`deepseek`、`workbuddy` 或 `portable`；`both` 只接入 Codex 和 Claude Code。单独上传 skill ZIP 只提供技能发现入口，本地查询仍需软件和可读资料。云端会话不能直接读取 Windows 路径，须另行传入实际可用的资料再绑定。

需要 Python 3.10 或以上。软件 ZIP 附带纯 Python 的 Excel 依赖；扩展 Parquet 化合物目录查询所需的可选依赖列在 `toolkit/requirements-catalog.txt`，未打入编译型依赖。缺少 DuckDB 时，受支持的 SQLite 查询继续可用，并提示 Parquet 身份来源不可用。从源码使用工作簿导出时，先安装 `toolkit/requirements.txt`。

## 更新已有课题

```text
python toolkit/install.py --project 课题目录 --client codex --update-tools --catalog DATA_ROOT/revisions/0.4.2-local.1/catalog.json
```

安装器备份受管理文件，保留研究成果和自定义配置；遇到用户修改过的工具会停止并列出文件。省略 `--catalog` 会保留原数据库绑定，不会自动应用数据修订。`--database` 可绑定历史独立 SQLite，不能与 `--catalog` 同时使用。

在课题目录运行 `python .fish-toxicology/tools/research.py doctor`。其中 `complete_repair_data_bound` 表示是否绑定 0.4.2 修订资料。软件检查通过不等于科学结论正确或新课题研究完成。

## 独立数据库前端

当前已认可前端为 **1.13.1-local.1**，独立维护。本软件包不安装或替换数据库界面。使用既有前端接入本地 API 时，显式指定目录：

```text
python .fish-toxicology/tools/browse_catalog.py --frontend-dir 已认可前端目录
```

不要将旧测试包的 1.9.0-local.6 前端替代当前独立前端。科研报告生成器仍随软件提供，沿用已认可的 00—07 工作簿与报告格式。

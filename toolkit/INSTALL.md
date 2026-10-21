# 给 AI：接入当前课题

当前为 1.5.1-rc.1 软件预发布版。读取课题已有说明并保留研究文件；用户只需描述研究问题，不要求其手动改配置或复制内部规程。

1. 确认真实课题目录和客户端。使用本文件旁的 `install.py`，以 `--project` 指定课题，`--client` 选 codex、claude、deepseek、workbuddy、both 或 portable。
2. 软件包不含数据库。用户已有扩展资料组件时，通过 `--catalog DATA_ROOT/revisions/0.4.2-local.1/catalog.json` 绑定；目录内所有路径均以该 catalog 所在目录解析。不要拿本机修复目录的绝对路径配置交给其他机器。
3. 更新已有安装时增加 `--update-tools`。安装器保留研究与既有配置，备份受管理文件；有本地改动时核对后再处理。省略 --catalog 保留旧数据绑定，不代表旧库已修复。
4. 读取安装后的 skill，运行 `.fish-toxicology/tools/research.py doctor`。如未绑定数据或缺少可选依赖，按实际状态报告；SQLite 可用与 Parquet 目录可用分别说明。
5. 当前数据库前端1.13.1-local.1独立维护。本包不安装、不替换数据库前端；不要使用1.9测试候选覆盖它。科研报告模板和00—07工作簿仍随包提供。

精确安装命令及数据布局见上级目录 INSTALL.zh-CN.md。工程检查通过不等于完成科学研究；不得改写旧分析或将新课题预填为完成。

# Release notes / 版本说明

## 1.5.1-rc.1 — 2026-10-21 / prerelease

- Add identity and source-DOI retrieval diagnostics. An empty query is not treated as absence of evidence.
- Preserve experimental conditions and evidence bindings through extraction, analysis, workbook/report export and completion registration.
- Separate program validation from scientific objective completion, and reject changed source conditions or unsupported completion records.
- Add portable `--catalog` installation. Full data repairs require the separate 0.4.2-local.1 observation revision plus the unchanged 0.4.1 baseline components.
- Ship software and skill without SQLite databases or a database UI. Keep the approved 1.13.1-local.1 frontend independent; do not install the 1.9 test frontend.
- This is a supervised-use prerelease. Targeted software checks do not establish new-topic scientific validity or production acceptance.

- 增加身份与来源 DOI 检索诊断；零匹配不等于无证据。
- 逐来源记录保留实验条件，贯通提取、分析、工作簿/网页和完成登记。
- 区分程序检查与科学目标完成，阻断来源条件被改写或完成记录无依据的情况。
- 新增 `--catalog` 可移植绑定；完整数据修复另需 0.4.2-local.1 observations 修订与原 0.4.1 基线组件。
- 软件包不含 SQLite 或数据库界面；保留独立的已认可 1.13.1 前端。
- 预发布科研试用；工程回归不代表新课题科学迁移或生产验收通过。

## 1.5.0

- Check skill and tool versions during installation. Back up plugin files during updates and restore them if installation fails.
- Support configurable fields and layouts in Excel workbooks and web reports generated from the same analysis data.
- Fix long-text display in Excel and chart display for negative values and empty datasets.
- Add licenses for project code, documentation and database compilation, with dependency and data-source attribution.

- 安装时检查技能与工具版本。更新时备份插件文件，安装失败时恢复。
- Excel 工作簿与网页报告支持自定义字段和布局，使用同一份分析数据生成。
- 修复 Excel 长文本显示，以及图表遇到负值或空数据时的显示问题。
- 添加项目代码、文档和数据库编排的许可证，以及依赖和数据来源的署名。

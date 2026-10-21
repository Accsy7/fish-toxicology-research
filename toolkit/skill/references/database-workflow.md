# 工具接口

1.5.1-rc.1 的[来源条件与完成检查](evidence-and-completion.md)补充来源筛选、无匹配诊断、条件保留和登记要求。

项目绑定在 `.fish-toxicology/workspace.json`，工具位于 `.fish-toxicology/tools/`；软件包对应 `toolkit/workspace.json` 与 `toolkit/tools/`。读取绑定后的真实路径运行命令，结果存入当前项目 `research/`。

## 查库与建立课题

先用 coverage 查看快照范围，再按物种、通路和物质查询。查询结果为空时，继续核对名称、编号及公开来源。

| research.py命令 | 用途 |
|---|---|
| `doctor` | 核对实际加载目录、skill 与工具版本、组件完整性和数据库连接；`doctor --deep`另查整个数据库的哈希及关联 |
| `taxonomy <学名> --taxid <编号>` | 核对本地物种记录与编号；未匹配时继续查物种官方记录 |
| `coverage` | 查看本地快照的来源、实际数量、范围和缺项 |
| `genes / proteins --species <学名或taxid> --term <名称或别名>` | 查基因或蛋白；以 `--limit` 和 `--offset` 分页，`has_more`表示尚有结果 |
| `pathways --species <学名或taxid> --term <通路名>` | 查该物种的通路目录 |
| `pathway-members <通路ID>` | 查成员及明确对应的基因、蛋白编号 |
| `sequence <UniProt编号>` | 读取完整氨基酸序列 |
| `source-record <编号> --kind gene或protein` | 回查原始来源行、文件哈希和行号 |
| `toxicity --species <学名或taxid> --term <物质名称或CAS>` | 分页查询各终点实验结果 |
| `new` | 建立空白课题输入；参数用 `new --help` 查看 |
| `analyses` | 查询已登记分析，续做选择当前版本 |
| `search <名称、CAS或编号>` | 查找物质并核对身份；歧义时检查结构、盐型及异构体 |
| `extract --chemical <明确名称或编号> --output <新目录>` | 提取固定资料版本，`--chemical`可重复指定 |

默认每页100条；继续读取时增加offset。先按物种和通路定位，再读取需要的记录与原文。数据库以只读方式查询，缺少资料时补充用户材料和公开来源。提取结果保留物质、实验条件、终点、原摘录、来源位置及空值。旧预测通过 `--history` 单独查询；新课题从当前问题重新判断。超出提取接口的查询可按绑定的schema使用SQLite只读连接。

## 资料分类与筛选

`chemicals / properties / environment / bioactivity / toxicity --term <名称或编号>` 查询身份、理化性质、环境过程、生物作用和毒性。默认数值查询只返回实验资料；`--support inferred_annotation`、`pending_verification` 可分别查看推定注释和尚待核对的记录，`all`查看全部非预测资料。缺失字段保持为空。

基因、蛋白和通路可包含推定注释。蛋白存在、功能及人工审阅分别保存；用 `--support experimental --assertion function` 筛选有实验支持的功能判断。保留限定关系、原来源代码和具体实验条件。`source-record <记录编号> --kind observation` 回查原始实验记录；基因和蛋白分别使用 `--kind gene` 与 `--kind protein`，`extract` 沿用同一筛选规则，已有预测通过 `--history` 另存。新的机制解释、假说和排序写入当前课题分析，并连接引用资料。

`python .fish-toxicology/tools/browse_catalog.py --frontend-dir <独立前端目录>` 使用已认可的1.13.1独立前端打开本机资料网页；本软件包不附带或替换数据库界面。页面筛选和 CSV 导出与命令行一致。覆盖数量及未完成批次见 `coverage`。同一资料库可由多个课题共用。

## 生成工作簿、网页与图版

使用同一份分析记录，通过通用入口生成。新课题沿用默认显示配置，按研究内容填充物质、蛋白、计算记录和图形面板；专业字段及特殊图形在配置中补充。输入示例、字段和配置方法见[渲染输入](render-input.md)。

```text
python .fish-toxicology/tools/render_reviewed.py research/<课题>/analysis/presentation.json --output research/<课题>/deliverables/<新版本>
```

格式调试使用 --stage preview。程序回读工作簿并记录输入与输出哈希；实际检查所有工作表、筛选、详情、复制和导出后登记成果。

## 登记成果

建立 `release.json`，通过 `research.py register <release.json>` 登记。相对路径均以release文件为起点：

- 基本信息：`project_id / analysis_version / title / analysis / analysis_sha256`。
- `content_review`：`reviewer / decision / open_blockers / candidate_ids / records[{path,sha256}]`。
- records 至少包含一份与本次分析绑定的 `publication_review`，格式见[渲染输入](render-input.md)。正式分析的 `project_id / analysis_version` 与登记值一致；物质范围优先读取 `chemicals`，旧格式兼容 `candidates`。
- `artifacts`：`kind / path / sha256`；网页另附 `web_files`，覆盖页面目录内的数据、脚本和图片；图版与对应数据分别登记。
- `database_links`：各 `candidate_id`对应 `chemical_id / basis`；未匹配时 `chemical_id`为null并写 `unmatched_reason`。

register核对文件、版本和关联，写入绑定的 `analysis_catalog`。资料库新增内容另存检查，再用新副本更新绑定；原始快照与历史分析保留。

## 独立数据修订

1.5.1-rc.1 软件不含SQLite。完整检索修复需绑定0.4.2-local.1目录：先保留并解压0.4.1全部基线组件，再解压单独的observations修订。通过安装器 `--catalog DATA_ROOT/revisions/0.4.2-local.1/catalog.json` 绑定；每个paths值均相对catalog父目录。软件更新不自动修订旧库，doctor会分别报告数据版本及可选Parquet依赖。

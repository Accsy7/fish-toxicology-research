# 工具接口

项目绑定在 `.fish-toxicology/workspace.json`，工具位于 `.fish-toxicology/tools/`；完整工作包对应 `toolkit/workspace.json` 与 `toolkit/tools/`。读取绑定后的真实路径运行命令，结果存入当前项目 `research/`。

## 查库与建立课题

| research.py命令 | 用途 |
|---|---|
| `doctor` | 核对实际加载目录、skill 与工具版本、组件完整性和数据库连接 |
| `taxonomy <学名> --taxid <编号>` | 核对本地物种记录与编号；未匹配时继续查物种官方记录 |
| `proteins --species <学名> --term <名称或别名>` | 查该物种蛋白；省略 term 可查看该物种全部记录 |
| `new` | 建立空白课题输入；参数用 `new --help` 查看 |
| `analyses` | 查询已登记分析，续做选择当前版本 |
| `search <名称、CAS或编号>` | 查找物质并核对身份；歧义时检查结构、盐型及异构体 |
| `extract --chemical <明确名称或编号> --output <新目录>` | 提取固定资料版本，`--chemical`可重复指定 |

数据库以只读方式查询，缺少资料时补充用户材料和公开来源。提取结果保留物质、实验条件、终点、原摘录、来源位置及空值。旧预测通过 `--history` 单独查询；新课题从当前问题重新判断。超出提取接口的查询可按绑定的schema使用SQLite只读连接。

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

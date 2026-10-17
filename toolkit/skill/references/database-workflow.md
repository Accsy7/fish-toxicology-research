# 数据库与课题分析

用户自己的项目读取`.fish-toxicology/workspace.json`，命令入口为`.fish-toxicology/tools/research.py`；完整工具包中的配置位于`toolkit/workspace.json`，工具位于`toolkit/tools/`。下文命令均由AI运行，不要求用户照抄。先执行doctor，续做用analyses查正式版本，新课题用new建立空白输入。

各课题保存在当前项目的research/；资料库可以共用，不复制整个NOR项目。doctor检查环境和资料，不进行科学复核。没有数据库时继续查公开资料；不得把未连接说成查询无结果。为登记无数据库课题，逐候选记录chemical_id为null和未匹配原因。

## 取证

`search <名称、CAS或编号>`核对身份；歧义需核查结构、盐型和异构体，不能选首条。`extract --chemical <明确名称或编号> --output <新目录>`可重复指定多个物质。输出各物质证据包与查询清单，保存固定资料版本。数据库只读。

证据包包含测量、对象与条件、终点、样品组成、多物质论文成员、关联存活结果、来源位置、原摘录与原库状态。保留null；检查值与原文、单位、剂量、时间、样本数及对照是否对应。原库复核标记不代替本次适用性判断。资料不足则主动补查公开来源并另存，不停在“库里没有”。

数据库中的旧预测默认不提取。确需历史对照时才使用--history，字段会明确标识历史分析版本。注册分析目录中的当前结论也只适用于其研究条件；新课题不能复制为预期答案。当前库内的BMP蛋白范围和BMPR1A计算不是新课题默认靶点。

超出物质取证命令的查询，AI根据workspace.json登记的schema（如有）使用SQLite只读连接完成。完整schema、原查询工具及维护工具随原离线数据库保留。不要臆造不存在的接口或把页面浏览等同于查完整库。

## 生成

已认可NOR示例保留原件。新课题从正式分析中的审定publication字段渲染，不能调用旧NOR复制入口来生成新课题。

publication具有title、context、version、sheets、candidates、sections字段：

- sheets：依00—07顺序的8项；每项有name、max_col、cells（单元格地址到已审值）、merges、links、heights，以及可选widths、autofilter。明确逐字段映射与来源，既有样式来自认可模板；清空示例科学内容后再填入本课题。字段含义和行高须实际核对。
- candidates：每项为id、title、group、summary和details。details含label、text及可选sources[{label,url}]。id必须与正式分析候选完全一致。预测、条件、反证及更新条件来自本课题审定文本，不能由渲染器补写。
- sections：四个科学问题入口，每项title、paragraphs、tables、figures及可选show_candidates。tables每项title、columns、rows；figures每项path、sha256、label、caption。图内数值及当前筛选必须先与正式分析核对。科学图版用已有绘图组件产生，不把正文截图充作图版。

渲染说明文件包含analysis（相对路径）、analysis_sha256和publication_review。publication_review包含reviewer、decision、publication_sha256、record:{path,sha256}，必须对应真实字段内容核对。publication本体存正式分析，不在说明文件另写一套。

```text
python .fish-toxicology/tools/render_reviewed.py research/<课题>/analysis/presentation.json --output research/<课题>/deliverables/<新版本>
```

导出内容严格取上述白名单。内部日志、校验值、审稿指令不随新增字段进入正文。程序不会从源码或模板自动得出科学结论，也不会用导出成功宣布验收。

渲染后逐表检查字段与实际数据、正文、来源、筛选和图注，再在正常显示尺寸检查XLSX及网页。render_status.json的rendered_for_display_review仅表示文件已写出，release_approved始终为false；实际验收另存。不要为让程序通过而编造review记录。

## 成果登记

复核通过后建立release.json并运行register。记录project_id、analysis_version、title、analysis、analysis_sha256，以及：

- content_review：实际reviewer、decision、open_blockers、candidate_ids、records[{path,sha256}]。继承旧审核时写明旧范围和本次亲自核对范围。
- artifacts：kind为xlsx、interactive_html、scientific_figures等；附path和sha256，路径均相对release.json。交互网页另附web_files（网页所在目录内全部相对文件路径与校验值），一并覆盖数据、脚本和图版。图版、数据表作为实际文件登记，不用一句“已完成”替代。
- database_links：每个candidate_id对应已核对chemical_id与basis；未匹配时chemical_id为null并写unmatched_reason。身份匹配不代表新旧科学结论相同。

register只核对版本、文件、覆盖与关联，写入配置指定的analysis_catalog和结果入口；它不进行科学评审，不回填原数据库的历史predictions表。新分析可由analyses --chemical查询。旧版本保留，新版使用独立编号。

## 维护边界

本次实际能力是本地资料取证、空白课题启动、审定内容渲染及成果登记。公共演示站不等于远程AI接口；未配置MCP就不要声称已有MCP。AI需要本地文件、Python及检索能力。跨AI按真实环境验证，不把一台机器上的运行成功泛化成全部客户端可用。

本地资料新增先另存并检查归属、单位、状态和重复；更新数据库使用新副本并更新workspace.json，不静默替换冻结输入。通用科学质量仍执行研究流程和质量复核要求，不能缩减为程序成功。

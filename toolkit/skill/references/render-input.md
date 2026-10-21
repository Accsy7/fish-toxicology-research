# 渲染输入

先将分析整理为命名记录，再选择显示配置。程序按模板生成工作簿，并让网页、图版与下载读取同一份数据。完整例子见 [report-example.json](../assets/report-example.json) 和配套的 [presentation-example.json](../assets/presentation-example.json)，默认配置见 [accepted.json](../assets/profiles/accepted.json)。

## 数据文件

报告 JSON 的 `schema_version` 为 `"2.0"`，包含 `project_id / analysis_version / title / context`，以及以下记录数组：

| 集合 | 主要字段 |
|---|---|
| `chemicals` | `id / name / group / prediction / basis / doubt / status / details`；details 为 `label / text / source_ids` |
| `scope` | `stage / scope / question / method / note / status` |
| `representatives` | `slot / name / group / question / reason / comparison` |
| `experiments` | `id / chemical / object / condition / result / interpretation / note / source` |
| `computations` | `id / method / input / n / result / note` |
| `target_proteins` | `name / pathway / gene_id / protein / function / method / status / mapping / reference / source` |
| `reference_proteins` | `name / species / accession / pathway / function / inclusion / code / target / status / source / url` |
| `sources` | `id / title / url / note` |
| `unresolved` | `item / impact / handling` |

各集合可以增加课题专用字段。缺少的集合写空数组；未评估的物质将 `status` 记为 `unassessed`。`chemical_ids` 用于筛选联动，`source_ids` 对应来源目录。文本单元格也可写成 `{"text":"名称","url":"https://..."}`。`paragraphs` 按入口 ID 保存正文段落数组。

物质可附 `abbr / aliases / cas` 供统一搜索；`web.search_fields` 可调整搜索字段。重复出现的结论或数值可写成 `{"$ref":"chemicals/A/prediction"}`，从原记录按 ID 解析后供全部输出使用，修订时修改被引用的那一处。

需要核查具体比较或公式时，可使用 `analysis_checks.py <报告.json> --workspace <课题目录>`。可选字段包括：`expected_chemical_ids`（本轮范围）；`identities[{id,scientific_name,taxid}]`（按本地资料核对物种）；`comparisons[{id,type:"same_system_dose_response",experiment_ids,matching_fields}]`（同体系条件匹配）；`numeric_checks[{id,operation,inputs,result_ref,rtol,atol}]`（按公式回算）。支持 sum、mean、geometric_mean、ratio 和 product，其他方法可扩展代码。例：`{"id":"mean1","operation":"geometric_mean","inputs":[4,16],"result_ref":"computations/C1/value"}`，其中 C1 的 value 应为 8。具体科学解释由复核者对照原材料完成。

## 图形面板

`panels` 中每项有 `id / type / title / section / caption`，可选 `source_ids / wide`。面板类型：

- `network`：`nodes[{id,label,x,y,kind,detail,details,source_ids}]` 与 `edges[{id,from,to,kind,detail,source_ids}]`。节点可指定 `w/h`；默认 x/y 为中心坐标，`coordinate_origin:"top-left"` 可使用左上角坐标。连线类型为 `activation / inhibition / binding / indirect`，可指定折线路径 `points`。`width/height` 定义画布，坐标由通路布局决定。
- `matrix`：`columns` 为列标题；`rows[{label,chemical_ids,values}]` 提供单元格内容。可配置列宽、行高。
- `interval` 或 `bar`：`rows[{label,chemical_ids,value,low,high,source_ids}]`；按实际数据提供数值，缺值用 null。`unit / axis_label / scale / domain` 定义单位、轴标题、线性或对数轴及范围。
- `scatter`：行记录另有 `x`，可附 `size` 控制点面积；`x_label / y_label`、`x_scale / y_scale` 与 `x_domain / y_domain` 分别配置双轴。`size_required:true` 仅显示有 size 的记录，CSV 同步；`size_label` 说明面积含义，`label_dx / label_dy` 调整点标签。
- `heatmap`：与 matrix 相同的行列结构，数值按 `domain:[最小值,最大值]` 映射颜色；可配置行高和列宽。
- `image`：现成结构图或专项图形使用 `path / sha256`，保留原始文件和图注。

网络图的节点、关系和解释来自分析记录。矩阵、浓度图等按当前选择筛选；整条通路作为共同背景显示。网页提供物质详情、节点与连线详情、放大、表格复制以及 SVG、PNG、CSV 下载，PDF 使用浏览器打印窗口。

## 版式配置

默认配置维护00—07表的内容职责及四个网页入口。03按物质重复标题行与两列分析块；06、07分别映射目标鱼与参考蛋白。来源目录放在04实验记录之后。

03 长文本自动续行。对应工作表的 `row_height` 可设置 `maximum`（默认 380 pt）、`line_spacing`（默认 1.55）及 `padding`（默认 8 pt）；列宽、字体沿用配置和模板。

其他格式可以用 `--profile` 指定 JSON：`workbook.template` 相对于配置文件；`sheets` 选择模板工作表、记录集合、字段、表头行、样式样本行及冻结位置。`kind:"blocks"` 表示纵向分析块，`kind:"table"` 表示记录表。网页 `sections[].blocks` 可选正文、记录表、物质详情及图形面板；`web.theme` 调整颜色。集合、字段、表数和入口数量由配置决定。

## 生成

`presentation.json` 包含 `analysis`（报告 JSON 路径）、`analysis_sha256`，可选 `profile` 和 `inputs[{path,sha256}]`。相对路径从 presentation 文件所在目录解析。

```text
python .fish-toxicology/tools/render_reviewed.py analysis/presentation.json --output deliverables/format-preview --stage preview
```

先检查实际生成的每张工作表、网页筛选和导出。科学内容或字段映射有误时修正分析 JSON 后重导出。格式预览不登记研究完成。

内容复核完成后，在 presentation 中添加 `review:{path,sha256}`。该文件记录 `record_type:"publication_review"`、本题 `project_id / analysis_version`、`publication_sha256`、`chemical_ids`、实际 `reviewer`、`decision` 与具体 `findings`；再用默认的 `--stage reviewed` 生成。publication哈希使用 `report_model.digest`，文件哈希使用SHA-256。

需要独立图版文件时，浏览器可直接下载；安装Playwright及Chromium的环境也可运行：

```text
node .fish-toxicology/tools/export_figures.cjs deliverables/format-preview
```

该命令复用网页中的绘图函数，生成180 mm宽的SVG、PNG、PDF和CSV。系统已有Edge或Chrome时可用 `--browser <可执行文件路径>`。

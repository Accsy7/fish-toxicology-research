# 来源条件与完成检查

适用于 1.5.1-rc.1 及后续的新分析。旧成果保留原文件和审核状态，不补写“通过”。00—07 工作簿的列与职责不变。

## 检索

`toxicity --term "norfloxacin" --species 30732` 可用本地化学标识关联查询。DuckDB 不可用时仍返回本地 SQLite 范围，并在 `retrieval_diagnostics` 标明未查到的目录类型。

物质查询无结果时，查看身份解析、物种、支持类型和分页状态，再按来源交叉核对：

```text
research.py --root <工作包> toxicity --species 30732 --source 10.1016/j.jhazmat.2025.139168
research.py --root <工作包> toxicity --species 30732 --endpoint mineralized
```

`--source` 与 `--endpoint` 是观测记录筛选条件。无匹配不证明文献中没有记录。不得仅凭 chemical_class、某个终点域或名称包含关系确定家族范围；先核对物质身份，再检查相关终点域。

## 条件保留

查询及提取返回 `experimental_context` 和 `evidence_binding`，保留来源记录编号、物质/混合物身份、浓度及限定符、暴露时长、测量年龄及时间口径、对照、显著性、来源定位和未解决字段冲突。一个原始观测保持一条记录；不能按相同数值去重，也不能把 SQL 多表连接的重复行当成独立实验。

保存查询 JSON 后，用工具生成条件输入，无须重新抄写：

```text
python <工具目录>/evidence_contract.py --packet <查询结果.json> --output <分析目录>/evidence-fields.json
```

将输出的 `evidence_inputs`、`evidence_records` 合并到正式分析。路径相对正式分析目录。每条 `experiments` 用 `evidence_ids` 引用来源，`preserved_conditions` 按同序引用 `/evidence_records/EV1/observation/conditions`（可用 `$ref`）。多物质、多浓度、多时间点分别记录；汇总行标 `record_kind: source_summary`，保留逐条 `condition_variants`。混合物结果不得归为每个成分的单独效应。

库中没有的原文数据仍可使用：先实际阅读并保存 PDF/正文，逐条件填 `observations`，每条含 record_id、source_reference、species、endpoint、value、unit、qualifier、conditions 及 `source_material:{path,sha256,locator}`。未知值用 null。运行 `evidence_contract.py --extraction <原文提取.json> --output <来源包.json>`，再用上面的 `--packet` 绑定来源包。工具只核对文件和字段，不代替原文提取或内容复核；结果必须区分原始/归一化指标及各剂量的阳性与未显著。

XLSX 和网页会在原有条件、结果单元格中带出这些绑定字段，不改变列布局。原始字段缺失仍为未知；不从图号、组名推断 F0/F2，不将空显著性写成阴性，不将通用畸形直接改称骨骼毒性。

`comparisons.type: same_condition_potency` 的 `evidence_ids` 必须引用实际记录。检查物种、终点、来源研究、暴露/测量时间、对照和剂量口径。缺失字段写入 `unknown_conditions` 并说明影响，不能同时标 `equivalence: confirmed`。已知的不同条件不能靠注释豁免。

## 研究目标与登记

正式分析增加 `research_completion`：

```json
{
  "schema_version": "1.0",
  "objective_status": "partial",
  "research_question": "与课题配置一致",
  "comparison_conditions": "与课题配置一致",
  "candidate_judgments": [
    {"chemical_id":"A","prediction_ref":"/chemicals/A/prediction","basis_ref":"/chemicals/A/basis","counterevidence_ref":"/chemicals/A/doubt"}
  ],
  "risk_relations": [],
  "unresolved_impact": "尚未完成的目标及其影响"
}
```

实际完成相对风险比较后，`risk_relations` 记录 `members`、`relation`（higher、lower、indistinguishable_under_conditions、unresolved）、`purpose: relative_target_endpoint_risk`、`target_endpoint`、`conditions`、`judgment_ref` 和 `basis_ref`。指针引用正式分析实际判断。实验优先级不能替代风险比较；全为未知不能写 complete。允许 partial 交付，不要求编造顺序。

内容复核记录增加 `review_mode`（self_review、independent_ai、independent_human），如实写身份。`open_blockers` 必须列出实际阻断问题；`findings` 每项含 id、severity、status、basis，resolved 另写 resolution。外部审核 not_accepted/rejected/changes_requested 不能被总状态 accepted 覆盖。程序无法证明科学推导正确；实际复核仍须对照原文，尤其检查缺失终点、归一化后阴性、统计处理和跨物种类推。

完成记录用 `schema_version: 2.0.0`，其 `objective_status` 与正式分析一致。登记 manifest 增加 `completion: {"path":"完成记录.json","sha256":"实际文件哈希","project":"课题配置.json"}`；路径相对 manifest。登记前重新执行检查，partial 以 partial 登记，不提升为科学研究完成。渲染器不生成审核或完成记录。

`scientific_outputs` 四项均指向本次正式分析文件，具体判断通过 `research_completion` 的指针核对；XLSX、网页和图版仍在交付 manifest 单独登记。来源汇总行的 `condition_variants` 为逐证据的 `{evidence_id, endpoint, conditions}` 数组，条件可引用相应 evidence_records 字段。

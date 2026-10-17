<p align="center">
  <img src="docs/assets/research-cover.png" alt="鱼类毒性研究工作流：证据分析、风险比较、实验选物" width="100%">
</p>

<p align="center">
  <b><a href="https://github.com/Accsy7/fish-toxicology-research/releases/latest/download/fish-toxicology-research-workpack.zip">下载完整工作包</a></b>　·　
  <a href="docs/装载教程.md">装载教程</a>　·　
  <a href="docs/工作原理.md">工作原理</a>
</p>

面向**鱼类与有机污染物毒性研究**的AI辅助工作流。整合文献、实验和计算证据，比较候选物的相对风险，选择实验代表物，并生成可追溯的研究成果。

## 开始使用

1. **下载并解压工作包**，准备自己的课题文件夹。完整包含资料库；GitHub的Source code压缩包仅含源码。
2. 按[装载教程](docs/装载教程.md)选择客户端，将`toolkit/INSTALL.md`交给AI：**“把这个研究工具接入当前项目。”**
3. 说明研究问题，附上已有资料或实验安排。例如：

   > 研究双酚类对斑马鱼的雌激素相关毒性，以BPA为参照，比较风险并选出实验代表物。

成果保存在课题目录的`research/`中，原始资料与旧版本保留。

## 如何工作

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/workflow-mobile.svg">
  <img src="docs/assets/workflow.svg" alt="先整理证据，由AI推导，再复核原材料与判断，统一生成交付" width="100%">
</picture>

AI负责证据解释与科学判断，工具负责记录、计算和明确矛盾检查。预测保留条件、反证与置信程度；风险分组和实验名单分别形成。三种交付读取同一份审定分析。[查看详细原理 →](docs/工作原理.md)

## 交付内容

| 科研图版 | XLSX工作簿 | 交互网页 |
| :--- | :--- | :--- |
| SVG、PDF、PNG与对应数据 | 00—07：预测、依据、实验与蛋白记录 | 概览、筛选、逐物质详情与来源 |

网页正文和表格支持复制到Word。物种、候选范围、通路与实验条件由课题确定。

<details>
<summary>适用范围与验证状态</summary>

用于组织证据、提出条件预测和支持实验选物。已完成本地安装、资料查询和XLSX／网页导出检查；各客户端界面尚未逐一实测，新的真实课题完整科学迁移验收尚未完成。预测可靠性取决于证据质量、条件可比性与机制适用性。

客户端操作见[装载教程](docs/装载教程.md)，版本文件见[Releases](https://github.com/Accsy7/fish-toxicology-research/releases)。

</details>

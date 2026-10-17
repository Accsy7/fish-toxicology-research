<p align="right"><a href="README.md">English</a> · <strong>简体中文</strong></p>

<p align="center">
  <img src="docs/assets/research-cover.png" alt="鱼类毒性研究插件 · Fish Toxicology Research Plugin" width="100%">
</p>

<p align="center">
  <strong><a href="https://github.com/Accsy7/fish-toxicology-research/releases/latest/download/fish-toxicology-research-workpack.zip">下载完整工作包</a></strong>　 /　
  <a href="https://github.com/Accsy7/fish-toxicology-research/blob/main/docs/装载教程.md">装载教程</a>　 /　
  <a href="docs/工作原理.md">推导与计算原理</a>
</p>

面向**鱼类与有机污染物毒性研究**的AI插件，集成SQLite数据库、数据库前端、AI分析与计算工具，用于风险比较和实验代表物选择。

## 插件组成

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/workflow-mobile.svg">
  <img src="docs/assets/workflow.svg" alt="SQLite数据库与前端：化合物 / 实验效应 / 蛋白质。AI分析：风险分组 / 实验代表物。计算工具：数据查询与计算记录核查。" width="100%">
</picture>

AI结合研究资料、实验条件和反证，提出可检验的预测。

## 开始一个课题

1. **准备项目。** 下载并解压完整工作包，另建自己的课题文件夹。
2. **装载插件。** 按[教程](https://github.com/Accsy7/fish-toxicology-research/blob/main/docs/装载教程.md)选择客户端，将包内`toolkit/INSTALL.md`交给AI：**“把这个研究工具接入当前项目。”**
3. **提出研究问题。** 说明物种、候选物和关注的效应，附上已有资料或实验安排。例如：

   > 研究双酚类对斑马鱼的雌激素相关毒性，以BPA为参照，比较风险并选出实验代表物。

成果存入课题目录的`research/`。下次打开同一项目即可继续。

## 研究成果

| 科研图版 | 分析工作簿 | 交互报告 |
| :--- | :--- | :--- |
| SVG · PDF · PNG<br>图注与对应数据 | 00—07 XLSX<br>预测、依据与实验记录 | 网页概览与逐物质详情<br>筛选、来源与文件下载 |

<details>
<summary><strong>下载内容与适用范围</strong></summary>

- **完整工作包**包含插件、SQLite数据库快照、SQL表结构和浏览前端；**源码仓库**包含skill、查询与导出程序、模板和客户端适配文件。
- 资料库收录化合物身份与结构、实验条件与效应、基因与蛋白及来源记录，使用时保持只读。新增课题按实际范围补充资料。
- 工具提供查询取证、计算记录核查、绘图和导出。分子对接等专项计算由AI根据适用性另行配置。

</details>

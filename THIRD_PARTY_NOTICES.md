# Third-party notices / 第三方许可与署名

## Software and icons / 软件与图标

| Component / 组件 | Terms and attribution / 条款与署名 |
| --- | --- |
| openpyxl 3.1.5 | MIT; copyright openpyxl contributors. The workpack retains `toolkit/vendor/licenses/openpyxl/LICENCE.rst`. / 保留上游版权及完整许可。 |
| et_xmlfile 2.0.0 | MIT and the Python license for included Python-derived code; see `toolkit/vendor/licenses/et_xmlfile/LICENCE.rst`, `LICENCE.python` and `AUTHORS.txt`. / 同时保留 MIT、所含 Python 衍生代码的许可和作者名单。 |
| 3Dmol.js 2.5.5 | BSD-3-Clause; University of Pittsburgh and contributors. Included GLmol, Three.js and jQuery notices remain in `database-browser/licenses/3dmol/`. GLmol's MIT option is used. / 保留其内含组件署名。 |
| vis-network 10.1.2 | MIT or Apache-2.0; Almende B.V. and visjs contributors. Both upstream texts remain in `database-browser/licenses/vis-network/`. / 保留上游双许可文本。 |
| Browser runtime dependencies / 网页运行依赖 | Package names, versions, upstream archives, checksums and license-file paths are listed in `LICENSES/third-party/browser-runtime/inventory.json`. The browser uses React 19.2.8, React DOM 19.2.8, Scheduler 0.27.0 and html-to-image 1.11.13 (MIT). esbuild 0.27.4 (MIT) is the build tool. / 网页运行依赖及构建工具 esbuild 均附完整 MIT 许可。 |
| Molecular and network viewer dependencies / 分子与网络视图依赖 | Twelve additional locked entries, including pako, UPNG, IOBuffer, netcdfjs, Hammer.js, vis-data and vis-util, are listed with their licenses in `LICENSES/third-party/viewer-dependencies/inventory.json`. / 按 3Dmol.js 和 vis-network 上游构建锁文件补充 12 项依赖条目及其许可。 |
| Tabler Icons 3.35.0 | MIT; Copyright © 2020–2025 Paweł Kuna. Existing notice: `database-browser/licenses/profile-icons/LICENSE`. / 使用的图标及来源见附件清单。 |
| Microsoft Fluent UI System Icons | MIT; Microsoft Corporation. Applies to the database, document, table and code icons identified in `LICENSES/third-party/icon-sources.json`. / 对应数据库、文档、表格和代码图标。 |

## Data and source material / 数据与来源资料

| Source / 来源 | Retained material and terms / 收录内容与条款 |
| --- | --- |
| US EPA ECOTOX | Selected experimental records from the 2026-09-15 snapshot, with source-paper citations. EPA-produced data are generally public domain under the [EPA data policy](https://edg.epa.gov/EPA_Data_License.htm), subject to any dataset-specific notice. Credit: U.S. Environmental Protection Agency, ECOTOX Knowledgebase. / 收录该快照中的实验记录和原论文引文，保留 EPA 及论文来源。该政策针对 EPA 编制的数据，论文原文另有版权。 |
| US EPA ToxCast via PubChem | BioAssays 2282933, 2282968, 2282965 and 2283005, deposited by EPA ToxCast (PubChem source 30476). Retain assay identifiers and EPA attribution; see [EPA open computational-toxicology data](https://www.epa.gov/comptox-tools/computational-toxicology-and-exposure-apis). / 保留测试编号和 EPA 署名。 |
| PubChem / NCBI | Chemical identifiers and calculated structure properties. Credit PubChem, National Library of Medicine, and the record identifiers. [NCBI policy](https://www.ncbi.nlm.nih.gov/home/about/policies/) distinguishes government information and molecular data from contributed copyrighted material. / 收录化合物标识及计算得到的结构属性，保留 CID、来源 URL 和 PubChem 署名；第三方提交的文字不因公开检索而获得统一授权。 |
| ChEBI | Compound names, structural representations and ontology relations retrieved on 2026-10-18; CC BY 4.0, Chemical Entities of Biological Interest, EMBL-EBI. [Terms](https://www.ebi.ac.uk/chebi/about). Source identifiers and links are included in the database. / 数据库保留 ChEBI 署名、来源编号和条目链接。 |
| UniProt | Protein annotations and identifiers, including function text. CC BY 4.0, UniProt Consortium; [license](https://www.uniprot.org/help/license), [machine-readable policy](https://rest.uniprot.org/help/license). The records were selected and reorganized for this database; original accession links are retained. / 蛋白注释按 CC BY 4.0 使用，保留 UniProt Consortium 署名与条目链接；本库对记录进行了选择和重组。 |
| Gene Ontology | GO terms, references and evidence codes carried within UniProt annotations. CC BY 4.0, Gene Ontology Consortium; [terms](https://geneontology.org/docs/go-citation-policy/). The package does not identify a separate GO release; accession-level source links and the bundled snapshot are retained. / GO 条目来自随包 UniProt 注释，未单独记录 GO 发行号，保留条目来源和本地快照。 |
| Ensembl | Gene identifiers and annotations, including upstream HGNC/ZFIN labels. Ensembl-generated data are available without restriction, with third-party rights retained; [Ensembl disclaimer](https://www.ensembl.org/info/about/legal/disclaimer.html) and [official source of that notice](https://github.com/Ensembl/ensembl-webcode/blob/release/116/htdocs/info/about/legal/disclaimer.html). / 保留 Ensembl 来源及 HGNC、ZFIN 等原始标识。 |
| AlphaFold Protein Structure Database | [A0A3B3BZY6](https://alphafold.ebi.ac.uk/entry/A0A3B3BZY6) and [A0A3B3E009](https://alphafold.ebi.ac.uk/entry/A0A3B3E009) models: CC BY 4.0, Google DeepMind and EMBL-EBI; [database attribution](https://alphafold.ebi.ac.uk/). Original PDB headers and their [Jumper et al. citation](https://doi.org/10.1038/s41586-021-03819-2) are retained. Receptor PDBQT files are prepared derivatives for docking. / 两份原始 PDB 保留头部引文；受体 PDBQT 为对接准备的衍生文件。 |
| Scientific publications / 研究论文 | Bibliographic identifiers, extracted measurements and project-written research notes. Article text and figures retain publisher/author rights. Paper-level entries are listed in `source-license-register.csv`. / 收录引文、实验数值和项目整理文字。论文版权及全文许可不由本项目另行授予。 |

The database's original selection and arrangement use ODC-By 1.0. Source contents follow the terms above. Preserve these notices with SQLite, SQL, CSV, XLSX and HTML exports.

数据库原创选择和编排采用 ODC-By 1.0，来源内容按上表各自条款使用。分发 SQLite、SQL、CSV、XLSX 和 HTML 导出文件时一并保留这些说明。

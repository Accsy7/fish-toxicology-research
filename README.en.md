<p align="right"><a href="README.md">简体中文</a> · <strong>English</strong></p>

<p align="center">
  <img src="docs/assets/research-cover.png" alt="Fish Toxicology Research Plugin · 鱼类毒性研究插件" width="100%">
</p>

<p align="center">
  <strong><a href="https://github.com/Accsy7/fish-toxicology-research/releases/latest/download/fish-toxicology-research-workpack.zip">Download full package</a></strong>　 /　
  <a href="docs/INSTALL.en.md">Installation</a>　 /　
  <a href="docs/METHODS.en.md">Reasoning &amp; computation</a>
</p>

An AI plugin for **fish toxicology and organic contaminant research**. It combines a SQLite evidence database, a database browser, an evidence-based reasoning skill, and computational and visualization tools to compare candidate risks, select compounds for experiments, and produce research outputs.

## What is included

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/workflow-mobile-en.svg">
  <img src="docs/assets/workflow-en.svg" alt="A database for chemical, experimental and protein evidence; AI reasoning for mechanisms and risk groups; tools for queries, calculation records and consistent exports." width="100%">
</picture>

The AI weighs sources, conditions and counterevidence to form testable predictions. Risk groups and experimental selections are determined separately. After content review, figures, XLSX and web reports use the same reviewed analysis. [Explore the approach →](docs/METHODS.en.md)

## Start a study

1. **Prepare your project.** Download and extract the full package, then create a separate folder for your study.
2. **Load the plugin.** Follow the [client guide](docs/INSTALL.en.md). Give the AI the package's `toolkit/INSTALL.md` and ask: **“Connect this research tool to the current project.”**
3. **Describe the research question.** Specify the species, candidates and effects of interest. Add existing papers or experimental plans. For example:

   > Study the estrogen-related toxicity of bisphenols in zebrafish. Use BPA as the reference, compare relative risks, and select representative compounds for experiments.

Outputs are saved in your project's `research/` directory. Reopen the same project to continue.

## Research outputs

| Scientific figures | Analysis workbook | Interactive report |
| :--- | :--- | :--- |
| SVG · PDF · PNG<br>Captions and underlying data | 00–07 XLSX<br>Predictions, evidence and experiments | Web overview and candidate details<br>Filters, sources and downloads |

Web text and tables can be copied into Word. Species, candidate scope, pathways and experimental conditions are defined for each study.

<details>
<summary><strong>Package contents and scope</strong></summary>

- The **full package** includes the plugin, a SQLite database snapshot, its SQL schema and a browser. The **source repository** includes the skill, query and export programs, templates and client adapters.
- The database stores chemical identities and structures, experimental conditions and effects, genes, proteins and source records. It is used read-only. New studies supplement the evidence for their own scope; historical judgments retain their original conditions.
- Tools cover evidence queries, calculation-record checks, plotting and exports. Specialized calculations, such as molecular docking, are configured separately when appropriate.
- Local installation, database queries and XLSX/web exports have been checked. Verification across all client interfaces and full scientific transfer to a new non-BMP study remain incomplete. Predictions retain their conditions and confidence; reliability depends on evidence quality and method suitability.

</details>

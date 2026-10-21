<p align="right"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>

<p align="center">
  <img src="docs/assets/research-cover.png" alt="Fish Toxicology Research Plugin · 鱼类毒性研究插件" width="100%">
</p>

<p align="center">
  <strong><a href="https://github.com/Accsy7/fish-toxicology-research/releases/download/v1.5.1-rc.1/fish-toxicology-research-software-1.5.1-rc.1.zip">Download software prerelease</a></strong>　 /　
  <a href="https://github.com/Accsy7/fish-toxicology-research/blob/main/docs/INSTALL.en.md">Installation</a>　 /　
  <a href="docs/METHODS.en.md">How it works</a>
</p>

An AI plugin for studying **the toxicity of organic pollutants in fish**. It combines a SQLite database, a database frontend, AI analysis and computational tools to compare risks and select compounds for experiments.

## What is included

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/workflow-mobile-en.svg">
  <img src="docs/assets/workflow-en.svg" alt="SQLite database and frontend: compounds, experimental effects and proteins. AI analysis: risk groups and representative compounds. Computational tools: data queries and calculation checks." width="100%">
</picture>

The AI uses research findings and experimental conditions to make testable predictions, taking conflicting evidence into account.

## Start a study

1. **Prepare your project.** Download and extract the software package, then create a separate folder for your study.
2. **Load the plugin.** Follow the [client guide](https://github.com/Accsy7/fish-toxicology-research/blob/main/docs/INSTALL.en.md). Give the AI the package's `toolkit/INSTALL.md` and ask: **“Connect this research tool to the current project.”**
3. **Describe the research question.** Specify the species, candidates and effects of interest. Add existing papers or experimental plans. For example:

   > Study the estrogen-related toxicity of bisphenols in zebrafish. Use BPA as the reference, compare relative risks, and select representative compounds for experiments.

Outputs are saved in your project's `research/` directory. Reopen the same project to continue.

## Research outputs

| Scientific figures | Analysis workbook | Interactive report |
| :--- | :--- | :--- |
| SVG · PDF · PNG<br>Captions and underlying data | 00–07 XLSX<br>Predictions, evidence and experiments | Web overview and candidate details<br>Filters, sources and downloads |

<details>
<summary><strong>Package contents and scope</strong></summary>

- The **1.5.1-rc.1 software package** contains the skill, query and export programs, templates, client adapters and Excel dependencies. Database catalog **0.4.2-local.1** and the approved independent frontend **1.13.1-local.1** are separate components. The 1.5.0 full workpack remains a historical release.
- The database stores chemical identities and structures, experimental conditions and effects, genes, proteins and source records. New studies supplement the evidence for their own scope.
- Tools cover evidence queries, calculation-record checks, plotting and exports. Specialized calculations, such as molecular docking, are configured separately when appropriate.

</details>

## Version 1.5.1-rc.1 — prerelease

This prerelease adds source-based retrieval diagnostics, per-observation experimental conditions and explicit research-completion checks. The installer binds portable external catalogs with `--catalog` and preserves existing research, data and frontend settings. Targeted engineering regressions are separate from new-topic scientific validation.

[Release notes](CHANGELOG.md) · [Installation and updates](INSTALL.en.md)

## License

Code: [MIT](LICENSE). Research instructions, documentation, figures and templates: [CC BY 4.0](LICENSES/CC-BY-4.0.txt). Database compilation: [ODC-By 1.0](LICENSES/ODC-By-1.0.txt). Code examples use MIT; original explanatory text in the database uses CC BY 4.0. Third-party content retains its own [licenses and attribution](THIRD_PARTY_NOTICES.md).

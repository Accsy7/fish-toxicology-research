# How it works

[简体中文](工作原理.md) · [Project overview](../README.md) · [Installation](INSTALL.en.md)

The Fish Toxicology Research Plugin helps researchers compare the potential effects of organic pollutants and decide which experiments to prioritize. It brings together papers, experimental records and computational results to produce predictions, supporting evidence and questions that could change the assessment of each candidate.

## Why use AI?

Before an experiment, researchers often face many candidates with uneven evidence. Some compounds have fish phenotype data; others have only cellular or molecular findings. Species, exposure concentrations, durations and endpoints differ. Choosing compounds requires understanding what each result supports, whether studies are comparable and which questions remain open.

Large language models can process natural-language materials, connect concepts across documents and select queries or calculations for a question. These abilities make them useful for extracting findings, comparing conditions, interpreting mechanisms and organizing hypotheses. For a chemical family without a complete set of toxicity data collected under common conditions, existing evidence can support conditional predictions. Suitable, validated quantitative models can also contribute to the comparison.

Published work illustrates this approach. ChemCrow combined a language model with chemistry tools for literature queries, calculations and synthesis-related tasks. Co-Scientist developed hypotheses from research goals and prior evidence, then tested them experimentally in the biomedical applications studied. [ChemCrow, 2024](https://www.nature.com/articles/s42256-024-00832-8) · [Co-Scientist, 2026](https://www.nature.com/articles/s41586-026-10644-y)

![Evidence from molecular, cellular and fish studies is compared by species, exposure, duration, endpoint and source to inform risk groups, compound selection and validation questions.](assets/methods-evidence.png)

**Figure 1 | Compare evidence before choosing experiments.** Molecular, cellular and fish findings each carry their own experimental conditions. Candidate symbols and groups illustrate the comparison process.

## How a language model processes the evidence

**Training provides a basis for working with language and concepts.** An autoregressive language model learns by predicting subsequent text fragments and adjusting its parameters. Large-scale training captures statistical relationships among words, concepts and forms of expression. Instructions and examples in the current context can guide the model on a new task, supporting reading, summarization and comparison. [Brown et al., 2020](https://arxiv.org/abs/2005.14165)

**A Transformer combines information in context.** Text is split into fragments called tokens and converted into numerical vectors with position information. Self-attention assigns weights to information at different positions; feed-forward networks further transform these representations. Repeated layers allow a word's representation to change with its context. For example, when processing a statement about decreased receptor activity, the surrounding description of the experimental system, treatment and assay also enters the computation. [Vaswani et al., 2017](https://proceedings.neurips.cc/paper/7181-attention-is-all-you-need.pdf)

**The response is generated incrementally.** The model computes a distribution over the next token, generates a new fragment and continues. The plugin supplies the research question, retrieved source text and tool results as context for this process. Loading the plugin uses an existing model; queried records inform the current analysis while the model parameters remain unchanged.

![Training produces model parameters. At use time, the question and retrieved evidence pass through tokenization, embeddings, Transformer layers and incremental generation.](assets/methods-transformer.png)

**Figure 2 | From evidence to model output.** A simplified autoregressive Transformer: a, training; b, use; c, attention as weighted information combination. Details such as normalization are omitted. Weights and probability bars are illustrative. Attention describes information processing within the model; biological causation requires experimental and other independent evidence.

## How the plugin applies these capabilities

**The database supplies inspectable records.** The SQLite database and its frontend contain chemical identities and structures, experimental conditions and effects, proteins and sources. The AI retrieves candidate records, checks the original material and searches for additional public evidence needed by the study. Retrieved material becomes part of the context, sharing the principle of using external evidence described in retrieval-augmented generation. The plugin currently accesses it through database queries and file reading. [Lewis et al., 2020](https://arxiv.org/abs/2005.11401)

**The research skill specifies the questions to answer.** For every candidate, the AI develops a prediction relative to a reference compound, with supporting evidence, applicable conditions and counterevidence, then ranks or groups the full candidate set. When findings conflict, the analysis examines differences in species, exposure or measurement level and explains how they affect the judgment. Researchers can inspect the reasons for compound selection and identify where further evidence is needed.

**Tools perform repeatable operations.** The AI requests a query or calculation, a program returns the result, and the AI uses it in the analysis. The plugin includes evidence extraction, calculation-record checks, plotting and export tools. Specialized calculations, such as molecular docking, are configured for the study. Figures, XLSX and the web report use the same reviewed analysis so researchers can examine the same predictions and evidence in different formats.

This combination still requires checking original records, method suitability and the scientific inference. In ChemCrow's evaluation, a language-model evaluator could favor fluent, complete-looking responses while experts judged chemical correctness differently. The plugin therefore calls for review of the scientific content. Its prediction quality and any reduction in experimental work must be established through comparisons and experiments in the relevant study. [ChemCrow evaluation](https://www.nature.com/articles/s42256-024-00832-8)

## How the analysis helps with experiments

Researchers first receive a comparison of all candidates: which compounds are expected to have stronger effects, which may be tied and which evidence explains the differences. Available experimental slots are then assigned to compounds that answer distinct questions. One might test a stronger predicted effect, another distinguish two mechanistic explanations, and another test whether a structural change alters activity. A reference compound provides a common basis for comparison.

For each selected compound, the analysis also states which possible result would change which judgment. The following teaching example considers whether a receptor response contributes to an effect in fish.

![A proposed candidate–receptor–fish-effect relationship is updated when both responses occur, only the receptor response occurs, or the fish effect is unchanged after effective receptor blockade.](assets/methods-experiments.png)

**Figure 3 | Turn a hypothesis into a discriminating experiment.** Dotted arrows indicate proposed links. The figure contains no actual compound rankings or experimental results. Interpretation requires comparable exposure, an appropriate viability background, a suitable observation window and adequate detection capability; blockade experiments also require confirmed effectiveness and specificity.

| Possible observation | Effect on the judgment |
| --- | --- |
| Both the receptor response and fish effect occur | Adds support for an association; test whether the receptor contributes to the effect. |
| The receptor responds, but the fish effect is absent | Lower the predicted fish effect under these conditions and reassess the inference from receptor response to the whole-organism endpoint. |
| The fish effect is essentially unchanged despite effective, specific receptor blockade and sufficient ability to detect the expected difference | Reduce support for dependence on that receptor and investigate other pathways. |

Each experimental slot therefore has a defined purpose. New results update the relevant compound's assessment, followed by consideration of untested members with similar mechanisms and conditions. Evidence, the reasons behind judgments and open experimental questions remain in the project files so the team can discuss compound selection, assign work and continue the study.

## Papers and figure references

The three figures are original illustrations for this project. Figure 2 draws on the layered presentation in Transformer Figures 1–2 and the training/use distinction in GPT-3 Figure 1.1. The plugin and experiment sections draw on how ChemCrow Figure 1 and Co-Scientist Figure 1 organize tool use, hypotheses and experimental testing.

1. Vaswani, A. et al. **Attention Is All You Need.** NeurIPS (2017). [Paper](https://proceedings.neurips.cc/paper/7181-attention-is-all-you-need.pdf)
2. Brown, T. B. et al. **Language Models are Few-Shot Learners.** NeurIPS (2020). [Paper](https://arxiv.org/abs/2005.14165)
3. Lewis, P. et al. **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.** NeurIPS (2020). [Paper](https://arxiv.org/abs/2005.11401)
4. Bran, A. M. et al. **Augmenting large language models with chemistry tools.** *Nature Machine Intelligence* 6, 525–535 (2024). [Paper](https://doi.org/10.1038/s42256-024-00832-8)
5. Gottweis, J. et al. **Accelerating scientific discovery with Co-Scientist.** *Nature* 655, 487–496 (2026). [Paper](https://doi.org/10.1038/s41586-026-10644-y)

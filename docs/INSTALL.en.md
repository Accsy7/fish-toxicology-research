# Installation

**English** · [简体中文](https://github.com/Accsy7/fish-toxicology-research/blob/main/docs/装载教程.md) · [Project homepage](https://github.com/Accsy7/fish-toxicology-research#readme)

## 1. Choose your AI application

Instructions are provided for WorkBuddy, DeepSeek Harness, Claude Code, Claude Cowork/Desktop, Codex and ChatGPT. Open only the section for your application below.

## 2. Download and prepare

1. **Download the full package.** Get [fish-toxicology-research-workpack.zip](https://github.com/Accsy7/fish-toxicology-research/releases/latest/download/fish-toxicology-research-workpack.zip), which includes the plugin, SQLite database and database frontend.
2. **For local use.** Extract the entire ZIP and keep its folder structure. The extracted tool folder holds the plugin and database. Create a separate study folder, or use an existing one, for your papers, data and research outputs. Open the study folder in your AI application, then follow the next section to load the plugin. Multiple studies can share one tool folder.
3. **For cloud use.** In ChatGPT web or cloud Work, upload the full package ZIP and your study materials, then follow the corresponding section below.

GitHub's **Code → Download ZIP** and the **Source code** release assets provide the source repository. The database and its frontend are distributed with `fish-toxicology-research-workpack.zip`. Choose the full package above to use the database.

## 3. Load the plugin

<details>
<summary>WorkBuddy</summary>

1. Install [WorkBuddy](https://www.workbuddy.cn/work/), select your study folder and use Agent mode.
2. Under Skills → Add skill → Upload skill, import `adapters/workbuddy/fish-toxicology-research.zip` and enable it.
3. Give the AI `toolkit/INSTALL.md` from the package and say: **“Connect this research tool to the current project.”**

[Official skill guide](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)

</details>

<details>
<summary>DeepSeek Harness</summary>

1. Download [Harness](https://www.deepseek.com/zh/harness/) and open your study folder.
2. Give the AI `toolkit/INSTALL.md` and say: **“Connect this research tool to the current project.”**
3. Once connected, describe your research question.

[Official skill guide](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/skills)

</details>

<details>
<summary>Claude Code, including Code mode in Desktop</summary>

1. Open or install [Claude Code](https://code.claude.com/docs/en/overview) and enter your study folder.
2. Give the AI `toolkit/INSTALL.md` and say: **“Connect this research tool to the current project.”**
3. Describe your research question. You can also invoke `/fish-toxicology-research`.

[Official skill guide](https://code.claude.com/docs/en/skills)

</details>

<details>
<summary>Claude Cowork / Desktop</summary>

1. In [Claude Desktop](https://claude.com/download), use Cowork or a task-execution mode with access to your study folder and the package.
2. Under Customize → Skills → + → Create skill → Upload a skill, upload `adapters/claude/fish-toxicology-research.zip`. Enable the skill, code execution and file creation.
3. Give the AI `toolkit/INSTALL.md` and say: **“Connect this research tool to the current project.”** For Desktop's Code mode, use the preceding instructions.

[Official upload guide](https://support.claude.com/en/articles/12512180-use-skills-in-claude) · [Cowork folder access](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork)

</details>

<details>
<summary>Codex / local work in ChatGPT Desktop</summary>

1. Open your study folder in Codex with local execution available.
2. Give the AI `toolkit/INSTALL.md` and say: **“Connect this research tool to the current project.”**
3. Describe your research question. You can also invoke `$fish-toxicology-research`.

[Official skill guide](https://learn.chatgpt.com/docs/customization/overview#skills)

</details>

<details>
<summary>ChatGPT web / cloud Work</summary>

1. Start a conversation and upload the full package ZIP and study materials. Use an environment that can extract archives, run code and create files.
2. Say: **“Read toolkit/INSTALL.md in the uploaded package and connect this research tool to the current project.”**
3. Once the AI confirms that it can read the materials and run the tools, describe your research question.

The tools run in the current conversation environment. For a new conversation, upload the package and required materials again, then repeat the loading steps. [Cloud file access](https://learn.chatgpt.com/docs/enterprise/chatgpt-work-overview#cloud-work)

</details>

## 4. Check setup and start research

The AI checks that it can read the research skill, access your materials, and run the query and export tools. Then describe your study, for example:

> Study the estrogen-related toxicity of bisphenols in zebrafish. Use BPA as the reference, compare relative risks, and select representative compounds for experiments.

Outputs include figures and data, XLSX and a web report. Local outputs are saved under `research/` in your study folder; reopen the same project to continue. Download cloud outputs to keep a copy.

## 5. If something fails

| Problem | Ask the AI |
| --- | --- |
| Skill not found | “Check this application's skill location and load the research instructions.” |
| Local files inaccessible | “Tell me which folder needs access or which files I need to provide.” |
| Database disconnected | “Check the database path. If no database is available, start with my materials and public sources.” |
| Missing dependencies | “Install the required dependencies in this project, then check queries and exports.” |

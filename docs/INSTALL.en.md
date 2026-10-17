# Installation

[简体中文](装载教程.md) · [Project overview](../README.en.md)

## 1. Choose your AI application

Instructions are provided for WorkBuddy, DeepSeek Harness, Claude Code, Claude Cowork/Desktop, Codex and ChatGPT. Open only the section for your application below.

## 2. Download and prepare

[Download the full package](https://github.com/Accsy7/fish-toxicology-research/releases/latest/download/fish-toxicology-research-workpack.zip), extract it and keep it in a stable location. Use an existing study folder or create an empty one. Multiple studies can share the tool package.

The GitHub source archive does not include the database. When using source only, the AI can connect an existing database or start with your materials and public sources.

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

1. Create a project or task and upload the package and study materials. Use an environment that can extract archives, run code and create files.
2. Say: **“Read toolkit/INSTALL.md in the uploaded package and connect this research tool to the current project.”**
3. Once the AI confirms that it can read the materials and run the tools, describe your research question.

Cloud tasks cannot read local computer paths directly. Provide accessible files. This loads the tools into the current task; it does not install an account-wide plugin. [Official plugin guide](https://learn.chatgpt.com/docs/build-plugins)

</details>

## 4. Check setup and start research

The AI checks that it can read the research skill, access your materials, and run the query and export tools. Then describe your study, for example:

> Study the estrogen-related toxicity of bisphenols in zebrafish. Use BPA as the reference, compare relative risks, and select representative compounds for experiments.

Local outputs are saved under `research/` in your study folder: figures and data, XLSX and a web report. Reopen the same project to continue. For cloud tasks, download your outputs and provide them with the package when starting another session.

## 5. If something fails

| Problem | Ask the AI |
| --- | --- |
| Skill not found | “Check this application's skill location and load the research instructions.” |
| Local files inaccessible | “Tell me which folder needs access or which files I need to provide.” |
| Database disconnected | “Check the database path. If no database is available, start with my materials and public sources.” |
| Missing dependencies | “Install the required dependencies in this project, then check queries and exports.” |

Installation, evidence retrieval and export programs have been tested. The client interfaces above have not all been verified on actual installations.

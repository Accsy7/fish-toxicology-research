# Installation and updates

[简体中文](INSTALL.zh-CN.md)

Workpack version: 1.5.0. This bundle includes the skill, query and rendering tools, default XLSX/HTML templates, a read-only database snapshot, and its browser. Python 3.10+ is required. XLSX dependencies are included.

## WorkBuddy

1. Extract the entire ZIP to a permanent folder. The database stays in this folder.
2. Create an empty research project folder.
3. Open PowerShell in the extracted bundle folder and run:

```powershell
.\Install-WorkBuddy.ps1 -ProjectPath "C:\Research\fish-test" -ReplaceManaged
```

The installer deploys the same skill and tools into the project and updates WorkBuddy's discovery entry. Existing managed components are backed up; research files and separate custom configuration are retained. If Python is unavailable, supply `-PythonPath "path to python.exe"` or use the equivalent Python command below in WorkBuddy's environment.

4. Open the new project in WorkBuddy and start a fresh conversation. Refresh the skill list or restart WorkBuddy if it still shows the previous version.
5. Ask the AI to read `.fish-toxicology/skill/SKILL.md`, run `.fish-toxicology/tools/research.py doctor`, and begin the research question.

The doctor's `bundle_version`, `components.skill`, and `components.tools` should all be `1.5.0`; `errors` and `modified_files` should be empty. Tools and defaults are in `.fish-toxicology/`; research outputs go into `research/`.

## Python commands and other clients

```text
python -B toolkit/install.py --project "absolute project path" --client workbuddy --replace-managed
python -B "project/.fish-toxicology/tools/research.py" doctor
```

Other client values are `codex`, `claude`, and `deepseek`. `portable` installs only the project entry. Uploadable skill archives are in adapters; use the installer to connect local tools and the database.

## Updating an existing project

```text
python -B toolkit/install.py --project "existing project path" --client workbuddy --update-tools --replace-managed
```

Updates preserve the database binding, research directory, and separate presentation profiles. Component backups are in `.fish-toxicology/backups/`, with original paths in index.json. Use an empty project for a new study and retain its research records.

## Rendering and configuration

Defaults provide sheets 00–07 and four report sections. The workbook, web charts, and downloads share the analysis data. Species, pathways, chemicals, and panels come from the project. Profiles configure fields, styles, sections, and search fields. See [render input](toolkit/skill/references/render-input.md).

Batch SVG/PNG/PDF export uses export_figures.cjs and requires Node.js, Playwright, and Chromium/Edge. The web report also offers chart downloads and printing. Chart data follows the same filter.

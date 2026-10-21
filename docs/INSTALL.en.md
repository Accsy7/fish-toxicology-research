# Installation and updates

Version **1.5.1-rc.1** is a software prerelease for supervised research use. It contains the skill, query and evidence checks, report tools, templates and Excel dependencies. It does not contain the scientific databases or the independent database frontend. The original 1.5.0 full workpack remains available in its historical release.

## Connect a project

1. Download the [software package](https://github.com/Accsy7/fish-toxicology-research/releases/download/v1.5.1-rc.1/fish-toxicology-research-software-1.5.1-rc.1.zip) and extract it to a permanent folder. Create a separate study folder.
2. If using the expanded database, extract the unchanged 0.4.1 baseline components into a chosen `DATA_ROOT`. Extract `observations-0.4.2-local.1.sqlite3.zip` into that same directory. The revision creates `revisions/0.4.2-local.1/` and preserves the old root observation database.
3. Give your AI the package's `toolkit/INSTALL.md` and ask it to connect the tool to your study. The AI runs the installer using the selected client's option and the real catalog path, for example:

```text
python toolkit/install.py --project STUDY_FOLDER --client codex --catalog DATA_ROOT/revisions/0.4.2-local.1/catalog.json
```

Use `claude`, `deepseek`, `workbuddy`, `both` (Codex and Claude Code) or `portable` for the corresponding environment. An uploadable skill archive is a discovery entry; local queries still require the software and readable data. Cloud conversations cannot access a Windows path without an actual file transfer and binding.

Python 3.10 or newer is required. The software ZIP includes the pure Python Excel dependencies. Optional expanded Parquet identity queries use the dependencies in `toolkit/requirements-catalog.txt`; these compiled packages are not bundled. Without DuckDB, supported SQLite queries remain available and report that Parquet identity sources are unavailable. A source checkout needs `python -m pip install -r toolkit/requirements.txt` for workbook export.

## Update an installed project

```text
python toolkit/install.py --project STUDY_FOLDER --client codex --update-tools --catalog DATA_ROOT/revisions/0.4.2-local.1/catalog.json
```

The installer backs up managed files, preserves research and custom settings, and refuses to overwrite locally modified tools unless explicitly resolved. Omitting `--catalog` retains the existing database binding; it does not apply the data revision. `--database` supports a standalone historical SQLite snapshot and is mutually exclusive with `--catalog`.

Run `python .fish-toxicology/tools/research.py doctor` from the study folder. `complete_repair_data_bound` states whether the 0.4.2 revision is connected. A passing software check does not establish a scientific conclusion or complete a new study.

## Independent frontend

The approved frontend is **1.13.1-local.1** and is maintained separately. This software package installs no database UI and does not replace an existing frontend. To use an existing frontend with the local API, supply its directory explicitly:

```text
python .fish-toxicology/tools/browse_catalog.py --frontend-dir FRONTEND_DIRECTORY
```

Do not substitute the old 1.9.0-local.6 test frontend for the approved independent frontend. The research report renderer remains included and retains the established 00–07 workbook and report formats.

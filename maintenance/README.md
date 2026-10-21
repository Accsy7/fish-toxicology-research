# Maintenance checks

Install Python dependencies with `python -m pip install -r toolkit/requirements.txt`.
Download and extract the full workpack, then set `FISH_TEST_BUNDLE` to its directory
to exercise installation, update/rollback, database and integration regressions:

```powershell
$env:FISH_TEST_BUNDLE = 'C:\Research\fish-toxicology-research-v1.5.0'
python -X utf8 -B -m unittest discover -s maintenance -p "test_*.py" -v
```

`test_renderers.py` can also run directly from a source checkout. Browser figure
regressions use `node maintenance/test_figures.cjs --browser <Chromium executable>`
with Playwright installed. The tests use synthetic data fixtures.

`python maintenance/package_skills.py` rebuilds the two uploadable skill archives.
The database/browser source and its locked build instructions are included in the
full workpack under `database-browser/browser-source.zip`.

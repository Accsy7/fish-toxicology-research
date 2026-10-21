# Maintenance checks

The 1.5.1-rc.1 software release and its data components are separate. Install `toolkit/requirements.txt` for source-only workbook tests.

```text
python -B -X utf8 -m unittest discover -s maintenance -p "test_*.py" -v
python -B -X utf8 maintenance/validate_evidence_integration.py
```

`test_portable_install.py` checks installation without data, portable external-catalog binding, retained research/frontend settings, conflict refusal and rollback using synthetic SQLite fixtures. `test_quality_contract.py` checks source conditions and completion constraints. `test_renderers.py` retains the existing synthetic report checks. Historical full-workpack tests in `test_bundle.py` require their corresponding database bundle and are skipped for this software-only release.

`maintenance/build_release.py --output OUTPUT --vendor-source PURE_PYTHON_VENDOR` builds software/source archives and adapters, with deterministic ZIP entries and hash manifests. Vendor input contains only the already distributed openpyxl and et_xmlfile libraries and their licenses. No SQLite, compiled catalog wheels, private research records or database UI are included.

Targeted real-data query regressions are recorded separately from these fixtures. No software test is a new-topic scientific validation.

"""Render a data-bound XLSX and offline interactive HTML using a replaceable profile."""
from pathlib import Path
import argparse
import copy
import json
import shutil
import sys

from report_model import digest, load, sha, validate
from render_workbook import render as workbook
from research import skill_home
from analysis_checks import materialize, check as analysis_checks
from bundle_runtime import inspect
from quality_contract import assert_analysis, review_errors, presentation_data


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def check_review(review, data, base):
    """Check review identity and content binding; scientific reasoning is read by the reviewer."""
    record = load(base / review["path"])
    if sha(base / review["path"]) != review["sha256"]:
        raise ValueError("Review file changed")
    checks = {
        "record_type": "publication_review",
        "project_id": data["project_id"],
        "analysis_version": data["analysis_version"],
        "publication_sha256": digest(data),
    }
    for key, expected in checks.items():
        if record.get(key) != expected:
            raise ValueError(f"Review {key} differs")
    if record.get("decision") not in ("accepted", "accepted_with_stated_limits") or not record.get("reviewer"):
        raise ValueError("Actual reviewer and decision required")
    if set(record.get("chemical_ids", [])) != {c["id"] for c in data.get("chemicals",data.get("candidates",[]))}:
        raise ValueError("Review chemical coverage differs")
    if not record.get("findings"):
        raise ValueError("Review must contain actual findings")
    errors=review_errors(record)
    if errors:raise ValueError('\n'.join(errors))
    return record


def web(data, profile, base, out):
    assets = skill_home() / "assets/web"
    for name in ("report.css", "renderer.css", "renderer.js"):
        shutil.copy2(assets / name, out / name)
    display = copy.deepcopy(data)
    for panel in display["panels"]:
        if panel["type"] == "image":
            src = (base / panel["path"]).resolve()
            if sha(src) != panel["sha256"]:
                raise ValueError(f"Image changed: {panel['id']}")
            dest = out / "figures" / (panel["id"] + src.suffix)
            dest.parent.mkdir(exist_ok=True)
            shutil.copy2(src, dest)
            panel["asset"] = dest.relative_to(out).as_posix()
    # JSON is embedded so the report also works from file:// without a server.
    payload = json.dumps({"data": display, "profile": profile}, ensure_ascii=False).replace("<", "\\u003c")
    (out / "report-data.js").write_text("window.REPORT=" + payload + ";\n", "utf-8")
    page = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>科研报告</title>
<link rel="stylesheet" href="report.css"><link rel="stylesheet" href="renderer.css"></head>
<body><header class="masthead"><div><p id="context"></p><h1 id="title"></h1></div>
<a class="button" href="analysis.xlsx" download>分析工作簿</a></header>
<nav class="tabs" id="tabs" role="tablist" aria-label="研究内容"></nav>
<div class="filter-bar"><label>查找<input id="search" type="search" placeholder="名称或编号"></label>
<label>分组<select id="group-filter"></select></label><label>比较物质<select id="chemical-filter"></select></label>
<button id="reset">重置</button><span id="count"></span><button id="export-family">下载筛选表</button></div>
<main id="pages"></main><dialog id="detail"><div class="dialog-head"><h2 id="detail-title"></h2>
<div><button data-copy="detail-content">复制正文</button><button data-close="detail">关闭</button></div></div>
<article class="reading" id="detail-content"></article></dialog>
<dialog id="zoom"><div class="dialog-head"><h2 id="zoom-title"></h2><button data-close="zoom">关闭</button></div>
<div id="zoom-content"></div></dialog><div id="status" role="status" aria-live="polite"></div>
<script src="report-data.js"></script><script src="renderer.js"></script></body></html>"""
    (out / "index.html").write_text(page, "utf-8")


def render(path, output, profile_path=None, stage="reviewed"):
    path, output = Path(path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Output already exists; choose a new directory")
    spec = load(path)
    runtime = inspect(Path(__file__).resolve().parents[1])
    analysis_path = (path.parent / spec["analysis"]).resolve()
    if sha(analysis_path) != spec["analysis_sha256"]:
        raise ValueError("Analysis hash differs")
    data = load(analysis_path)
    if data.get("schema_version") != "2.0":
        raise ValueError("Map legacy publication cells to named records using the documented 2.0 input")
    profile_path = Path(profile_path).resolve() if profile_path else (
        (path.parent / spec["profile"]).resolve() if spec.get("profile") else
        skill_home() / "assets/profiles/accepted.json")
    profile = load(profile_path)
    resolved = materialize(data)
    errors = validate(resolved, profile) + analysis_checks(resolved)
    if errors:
        raise ValueError("\n".join(errors))
    for item in spec.get("inputs", []):
        if sha(path.parent / item["path"]) != item["sha256"]:
            raise ValueError(f"Source input changed: {item['path']}")
    if stage == "reviewed":
        if not spec.get("review"):
            raise ValueError("A content-bound review is required; use --stage preview for format work")
        check_review(spec["review"], data, path.parent)
        assert_analysis(resolved,analysis_path.parent)
    data = presentation_data(resolved)
    template = (profile_path.parent / profile["workbook"]["template"]).resolve()
    output.mkdir(parents=True)
    write(output / "render_status.json", {"status": "rendering", "stage": stage})
    try:
        checks = workbook(data, profile, template, output / "analysis.xlsx")
        web(data, profile, path.parent, output)
        write(output / "report.json", data)
        write(output / "profile.json", profile)
        status = {
            "status": "rendered", "stage": stage, "project_id": data["project_id"],
            "analysis_sha256": sha(analysis_path), "profile_sha256": sha(profile_path),
            "template_sha256": sha(template), "workbook_readback": checks,
            "runtime": runtime,
            "research_objective_status":data.get('research_completion',{}).get('objective_status'),
            "inputs": spec.get("inputs", []),
            "files": {p.relative_to(output).as_posix(): sha(p) for p in output.rglob("*")
                      if p.is_file() and p.name != "render_status.json"},
        }
        write(output / "render_status.json", status)
    except BaseException as exc:
        write(output / "render_status.json", {"status": "failed", "stage": stage, "error": str(exc)})
        raise
    return {"output": str(output), "stage": stage, "checked_cells": checks["checked_cells"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("presentation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--stage", choices=("preview", "reviewed"), default="reviewed")
    args = parser.parse_args()
    try:
        print(json.dumps(render(args.presentation, args.output, args.profile, args.stage), ensure_ascii=False))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)

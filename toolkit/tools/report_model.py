"""Shared presentation data. Field mappings and scientific content live in input files."""
import hashlib
import json
import math
import re
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text("utf-8-sig"))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("text", json.dumps(value, ensure_ascii=False)))
    if isinstance(value, list):
        return "\n".join(text(v) for v in value)
    return str(value)


def field(record, key, default=""):
    for part in key.split("."):
        if not isinstance(record, dict) or part not in record:
            return default
        record = record[part]
    return record


def select(data, path):
    value = field(data, path, [])
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected an array of records")
    return value


def mapped(record, column):
    """A mapping may combine named fields without executable expressions."""
    if "fields" in column:
        return column.get("separator", "\n").join(text(field(record, k)) for k in
                                                column["fields"] if field(record, k) != "")
    return field(record, column["field"])


def validate(data, profile):
    errors = []
    if data.get("schema_version") != "2.0":
        return ["schema_version must be 2.0; map legacy cells to named records first"]
    for s in profile["workbook"]["sheets"]:
        if s["kind"] == "table" and len(s["columns"]) != s["columns_count"]:
            errors.append(f"profile.{s['name']}: column mapping differs from declared width")
        if not isinstance(field(data, s["collection"]), list):
            errors.append(f"profile.{s['name']}: collection {s['collection']} is not an array")
    for key in ("project_id", "analysis_version", "title"):
        if not data.get(key):
            errors.append(f"{key}: required")
    sources = data.get("sources", [])
    chemicals = data.get("chemicals", [])
    for label, records in (("sources", sources), ("chemicals", chemicals),
                           ("panels", data.get("panels", [])), ("sections", profile["web"]["sections"])):
        ids = [x.get("id") for x in records]
        if any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
            errors.append(f"{label}: IDs must be nonempty and unique")
    source_ids = {x["id"] for x in sources}
    chemical_ids = {x["id"] for x in chemicals}

    def walk(value, path):
        if isinstance(value, dict):
            for key, v in value.items():
                if key == "source_ids" and isinstance(v, list):
                    for s in v:
                        if s not in source_ids:
                            errors.append(f"{path}.source_ids: unknown source {s}")
                elif key == "chemical_ids" and isinstance(v, list):
                    for c in v:
                        if c not in chemical_ids:
                            errors.append(f"{path}.chemical_ids: unknown chemical {c}")
                else:
                    walk(v, path + "." + key)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f"{path}[{i}]")
    walk(data, "report")
    for c in chemicals:
        if c.get("status") == "complete" and not text(c.get("prediction")).strip():
            errors.append(f"chemicals.{c['id']}: completed record has no prediction")
    allowed = {"network", "matrix", "interval", "bar", "image", "scatter", "heatmap"}
    for p in data.get("panels", []):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", p["id"]):
            errors.append(f"panels.{p['id']}: unsafe file ID")
        if p.get("type") not in allowed:
            errors.append(f"panels.{p['id']}: unsupported type")
        if p["type"] == "network":
            ids = [n["id"] for n in p.get("nodes", [])]
            if len(ids) != len(set(ids)):
                errors.append(f"panels.{p['id']}: duplicate node IDs")
            for edge in p.get("edges", []):
                if edge["from"] not in ids or edge["to"] not in ids:
                    errors.append(f"panels.{p['id']}.{edge['id']}: missing endpoint")
        if p["type"] in ("matrix", "heatmap"):
            for row in p.get("rows", []):
                if len(row["values"]) != len(p["columns"]):
                    errors.append(f"panels.{p['id']}: matrix column count differs")
        if p["type"] in ("interval", "bar", "scatter"):
            if p.get("domain") and (len(p["domain"]) != 2 or p["domain"][0] >= p["domain"][1]):
                errors.append(f"panels.{p['id']}: invalid axis domain")
            for row in p.get("rows", []):
                for key in ("x", "value", "low", "high", "size"):
                    v = row.get(key)
                    scale = p.get('x_scale') if key=='x' else p.get('y_scale',p.get('scale')) if key in ('value','low','high') else None
                    if v is not None and (type(v) not in (int, float) or not math.isfinite(v) or
                                          (scale=='log' and v <= 0) or (key=='size' and v<0)):
                        errors.append(f"panels.{p['id']}.{key}: invalid numeric value")
                if row.get("low") is not None and row.get("high") is not None and row["low"] > row["high"]:
                    errors.append(f"panels.{p['id']}: interval is reversed")
    return errors

"""Inspect the actual local bundle; no network or scientific decisions."""
from pathlib import Path
import hashlib
import json
import re

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def version(path):
    header = Path(path).read_text('utf-8-sig').split('---', 2)[1]
    match = re.search(r'^\s*version:\s*[\"\']?([^\s\"\']+)', header, re.M)
    return match.group(1) if match else None

def inspect(home, hashes=True):
    home = Path(home).resolve()
    if not (home/'bundle.json').exists():
        return {'bundle_version':None,'modified_files':[],'errors':['缺少 bundle.json，请从完整工作包安装。']}
    manifest=json.loads((home/'bundle.json').read_text('utf-8-sig'))
    errors,modified=[],[]
    for rel,expected in manifest['files'].items():
        p=(home/rel).resolve()
        if not p.is_relative_to(home): errors.append('包清单路径超出工具目录：'+rel)
        elif not p.is_file(): errors.append('缺少组件：'+rel)
        elif hashes and sha(p)!=expected: modified.append(rel)
    actual=version(home/'skill/SKILL.md') if (home/'skill/SKILL.md').exists() else None
    if actual!=manifest['components']['skill']: errors.append('skill 与包清单版本不一致。')
    if home.name=='.fish-toxicology' and (home/'workspace.json').exists():
        config=json.loads((home/'workspace.json').read_text('utf-8-sig'))
        if config.get('package_version')!=manifest['version'] or config.get('skill_version')!=actual:
            errors.append('项目绑定与实际组件版本不一致。')
        for discovery in config.get('discovery_skills',[]):
            p=Path(discovery)
            if not p.exists() or version(p)!=actual: errors.append('客户端发现入口版本不一致：'+str(p))
    return {'bundle_version':manifest['version'],'components':manifest['components'],
            'tool_root':str(home),'skill':str(home/'skill/SKILL.md'),'modified_files':modified,'errors':errors}

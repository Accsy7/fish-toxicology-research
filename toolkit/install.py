"""Attach this research toolkit to an existing or empty project without replacing it."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

HOME = Path(__file__).resolve().parent
PACKAGE_ROOT = HOME.parent if HOME.name == 'toolkit' else HOME
VERSION = '1.2.3'
NAME = 'fish-toxicology-research'


def load(p):
    return json.loads(p.read_text('utf-8-sig'))


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative(p, root):
    try:
        return Path(os.path.relpath(p, root)).as_posix()
    except ValueError:  # Different Windows drives.
        return p.as_posix()


def install(project, client='both', database=None):
    project = project.expanduser().resolve()
    if (project == PACKAGE_ROOT or project.is_relative_to(PACKAGE_ROOT)
            or PACKAGE_ROOT.is_relative_to(project)):
        raise ValueError('请选择自己的课题目录，不要把工具包本身当成新课题。')
    clients = ['codex', 'claude'] if client == 'both' else [client]
    locations = {'codex': '.agents', 'claude': '.claude', 'deepseek': '.dsh'}
    destinations = {c: project / locations[c] / 'skills' / NAME for c in clients if c in locations}
    existing = project / '.fish-toxicology/install-record.json'
    if existing.exists():
        record = load(existing)
        intact = all((project / p).is_file() and digest(project / p) == h for p, h in record['files'].items())
        if (intact and record['version'] == VERSION and set(record['clients']) >= set(clients)
                and database is None):
            return {'status': 'already_installed', 'project': str(project), 'clients': record['clients']}
        raise ValueError('项目已接入工具且版本、配置或内容不同；原件已保留，请先核对现有安装记录。')
    occupied = [p for p in [project / '.fish-toxicology', *destinations.values()] if p.exists()]
    if occupied:
        raise ValueError('这些位置已有内容，本次未改动：' + '；'.join(str(p) for p in occupied))
    data = None
    if database:
        path = database.expanduser().resolve()
        if not path.is_file():
            raise ValueError('指定的数据库文件不存在。')
        data = {'file': relative(path, project), 'version': 'external_snapshot',
                'mode': 'read_only_snapshot', 'sha256': digest(path)}
    elif (HOME / 'workspace.json').exists():
        original = load(HOME / 'workspace.json').get('database')
        if original:
            data = dict(original)
            for key in ('file', 'schema', 'browser'):
                if data.get(key):
                    path = (HOME / data[key]).resolve()
                    if not path.is_file():
                        raise ValueError('工作包缺少数据库文件，请完整解压后重试。')
                    data[key] = relative(path, project)
            path = (project / data['file']).resolve()
            if digest(path) != data['sha256']:
                raise ValueError('数据库与登记版本不一致，本次未安装。')
    # Preflight is complete. Stage everything before adding files to the project.
    with tempfile.TemporaryDirectory(prefix='fish-toolkit-') as temporary:
        stage = Path(temporary)
        managed = stage / '.fish-toxicology'
        managed.mkdir()
        for folder in ('tools', 'skill', 'vendor'):
            if (HOME / folder).exists():
                shutil.copytree(HOME / folder, managed / folder,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        config = {'schema_version': '1.1', 'package_version': VERSION,
                  'skill_version': '1.3.0',
                  'skill': relative(next(iter(destinations.values())) / 'SKILL.md', project) if destinations else '.fish-toxicology/skill/SKILL.md',
                  'database': data, 'analysis_catalog': 'research/catalog.json',
                  'projects_dir': 'research', 'query_tool': '.fish-toxicology/tools/research.py',
                  'renderer': '.fish-toxicology/tools/render_reviewed.py',
                  'delivery_types': ['scientific_figures_with_data', 'xlsx_00_07', 'interactive_html']}
        (managed / 'workspace.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), 'utf-8')
        for c, dest in destinations.items():
            shutil.copytree(HOME / 'skill', stage / dest.relative_to(project),
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        files = {p.relative_to(stage).as_posix(): digest(p) for p in stage.rglob('*') if p.is_file()}
        record = {'version': VERSION, 'clients': clients, 'files': files,
                  'new_scientific_judgments': 0, 'existing_project_files_changed': []}
        (managed / 'install-record.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), 'utf-8')
        project.mkdir(parents=True, exist_ok=True)
        shutil.copytree(managed, project / '.fish-toxicology')
        for dest in destinations.values():
            shutil.copytree(stage / dest.relative_to(project), dest)
    return {'status': 'installed', 'project': str(project), 'clients': clients,
            'database_connected': bool(data), 'new_scientific_judgments': 0,
            'next': '在当前课题里读取已接入的skill，再直接提出研究问题。'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='把研究工具接入自己的项目，保留已有文件。')
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--client', choices=['codex', 'claude', 'deepseek', 'portable', 'both'], default='both')
    parser.add_argument('--database', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.project, args.client, args.database), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)

"""Install one local bundle into a project and its selected discovery entry."""
from pathlib import Path
from datetime import datetime, timezone
from contextlib import closing
import argparse, hashlib, json, os, sqlite3, sys
HOME=Path(__file__).resolve().parent
PACKAGE_ROOT=HOME.parent
NAME='fish-toxicology-research'
sys.path.insert(0,str(HOME/'tools'))
from bundle_runtime import inspect,version

def load(p): return json.loads(Path(p).read_text('utf-8-sig'))
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def encoded(v): return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def relative(p,root):
    try: return Path(os.path.relpath(p,root)).as_posix()
    except ValueError: return Path(p).as_posix()

def discovery_bytes(p,client):
    data=p.read_bytes()
    if p.name=='SKILL.md' and client=='workbuddy':
        header,body=data.decode('utf-8-sig').split('---',2)[1:]
        desc=next(x.split(':',1)[1].strip() for x in header.splitlines() if x.startswith('description:'))
        data=('---\nname: '+NAME+'\ndescription: '+json.dumps(desc,ensure_ascii=False)+
              '\ndescription_zh: '+json.dumps(desc,ensure_ascii=False)+
              '\ndescription_en: "Fish toxicology research and experiment selection."\nversion: '+json.dumps(version(p))+
              '\nauthor: "Fish toxicology research toolkit"\n---'+body).encode('utf-8')
    return data

def catalog_binding(path, project, previous=None):
    """Bind a portable external catalog without rewriting or hashing its large data files."""
    path = Path(path).expanduser().resolve()
    catalog = load(path)
    paths = {key: (path.parent / value).resolve() for key, value in catalog.get('paths', {}).items()}
    for key in ('fish_database', 'observations', 'molecular_support', 'policy'):
        if key not in paths or not paths[key].is_file():
            raise ValueError('分类资料组件缺失：' + key + '；请先解压基线数据和对应修订。')
    if not catalog.get('version'):
        raise ValueError('分类资料目录缺少版本。')
    uri = paths['fish_database'].as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.execute('PRAGMA query_only=ON')
        row = connection.execute("SELECT value FROM metadata WHERE key='database_version'").fetchone()
    if not row:
        raise ValueError('来源SQLite缺少database_version元数据。')
    data = dict(previous or {})
    for key in ('schema', 'sha256'):
        data.pop(key, None)
    data.update(file=relative(paths['fish_database'], project), version=row[0],
                catalog=relative(path, project), catalog_version=catalog['version'],
                catalog_sha256=digest(path), mode='read_only_external_catalog')
    return data


def install(project,client='portable',database=None,update=False,replace_managed=False,workbuddy_home=None,use_bundled_database=False,catalog=None):
    project=Path(project).expanduser().resolve()
    if project==PACKAGE_ROOT or project.is_relative_to(PACKAGE_ROOT) or PACKAGE_ROOT.is_relative_to(project):
        raise ValueError('请使用工具包以外的课题目录。')
    state=inspect(HOME)
    if state['errors'] or state['modified_files']: raise ValueError('安装来源不完整或已修改：'+str(state))
    manifest=load(HOME/'bundle.json')
    record_path=project/'.fish-toxicology/install-record.json'
    previous=load(record_path) if record_path.exists() else None
    if previous and not update:
        if previous.get('bundle_sha256')==digest(HOME/'bundle.json') and all(Path(p).is_file() and digest(p)==h for p,h in previous.get('managed_files',{}).items()):
            requested={'codex','claude'} if client=='both' else {client}
            if requested.issubset(previous['clients']) and database is None and catalog is None:
                return {'status':'already_installed',**inspect(project/'.fish-toxicology')}
        raise ValueError('已有安装；使用 --update-tools 更新并保留备份。')
    if not previous and (project/'.fish-toxicology').exists(): raise ValueError('已有未登记工具目录，请先核对其来源。')
    if update and not previous: raise ValueError('该项目尚未安装，请使用首次安装命令。')
    config=load(project/'.fish-toxicology/workspace.json') if previous else {}
    clients=set(previous.get('clients',[])) if previous else set()
    clients.update(['codex','claude'] if client=='both' else [client])
    changes={project/'.fish-toxicology'/rel:(HOME/rel).read_bytes() for rel in manifest['files']}
    changes[project/'.fish-toxicology/bundle.json']=(HOME/'bundle.json').read_bytes()
    roots={'codex':project/'.agents/skills'/NAME,'claude':project/'.claude/skills'/NAME,'deepseek':project/'.dsh/skills'/NAME,
           'workbuddy':(Path(workbuddy_home).expanduser().resolve() if workbuddy_home else Path.home()/'.workbuddy')/'skills'/NAME}
    discoveries=[]
    for c in sorted(clients):
        if c not in roots: continue
        dest=roots[c].resolve();discoveries.append(str(dest/'SKILL.md'))
        for p in (HOME/'skill').rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                changes[dest/p.relative_to(HOME/'skill')]=discovery_bytes(p,c)
    old=(previous or {}).get('managed_files',{})
    if previous and not old: old={str(project/p):h for p,h in previous.get('files',{}).items()}
    # workspace.json is user configuration; preserve and merge it during tool updates.
    workspace_path=project/'.fish-toxicology/workspace.json'
    modified=[p for p,h in old.items() if Path(p)!=workspace_path and (not Path(p).is_file() or digest(p)!=h)]
    modified += [str(p) for p,b in changes.items() if p.exists() and str(p) not in old and p.read_bytes()!=b and not p.is_relative_to(project/'.fish-toxicology')]
    if modified and not replace_managed:
        raise ValueError('以下组件已有修改；核对后可用 --replace-managed 备份并更新：'+'；'.join(modified))
    data=config.get('database')
    if sum(bool(value) for value in (database, catalog, use_bundled_database)) > 1:
        raise ValueError('--database、--catalog 与 --use-bundled-database 只能选择一个。')
    if catalog:
        data = catalog_binding(catalog, project, data)
    elif database:
        p=Path(database).expanduser().resolve()
        if not p.is_file(): raise ValueError('资料库文件不存在。')
        data={'file':relative(p,project),'version':'external_snapshot','mode':'read_only_snapshot','sha256':digest(p)}
    elif (not previous or use_bundled_database) and (HOME/'workspace.json').exists():
        data=load(HOME/'workspace.json').get('database')
        if data:
            for k in ('file','schema','browser','catalog'):
                if data.get(k):
                    p=(HOME/data[k]).resolve()
                    if not p.is_file(): raise ValueError('完整包缺少资料文件：'+str(p))
                    data[k]=relative(p,project)
            if digest(project/data['file'])!=data['sha256']: raise ValueError('数据库与登记快照不一致。')
    config.update(schema_version='1.2',package_version=manifest['version'],skill_version=manifest['components']['skill'],
        skill='.fish-toxicology/skill/SKILL.md',database=data,analysis_catalog=config.get('analysis_catalog','research/catalog.json'),
        projects_dir=config.get('projects_dir','research'),query_tool='.fish-toxicology/tools/research.py',
        renderer='.fish-toxicology/tools/render_reviewed.py',discovery_skills=discoveries,
        delivery_types=['scientific_figures_with_data','xlsx_00_07','interactive_html'],
        component_requirements=manifest.get('external_components', {}))
    changes[project/'.fish-toxicology/workspace.json']=encoded(config)
    record={'version':manifest['version'],'skill_version':manifest['components']['skill'],'clients':sorted(clients),
        'bundle_sha256':digest(HOME/'bundle.json'),'managed_files':{str(p):hashlib.sha256(b).hexdigest() for p,b in changes.items()}}
    changes[record_path]=encoded(record)
    originals={p:p.read_bytes() if p.exists() else None for p in changes};backup=None
    if any(b is not None for b in originals.values()):
        backup=project/'.fish-toxicology/backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup.mkdir(parents=True)
        index=[]
        for i,(p,b) in enumerate(originals.items()):
            if b is not None:
                target=backup/(str(i)+'.bin');target.write_bytes(b);index.append({'original':str(p),'backup':target.name})
        (backup/'index.json').write_bytes(encoded(index))
    try:
        for p,b in changes.items(): p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        result=inspect(project/'.fish-toxicology')
        if result['errors'] or result['modified_files']: raise ValueError(str(result))
    except BaseException:
        for p,b in originals.items():
            if b is None:
                if p.exists(): p.unlink()
            else: p.write_bytes(b)
        raise
    return {'status':'updated_tools' if previous else 'installed','project':str(project),'backup':str(backup) if backup else None,
            'database_connected':bool(data),**result}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--client',choices=['portable','workbuddy','codex','claude','deepseek','both'],default='portable')
    p.add_argument('--database',type=Path);p.add_argument('--update-tools',action='store_true')
    p.add_argument('--catalog',type=Path,help='独立数据组件的catalog.json；所有资料路径相对该文件解析')
    p.add_argument('--replace-managed',action='store_true',help='备份并替换已有组件；保留研究目录与独立配置')
    p.add_argument('--use-bundled-database',action='store_true',help='更新项目时切换到本包数据库，并备份旧绑定')
    p.add_argument('--workbuddy-home',type=Path,help='WorkBuddy 设置目录，默认 ~/.workbuddy')
    a=p.parse_args()
    try: print(json.dumps(install(a.project,a.client,a.database,a.update_tools,a.replace_managed,a.workbuddy_home,a.use_bundled_database,a.catalog),ensure_ascii=False,indent=2))
    except Exception as e: print(json.dumps({'error':str(e)},ensure_ascii=False),file=sys.stderr);raise SystemExit(1)

if __name__=='__main__': main()

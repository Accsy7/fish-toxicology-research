"""Local database/workflow bridge. Standard library only; never infers science."""
from pathlib import Path
import argparse
import csv
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

RESOURCES = Path(__file__).resolve().parents[1]
ROOT = RESOURCES.parent if RESOURCES.name == '.fish-toxicology' else RESOURCES


def load(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_id(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', value):
        raise ValueError('目录编号仅使用字母、数字、下划线、点或短横线。')
    return value


def config_path(root):
    installed = root / '.fish-toxicology/workspace.json'
    return installed if installed.is_file() else root / 'workspace.json'


def catalog_path(root):
    config = load(config_path(root))
    return root / config.get('analysis_catalog', 'projects/catalog.json')


def skill_home():
    portable = RESOURCES / 'skill'
    return portable if portable.is_dir() else RESOURCES / '.agents/skills/fish-toxicology-research'


def connect(root=ROOT):
    config = load(config_path(root))
    if not config.get('database'):
        raise ValueError('本项目未接入本地数据库，可从公开资料继续研究；需要查库时接入资料快照。')
    path = (root / config['database']['file']).resolve()
    if not path.is_file():
        raise ValueError('找不到已登记的资料库。资料库可能已移动，请按原版本重新绑定路径。')
    c = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA query_only=ON')
    return c, config, path


def rows(c, sql, params=()):
    return [dict(r) for r in c.execute(sql, params)]


def search(c, term):
    return rows(c, '''SELECT c.*,
      (SELECT group_concat(identifier, ' | ') FROM chemical_identifiers i
       WHERE i.chemical_id=c.chemical_id AND i.namespace='CAS') AS cas
      FROM chemicals c WHERE c.chemical_id=?
      OR instr(lower(c.preferred_name),lower(?))>0
      OR instr(lower(coalesce(c.name_zh,'')),lower(?))>0
      OR EXISTS(SELECT 1 FROM chemical_identifiers i WHERE i.chemical_id=c.chemical_id
          AND instr(lower(i.identifier),lower(?))>0)
      ORDER BY c.preferred_name''', (term, term, term, term))


def resolve(c, term):
    hits = search(c, term)
    exact = [r for r in hits if term.casefold() in
             [str(r.get(k) or '').casefold() for k in ('chemical_id', 'preferred_name', 'name_zh')]]
    exact_ids = {r['chemical_id'] for r in rows(c,
        'SELECT DISTINCT chemical_id FROM chemical_identifiers WHERE lower(identifier)=lower(?)', (term,))}
    exact_ids.update(r['chemical_id'] for r in exact)
    if len(exact_ids) == 1:
        return next(iter(exact_ids))
    if not exact_ids and len(hits) == 1:
        return hits[0]['chemical_id']
    raise ValueError(f'{term} 匹配不唯一或未收录，请先search并核对身份；不能自动选首条。匹配数：{len(hits)}')


def by_ids(c, table, key, ids):
    # All identifiers passed here are fixed by this module, never user SQL.
    out = []
    values = sorted(set(x for x in ids if x))
    for i in range(0, len(values), 400):
        group = values[i:i + 400]
        out.extend(rows(c, f'SELECT * FROM {table} WHERE {key} IN ({",".join("?" for _ in group)})', group))
    return out


def evidence(c, cid, include_history=False):
    chemical = rows(c, 'SELECT * FROM chemicals WHERE chemical_id=?', (cid,))[0]
    measurements = rows(c, '''SELECT * FROM v_measurements
      WHERE sample_id IN (SELECT sample_id FROM sample_components WHERE chemical_id=?) ORDER BY measurement_id''', (cid,))
    groups = by_ids(c, 'experimental_groups', 'group_id', [r['group_id'] for r in measurements])
    samples = by_ids(c, 'samples', 'sample_id', [r['sample_id'] for r in groups])
    components = by_ids(c, 'sample_components', 'sample_id', [r['sample_id'] for r in samples])
    notes = rows(c, '''SELECT n.* FROM evidence_notes n JOIN evidence_note_chemicals nc
      USING(note_id) WHERE nc.chemical_id=? ORDER BY n.note_id''', (cid,))
    note_members = by_ids(c, 'evidence_note_chemicals', 'note_id', [r['note_id'] for r in notes])
    activities = rows(c, 'SELECT * FROM bioactivities WHERE chemical_id=? ORDER BY activity_id', (cid,))
    assays = by_ids(c, 'assays', 'assay_id', [r['assay_id'] for r in activities])
    mechanisms = rows(c, 'SELECT * FROM mechanism_evidence WHERE chemical_id=? ORDER BY mechanism_id', (cid,))
    calculations = rows(c, 'SELECT * FROM calculation_results WHERE chemical_id=? ORDER BY result_id', (cid,))
    calc_runs = by_ids(c, 'calculation_runs', 'run_id', [r['run_id'] for r in calculations])
    structures = rows(c, 'SELECT * FROM chemical_structures WHERE chemical_id=? ORDER BY structure_id', (cid,))
    identifiers = rows(c, 'SELECT * FROM chemical_identifiers WHERE chemical_id=? ORDER BY identifier_id', (cid,))
    related = rows(c, 'SELECT * FROM chemical_relationships WHERE chemical_a=? OR chemical_b=?', (cid, cid))
    linked_measurements = {}
    links = []
    mids = {r['measurement_id'] for r in measurements}
    for r in rows(c, 'SELECT * FROM measurement_links'):
        if r['measurement_a'] in mids or r['measurement_b'] in mids:
            links.append(r)
            for mid in (r['measurement_a'], r['measurement_b']):
                if mid not in mids and mid not in linked_measurements:
                    linked_measurements[mid] = rows(c, 'SELECT * FROM v_measurements WHERE measurement_id=?', (mid,))[0]
    # Keep control and linked-result conditions, not just their response values.
    extra_groups = by_ids(c, 'experimental_groups', 'group_id',
                         [r['group_id'] for r in linked_measurements.values()] +
                         [r['control_group_id'] for r in groups])
    groups = list({r['group_id']: r for r in groups + extra_groups}.values())
    samples = by_ids(c, 'samples', 'sample_id', [r['sample_id'] for r in groups])
    components = by_ids(c, 'sample_components', 'sample_id', [r['sample_id'] for r in samples])
    studies = by_ids(c, 'studies', 'study_id', [r['study_id'] for r in groups + notes])
    sources = by_ids(c, 'sources', 'source_id', [r.get('source_id') for r in
        measurements + list(linked_measurements.values()) + notes + assays + mechanisms + studies])
    raw_ids = {r.get('raw_id') for r in measurements + list(linked_measurements.values()) + notes +
               activities + mechanisms + calculations + structures + identifiers + groups + samples + studies}
    materials = by_ids(c, 'biological_materials', 'material_id', [r['material_id'] for r in groups])
    exposures = by_ids(c, 'exposures', 'exposure_id', [r['exposure_id'] for r in measurements + list(linked_measurements.values())])
    taxa = by_ids(c, 'taxa', 'taxon_id', [r['taxon_id'] for r in materials + assays])
    endpoints = by_ids(c, 'endpoints', 'endpoint_id', [r['endpoint_id'] for r in measurements + list(linked_measurements.values())])
    target_proteins = by_ids(c, 'proteins', 'protein_id', [r['target_protein_id'] for r in calculations])
    raw_ids.update(r.get('raw_id') for r in target_proteins)
    raw_ids.update(r.get('raw_id') for r in materials + exposures)
    raw = by_ids(c, 'raw_records', 'raw_id', raw_ids)
    assets = by_ids(c, 'source_assets', 'asset_id', [r['asset_id'] for r in raw] + [r['source_asset_id'] for r in calc_runs])
    packet = {
        'chemical': chemical, 'identifiers': identifiers, 'structures': structures,
        'chemical_relationships': related, 'measurements': measurements,
        'experimental_groups': groups, 'biological_materials': materials, 'exposures': exposures,
        'taxa': taxa, 'endpoints': endpoints, 'target_proteins': target_proteins,
        'samples': samples, 'sample_components': components,
        'linked_results': list(linked_measurements.values()), 'measurement_links': links,
        'evidence_notes': notes, 'evidence_note_members': note_members,
        'bioactivities': activities, 'assays': assays, 'mechanism_evidence': mechanisms,
        'calculation_results': calculations, 'calculation_runs': calc_runs,
        'studies': studies, 'sources': sources, 'raw_records': raw, 'source_assets': assets,
        'evidence_gaps': rows(c, 'SELECT * FROM evidence_gaps WHERE entity_id=?', (cid,)),
        'interpretation': {
            'review_status': '原库状态逐条保留；本次导出没有重新核对原文。',
            'attribution': '样品可能为混合物；叙述可能关联多个物质。分别核对sample_components和evidence_note_members，不把整篇论文结论分配给每个物质。',
            'calculation_use': '计算与其run配置、校准和质量状态共同读取；导出不确认该分支适用于新课题。',
            'source_access': '原始摘录和来源地址已附；source_assets为原库登记，文件路径不代表本包包含论文全文。',
            'missingness': '缺失值保持null，未收录不等于阴性或安全。'
        }
    }
    if include_history:
        packet['historical_predictions_not_current'] = rows(c, '''SELECT p.*,a.version AS analysis_version,
          a.status AS analysis_status,a.scope AS analysis_scope FROM predictions p
          JOIN analyses a USING(analysis_id) WHERE chemical_id=?''', (cid,))
    return packet


def extract(root, terms, output, include_history=False, support='default'):
    config=load(config_path(root))
    if config.get('database',{}).get('catalog'):
        from catalog_access import extract_catalog
        return extract_catalog(root,config,terms,output,include_history,support)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('取证目录已存在，请另存一版。')
    c, config, db = connect(root)
    try:
        ids = list(dict.fromkeys(resolve(c, t) for t in terms))
        packets = {cid: evidence(c, cid, include_history) for cid in ids}
        counts = {cid: {k: len(v) for k, v in p.items() if isinstance(v, list)} for cid, p in packets.items()}
        output.mkdir(parents=True)
        for cid, packet in packets.items():
            write(output / (cid + '.json'), packet)
        manifest = {
            'database_version': config['database']['version'], 'database_sha256': sha(db),
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'query': terms, 'chemical_ids': ids, 'counts': counts,
            'files': {cid + '.json': sha(output / (cid + '.json')) for cid in ids},
            'historical_predictions_included': include_history,
            'new_scientific_review_performed': False
        }
        catalog = load(catalog_path(root)) if catalog_path(root).exists() else {'analyses': []}
        manifest['registered_analysis_versions'] = [
            {k: a[k] for k in ('project_id', 'analysis_version', 'title', 'analysis', 'manifest')}
            for a in catalog['analyses'] if any(x.get('chemical_id') in ids for x in a['database_links'])]
        write(output / 'evidence_manifest.json', manifest)
        return {'output': str(output), 'candidates': len(ids), 'counts': counts,
                'historical_predictions_included': include_history}
    finally:
        c.close()


def init_project(root, name, question):
    config = load(config_path(root))
    target = root / config.get('projects_dir', 'projects') / safe_id(name)
    if target.exists():
        raise ValueError('课题目录已存在，请继续原课题或使用新名称。')
    template = skill_home() / 'assets/new-project.json'
    profile = load(template)
    profile.update({'project_id': name, 'research_question': question,
                    'database_binding': os.path.relpath(config_path(root), target), 'status': 'scope_to_confirm'})
    target.mkdir(parents=True)
    for directory in ('inputs', 'sources', 'analysis', 'review', 'deliverables'):
        (target / directory).mkdir()
    write(target / 'project.json', profile)
    return {'project': str(target), 'profile': str(target / 'project.json'), 'scientific_judgments_created': 0}


def register(root, manifest_path):
    """Bind existing reviewed analysis to artifacts; does not perform content review."""
    manifest_path = Path(manifest_path).resolve()
    m = load(manifest_path)
    pid, version = safe_id(m['project_id']), safe_id(m['analysis_version'])
    analysis_path = (manifest_path.parent / m['analysis']).resolve()
    if sha(analysis_path) != m['analysis_sha256']:
        raise ValueError('正式分析已变化，与复核绑定不一致。')
    analysis = load(analysis_path)
    if analysis.get('project_id')!=pid or analysis.get('analysis_version')!=version:
        raise ValueError('登记的课题或版本与正式分析不一致。')
    from quality_contract import assert_analysis
    from analysis_checks import materialize
    assert_analysis(materialize(analysis),analysis_path.parent)
    completion=m.get('completion',{})
    if not all(completion.get(k) for k in ('path','sha256','project')):
        raise ValueError('新登记必须绑定实际完成检查记录及课题配置；文件存在不等于研究目标完成。')
    completion_path=(manifest_path.parent/completion['path']).resolve()
    if sha(completion_path)!=completion['sha256']:raise ValueError('完成检查记录变化。')
    import importlib.util
    checker_path=skill_home()/'scripts/check_completion.py'
    spec=importlib.util.spec_from_file_location('delivery_completion_check',checker_path)
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    completion_result=checker.check(load(manifest_path.parent/completion['project']),load(completion_path),completion_path.parent)
    if completion_result['errors']:raise ValueError(json.dumps(completion_result,ensure_ascii=False))
    review = m['content_review']
    if review.get('decision') not in ('accepted', 'accepted_with_stated_limits') or not review.get('reviewer'):
        raise ValueError('缺少实际内容复核者或有效复核结果。')
    if review.get('open_blockers') != []:
        raise ValueError('仍有阻断问题或未说明阻断问题状态。')
    if not review.get('records'):
        raise ValueError('缺少实际复核记录。')
    bound_reviews=0
    for record in review['records']:
        if sha(manifest_path.parent / record['path']) != record['sha256']:
            raise ValueError('复核记录变化或不匹配。')
        file=manifest_path.parent / record['path']
        if file.suffix.lower()=='.json' and load(file).get('record_type')=='publication_review':
            from render_reviewed import check_review
            checked=check_review(record,analysis,manifest_path.parent)
            if checked['reviewer']!=review['reviewer'] or checked['decision']!=review['decision']:
                raise ValueError('登记的复核者或决定与实际复核记录不一致。')
            bound_reviews+=1
    if not bound_reviews:
        raise ValueError('需要绑定本次正式分析的 publication_review 内容复核记录。')
    kinds = {r['kind'] for r in m.get('artifacts', [])}
    if not {'xlsx', 'interactive_html'}.issubset(kinds):
        raise ValueError('缺少XLSX或交互网页。')
    for artifact in m['artifacts']:
        artifact_path = manifest_path.parent / artifact['path']
        if sha(artifact_path) != artifact['sha256']:
            raise ValueError('交付文件变化，与复核绑定不一致。')
        if artifact['kind'] == 'interactive_html':
            expected = artifact.get('web_files')
            actual = {p.relative_to(artifact_path.parent).as_posix(): sha(p)
                      for p in artifact_path.parent.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
            if not expected or expected != actual:
                raise ValueError('网页配套数据、脚本或图版变化，与复核绑定不一致。')
    items=analysis.get('chemicals',analysis.get('candidates',[]))
    candidate_ids = {r['id'] for r in items}
    if not candidate_ids or len(candidate_ids)!=len(items):
        raise ValueError('分析物质编号应完整且唯一。')
    if candidate_ids != set(review.get('candidate_ids', [])):
        raise ValueError('内容复核范围未覆盖当前候选集。')
    c = connect(root)[0] if load(config_path(root)).get('database') else None
    try:
        mapping = m.get('database_links', [])
        if len(mapping) != len(candidate_ids) or {r['candidate_id'] for r in mapping} != candidate_ids:
            raise ValueError('每个候选必须登记数据库对应或明确说明未匹配。')
        for link in mapping:
            if link.get('chemical_id'):
                if c is None:
                    raise ValueError('尚未接入资料库，不能登记未经核对的数据库物质编号。')
                if not c.execute('SELECT 1 FROM chemicals WHERE chemical_id=?', (link['chemical_id'],)).fetchone():
                    raise ValueError('不存在的数据库物质编号。')
                if not link.get('basis'):
                    raise ValueError('数据库身份对应缺少依据。')
            elif not link.get('unmatched_reason'):
                raise ValueError('未匹配候选须说明原因。')
    finally:
        if c is not None:
            c.close()
    catalog_file = catalog_path(root)
    catalog = load(catalog_file) if catalog_file.exists() else {'schema_version': '1.0', 'analyses': []}
    if any(x['project_id'] == pid and x['analysis_version'] == version for x in catalog['analyses']):
        raise ValueError('此分析版本已登记，请保留旧版并使用新版本号。')
    # All catalog paths remain portable with the workspace. No outside file dependency.
    def relative(path):
        try:
            return Path(path).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            raise ValueError('分析、交付和复核记录须保存在当前课题项目内，再登记。')
    entry = {'project_id': pid, 'analysis_version': version, 'title': m['title'],
             'analysis': relative(analysis_path), 'analysis_sha256': m['analysis_sha256'],
             'manifest': relative(manifest_path), 'database_links': mapping,
             'artifacts': [{'kind': a['kind'], 'path': relative(manifest_path.parent / a['path'])} for a in m['artifacts']],
             'reviewer': review['reviewer'], 'review_decision': review['decision'],
             'candidate_count': len(candidate_ids), 'registration_is_new_scientific_review': False}
    entry['research_objective_status']=completion_result['objective_status']
    entry['completion']=relative(completion_path)
    for record in review['records']:
        relative(manifest_path.parent / record['path'])
    catalog['analyses'].append(entry)
    write(catalog_file, catalog)
    catalog_html(root, catalog)
    return {'registered': pid, 'version': version, 'candidates': len(candidate_ids), 'new_scientific_review': False}


def catalog_html(root, catalog):
    e = html.escape
    body = '<h1>已复核的研究结果</h1><p>每项结果保留课题、版本与适用条件。数据库中的历史预测仍单独保存。</p>'
    for item in catalog['analyses']:
        body += '<section><h2>' + e(item['title']) + '</h2><p>' + e(item['analysis_version']) + ' · ' + str(item['candidate_count']) + '种候选</p><p>'
        labels = {'xlsx': '分析工作簿', 'interactive_html': '交互报告', 'scientific_figures': '科研图版'}
        for art in item['artifacts']:
            label = labels.get(art['kind'], art['kind'])
            if art['kind'] == 'scientific_figures':
                label = Path(art['path']).stem
            relative = os.path.relpath(root / art['path'], catalog_path(root).parent).replace('\\', '/')
            body += '<a href="' + e(relative, quote=True) + '">' + e(label) + '</a>　'
        body += '</p></section>'
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>研究结果</title><style>body{font:16px/1.8 system-ui,"Microsoft YaHei";max-width:960px;margin:40px auto;padding:0 24px;color:#233746}section{border-top:1px solid #d8e0e6;padding:20px 0}a{color:#276982}</style><main>' + body + '</main></html>'
    target = catalog_path(root).with_name('index.html')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, 'utf-8')


def doctor(root, deep=False):
    config = load(config_path(root))
    from bundle_runtime import inspect
    runtime = inspect(root / '.fish-toxicology' if (root / '.fish-toxicology').exists() else root)
    if not config.get('database'):
        errors=runtime['errors'] + (['组件与包清单不同：'+'；'.join(runtime['modified_files'])] if runtime['modified_files'] else [])
        return {'ready_for_local_queries': False, 'errors': errors, 'runtime':runtime,
                'warnings': ['未绑定独立数据组件；用安装器 --catalog 指定已解压的catalog.json。'],
                'ready_for_public_source_research': not errors,
                'database_status': 'not_connected',
                'scientific_analysis_or_review_performed': False}
    c, config, db = connect(root)
    try:
        errors = list(runtime['errors'])
        warnings = []
        if runtime['modified_files']:
            errors.append('组件与包清单不同：'+'；'.join(runtime['modified_files']))
        checks={'mode':'connection_and_version','full_hash_checked':False,'integrity_checked':False}
        meta=c.execute("SELECT value FROM metadata WHERE key='database_version'").fetchone()
        if meta and config['database'].get('version') not in ('external_snapshot',meta[0]):
            errors.append('数据库内容版本与绑定版本不一致。')
        if deep:
            integrity=c.execute('PRAGMA quick_check').fetchone()[0]
            foreign=list(c.execute('PRAGMA foreign_key_check'))
            actual_hash=sha(db)
            checks.update(full_hash_checked=True,integrity_checked=True,quick_check=integrity,foreign_key_errors=len(foreign),actual_sha256=actual_hash)
            if integrity!='ok' or foreign:errors.append('数据库完整性或关联检查失败。')
            if config['database'].get('sha256') and actual_hash!=config['database']['sha256']:
                errors.append('数据库文件与工作包登记版本不一致。')
            if not config['database'].get('sha256'):
                warnings.append('此外置资料绑定未登记fish SQLite哈希；已计算哈希，仍须和数据组件回执核对。')
        required = [config['skill'], config.get('query_tool', 'tools/research.py')]
        required += [config['database'][k] for k in ('browser', 'schema') if config['database'].get(k)]
        for path in required:
            if not (root / path).is_file():
                errors.append('缺少文件：' + path)
        catalog_checks=None
        if config['database'].get('catalog'):
            try:
                from catalog_access import open_catalog
                with open_catalog(root,config) as catalog:
                    catalog_checks={'version':catalog.config['version'],'policy_version':catalog.policy.get('version'),
                        'files':{k:str(v) for k,v in catalog.paths.items()},'read_only':True,
                        'identity_runtime_available':catalog.d is not None}
                    for key in ('observations','molecular_support','identities','policy'):
                        if not catalog.paths[key].exists():errors.append('缺少分类目录文件：'+key)
                    if catalog.d is None:warnings.append('缺少可选duckdb；SQLite查询可用，Parquet化合物目录查询不可用。')
                    if catalog.config['version']!=config['database'].get('catalog_version'):
                        errors.append('分类目录版本与绑定版本不一致。')
            except Exception as exc:errors.append('分类目录连接失败：'+str(exc))
        expected = config.get('component_requirements',{}).get('data',{}).get('required_for_complete_repair','0.4.2-local.1')
        repair_data_ready = bool(catalog_checks and catalog_checks['version']==expected)
        if not repair_data_ready:
            warnings.append('当前未绑定'+expected+'修订目录；软件更新不会补回旧数据组件遗漏的条件和标识关联。')
        return {'ready_for_local_queries': not errors, 'errors': errors, 'warnings':warnings,
                'complete_repair_data_bound': repair_data_ready,
                'ready_for_parquet_catalog_queries':bool(catalog_checks and catalog_checks['identity_runtime_available'] and not errors),
                'runtime': runtime,
                'catalog_checks':catalog_checks,
                'counts_scope':'preserved fish source snapshot; chemical expansion counts are returned by coverage',
                'database_version': config['database']['version'],'database_checks':checks,
                'counts': {t: c.execute('SELECT count(*) FROM ' + t).fetchone()[0] for t in
                           ('chemicals', 'measurements', 'sources', 'genes', 'proteins')},
                'database_analyses': rows(c, 'SELECT analysis_id,version,status,scope FROM analyses'),
                'scientific_analysis_or_review_performed': False}
    finally:
        c.close()


def main():
    p = argparse.ArgumentParser(description='鱼类毒性研究：查库、取证、建立空白课题、登记已审成果。')
    p.add_argument('--root', type=Path, default=ROOT)
    sub = p.add_subparsers(dest='command', required=True)
    a=sub.add_parser('doctor');a.add_argument('--deep',action='store_true',help='完整检查大文件哈希、数据库和关联')
    a = sub.add_parser('taxonomy'); a.add_argument('name'); a.add_argument('--taxid',type=int)
    for command in ('genes','proteins','pathways','toxicity','chemicals','properties','environment','bioactivity','mechanisms','compound-relations','entity-pathways','structure'):
        a=sub.add_parser(command);a.add_argument('--species',default='');a.add_argument('--term',default='');a.add_argument('--limit',type=int,default=100);a.add_argument('--offset',type=int,default=0)
        a.add_argument('--support',default='default');a.add_argument('--assertion',default='any',choices=['any','function','existence'])
        a.add_argument('--source',default='',help='Exact source DOI or stored reference; bypasses chemical identity filters when --term is omitted')
        a.add_argument('--endpoint',default='',help='Literal endpoint text within the selected observation scope')
    a=sub.add_parser('pathway-members');a.add_argument('pathway');a.add_argument('--support',default='default');a.add_argument('--limit',type=int,default=100);a.add_argument('--offset',type=int,default=0)
    a=sub.add_parser('sequence');a.add_argument('accession')
    a=sub.add_parser('source-record');a.add_argument('identifier');a.add_argument('--kind',choices=['gene','protein','observation'],default='protein')
    sub.add_parser('coverage')
    a = sub.add_parser('search'); a.add_argument('term')
    a = sub.add_parser('extract'); a.add_argument('--chemical', action='append', required=True); a.add_argument('--output', type=Path, required=True); a.add_argument('--history', action='store_true')
    a.add_argument('--support',default='default')
    a = sub.add_parser('new'); a.add_argument('name'); a.add_argument('--question', required=True)
    a = sub.add_parser('register'); a.add_argument('manifest', type=Path)
    a = sub.add_parser('analyses'); a.add_argument('--chemical')
    args = p.parse_args(); root = args.root.resolve()
    if args.command == 'doctor':
        result = doctor(root,args.deep)
    elif args.command in ('coverage','genes','proteins','pathways','pathway-members','toxicity','sequence','source-record','chemicals','properties','environment','bioactivity','mechanisms','compound-relations','entity-pathways','search','structure'):
        from database_queries import query
        config=load(config_path(root))
        kind={'pathway-members':'members','source-record':getattr(args,'kind','protein')+'-record','search':'chemicals'}.get(args.command,args.command)
        if kind=='observation-record':kind='observation'
        term=getattr(args,'pathway',getattr(args,'accession',getattr(args,'identifier',getattr(args,'term',''))))
        if (config.get('database') or {}).get('catalog'):
            from catalog_access import open_catalog
            with open_catalog(root,config) as c:result=c.query(kind,term,getattr(args,'species',''),getattr(args,'support','default'),getattr(args,'limit',100),getattr(args,'offset',0),getattr(args,'assertion','any'),source=getattr(args,'source',''),endpoint=getattr(args,'endpoint',''))
        else:
            c,_,_=connect(root)
            try:result={'matches':search(c,term)} if args.command=='search' else query(c,kind,term,getattr(args,'species',''),getattr(args,'limit',100),getattr(args,'offset',0))
            finally:c.close()
    elif args.command == 'taxonomy':
        c,_,_=connect(root)
        try:
            name=args.name if args.command=='taxonomy' else args.species
            taxa=rows(c,'SELECT * FROM taxa WHERE lower(scientific_name)=lower(?) OR common_name=?',(name,name))
            if args.command=='taxonomy':
                result={'query':name,'matches':taxa,'status':'matched' if taxa else 'no_local_match'}
                if args.taxid is not None and taxa and not any(t['ncbi_taxid']==args.taxid for t in taxa):
                    raise ValueError('物种名称与指定 taxid 不符；数据库对应：'+str(taxa))
            else:
                found=[]
                for t in taxa:
                    found.extend(rows(c,"SELECT p.*,t.scientific_name,t.ncbi_taxid FROM proteins p JOIN taxa t USING(taxon_id) WHERE p.taxon_id=? AND (instr(lower(coalesce(p.gene_label,'')),lower(?))>0 OR instr(lower(coalesce(p.name,'')),lower(?))>0 OR instr(lower(p.protein_id),lower(?))>0)",(t['taxon_id'],args.term,args.term,args.term)))
                result={'species':name,'term':args.term,'matches':found,'count':len(found),'status':'matched' if found else 'no_local_match'}
        finally: c.close()
    elif args.command == 'new':
        result = init_project(root, args.name, args.question)
    elif args.command == 'extract':
        result = extract(root, args.chemical, args.output, args.history,args.support)
    elif args.command == 'register':
        result = register(root, args.manifest)
    elif args.command == 'analyses':
        catalog = load(catalog_path(root)) if catalog_path(root).exists() else {'analyses': []}
        cid = None
        if args.chemical:
            c, _, _ = connect(root)
            try:
                cid = resolve(c, args.chemical)
            finally:
                c.close()
        entries = [r for r in catalog['analyses'] if cid is None or any(x.get('chemical_id') == cid for x in r['database_links'])]
        result = {'chemical_id': cid, 'analyses': [
            {**{k:r[k] for k in ('project_id','analysis_version','title','analysis','manifest','candidate_count','artifacts')},
             'matched_candidates':[x['candidate_id'] for x in r['database_links'] if x.get('chemical_id') == cid] if cid else []}
            for r in entries]}
    else:
        c, _, _ = connect(root)
        try:
            result = {'matches': search(c, args.term)}
        finally:
            c.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == 'doctor' and result['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        main()
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)

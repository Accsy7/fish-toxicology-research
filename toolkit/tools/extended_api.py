"""Presentation adapters. Original records remain read-only and independently identified."""
from pathlib import Path
from functools import lru_cache
import gzip, json, hashlib, threading, time
from workspace_api import WorkspaceAPI as BaseAPI, NUMERIC
from catalog_queries import Catalog, rows, normalize_query, filter_values

ROOT = Path(__file__).resolve().parent
DOMAINS = (*NUMERIC, 'chemicals', 'species', 'sources', 'endpoints', 'pathways', 'genes', 'proteins', 'members', 'mechanisms')

def choices(value):
    return filter_values(value)

class WorkspaceAPI(BaseAPI):
    _manifest_lock = threading.Lock()
    @lru_cache(maxsize=1)
    def legacy(self):
        with gzip.open(ROOT/'approved-records.json.gz', 'rt', encoding='utf-8') as f:
            return json.load(f)

    def meta(self):
        result = dict(super().meta())
        result['ui_version'] = '1.9.0-local.6'
        result['legacy_version'] = '0.2.0'
        return result

    def search(self, a):
        a = normalize_query(a)
        original = dict(a)
        kind = a.get('kind', 'chemicals')
        if kind not in DOMAINS:
            raise ValueError('Unknown collection')
        if a.get('_empty_filters'):
            return super().search(a)
        # Applicable filters remain stored by the caller. Unrelated dimensions
        # are not applied to a different kind, and are not erased on tab changes.
        if kind not in NUMERIC and kind != 'chemicals':
            for key in ('family', 'endpoint', 'stage'):
                a.pop(key, None)
        if kind == 'bioactivity':
            # The full source has no comparable stage/family fields.
            for key in ('family', 'endpoint', 'stage'):
                a.pop(key, None)
        if kind == 'chemicals':
            # Identity assertions have their own support classification. This
            # selector must not silently classify toxicity results instead.
            with Catalog(self.path) as catalog:
                allowed = catalog.types(kind, a.get('support', 'default'))
            if 'pending_verification' not in allowed:
                return {'matches': [], 'returned': 0, 'total': 0,
                        'offset': int(a.get('offset', 0)), 'has_more': False,
                        'query': a, 'applied_support_filter': allowed,
                        'unapplied_filters': [], 'stored_filters': original,
                        'scope_note': '身份条目的来源分类；测量资料可在实验与性质目录查询。'}
        if kind == 'chemicals' and not a.get('sort_field') and not any(str(a.get(k, '')).strip() for k in ('term', 'family', 'species')):
            result = self.all_identities(a)
        else:
            result = super().search(a)
        if not result.get('has_more') and (result.get('returned') or not int(a.get('offset', 0))):
            result.setdefault('total', int(a.get('offset', 0)) + result.get('returned', 0))
        inactive = [key for key in original if key not in a and original[key]]
        for r in result.get('matches', []):
            r['_collection'] = kind
            if inactive:r['_unapplied_filters'] = inactive
        result['unapplied_filters'] = inactive
        result['stored_filters'] = original
        return result

    def all_identities(self, a):
        """Page source identities across every identity store, without dedup claims."""
        limit, offset = int(a.get('limit', 50)), int(a.get('offset', 0))
        if not 1 <= limit <= 500 or offset < 0: raise ValueError('Invalid page')
        with Catalog(self.path) as c:
            metas = sorted((json.loads(p.read_text('utf-8')) for p in c.paths['sdf'].glob('*.json')), key=lambda x:x['min_cid'])
            pubchem = sum(m['records'] for m in metas)
            ds = c.pq('DSSToxCCDdump.parquet')
            ds_count = c.d.execute('SELECT count(*) FROM read_parquet(?)', [str(ds)]).fetchone()[0] if ds.exists() else 0
            fish_count = c.fish.execute('SELECT count(*) FROM chemicals').fetchone()[0]
            total = pubchem + ds_count + fish_count
            remaining, result = offset, []
            for m in metas:
                if remaining >= m['records']:
                    remaining -= m['records']; continue
                records = c.parquet(c.paths['sdf']/m['parquet'], ' ORDER BY cid OFFSET ?', [remaining], limit-len(result))
                remaining = 0
                for r in records:r.update(source_id='PubChemCID:'+str(r['cid']),name=r.get('name') or r.get('iupac_name'),provider='PubChem',support_type='pending_verification',structure_2d_available=True)
                result.extend(records)
                if len(result) >= limit:break
            if len(result) < limit and remaining < ds_count:
                cur = c.d.execute('SELECT DTXSID AS source_id,PREFERRED_NAME AS name,CASRN AS cas,SMILES AS smiles,INCHIKEY AS inchikey,MOLECULAR_FORMULA AS formula,AVERAGE_MASS AS molecular_weight,IDENTIFIER AS aliases FROM read_parquet(?) ORDER BY DTXSID LIMIT ? OFFSET ?', [str(ds),limit-len(result),remaining])
                names = [x[0] for x in cur.description]
                result.extend({**dict(zip(names,r)),'provider':'DSSTox','support_type':'pending_verification'} for r in cur.fetchall())
                remaining = 0
            elif len(result) < limit:remaining -= ds_count
            if len(result) < limit:
                result.extend(self.scoped_chemicals(c, {}, limit-len(result), remaining)['matches'])
            for r in result:r['support_label']='尚待核对'
            result = c.resolve_paths(result)
            return {'matches':result,'returned':len(result),'offset':offset,'total':total,
                    'has_more':offset+len(result)<total,'query':{**a,'limit':limit,'offset':offset},
                    'source_counts':{'PubChem':pubchem,'DSSTox':ds_count,'FishCatalog':fish_count},
                    'count_unit':'source_identity_record','applied_support_filter':c.types('chemicals',a.get('support','default'))}

    def iter_batches(self, a, network=False):
        """One user operation; transport batches do not cap the result scope."""
        if network:
            from network_stream import iter_network
            yield from iter_network(self,a)
            return
        a = normalize_query(a)
        kinds = choices(a.pop('kinds', a.get('kind', 'chemicals')))
        if not kinds or any(k not in DOMAINS for k in kinds):
            raise ValueError('Select at least one collection')
        cap = a.pop('take', 'all')
        cap = None if cap in ('all', 'unlimited', '0', '') else int(cap)
        if cap is not None and cap < 1:
            raise ValueError('Record count must be positive, or all')
        total = 0
        for kind in kinds:
            offset = 0
            while True:
                limit = min(500, cap-offset) if cap is not None else 500
                if limit <= 0:
                    break
                q = {**a, 'kind':kind, 'limit':limit, 'offset':offset}
                batch = self.network(q) if network else self.search(q)
                count = batch.get('returned', 0)
                total += count
                offset += count
                yield {'kind':kind, 'batch':batch, 'loaded':total, 'kind_loaded':offset,
                       'kind_complete':not batch.get('has_more', False),
                       'limited':bool(batch.get('has_more') and cap is not None and offset>=cap)}
                if not count or not batch.get('has_more') or cap is not None and offset >= cap:
                    break

    def network(self, a):
        return super().network(a)

    def legacy_context(self, a):
        key = a.get('id','')
        data = self.detail({'kind':'chemicals','id':key,'support':a.get('support','default')})
        ids = {x['identifier'] for x in data['identifiers'] if x['namespace']=='CAS'}
        old = self.legacy()
        matches = [r for r in old['chemicals'] if r.get('cas') in ids or r['chemical_id']==key]
        chemical_ids = {r['chemical_id'] for r in matches}
        result = {}
        for table in ('structures','notes','bioactivity','predictions','docking','category_memberships'):
            result[table] = [r for r in old[table] if r.get('chemical_id') in chemical_ids or chemical_ids.intersection(str(r.get('chemical_ids','')).split('|'))]
        # Older activity rows did not record an item-level support classification.
        # Retain them, but apply the same default as the current numerical catalog.
        with Catalog(self.path) as catalog:
            permitted = catalog.types('bioactivity', a.get('support','default'))
        result['bioactivity'] = [{**r,'support_type':r.get('support_type') or 'pending_verification',
                                 'support_label':r.get('support_label') or '尚待核对'}
                                for r in result['bioactivity']
                                if (r.get('support_type') or 'pending_verification') in permitted]
        source_ids = {r['source_id'] for r in result['notes'] if r.get('source_id')}
        result['sources'] = [r for r in old['sources'] if r['source_id'] in source_ids]
        result['categories'] = old['categories']
        result['chemical'] = {**(matches[0] if len(matches)==1 else {}), **{k:v for k,v in data['record'].items() if v is not None}}
        result['chemical']['chemical_id'] = key
        result['chemical']['preferred_name'] = result['chemical'].get('preferred_name') or result['chemical'].get('name') or key
        # Adapt display identity only; retain original IDs next to the mapped ID.
        for table in ('structures','notes','bioactivity','predictions','docking','category_memberships'):
            result[table] = [{**r,'legacy_chemical_id':r.get('chemical_id'),'legacy_chemical_ids':r.get('chemical_ids'),'chemical_id':key,'chemical_ids':key} for r in result[table]]
        result['linked_identities'] = data['linked_identities']
        result['identifiers'] = data['identifiers']
        result['counts'] = data['counts']
        result['families'] = data['families']
        return result

    def reader(self, a):
        data = self.detail(a)
        row = data['record']
        # Prefer the original condition-rich presentation row where the record ID
        # maps exactly; no join on compound alone or a shared publication.
        mid = row.get('record_id','')
        old = self.legacy().get('measurements', [])
        original = next((r for r in old if mid in (r['measurement_id'], 'FishCatalog:'+r['measurement_id'], 'FishSnapshot0.3:'+r['measurement_id'], 'legacy:'+r['measurement_id'])), None)
        if original is None and row.get('original_record',{}).get('measurement_id'):
            original = row['original_record']
        if original:
            data['reader_record'] = {**original, 'support_type':row.get('support_type'), 'support_label':row.get('support_label'),'source_enrichment':row.get('source_enrichment'),'original_source_record':row.get('original_source_record') or row.get('original_record')}
        return data

    def files(self):
        # A short-lived manifest keeps repeated downloads from re-enumerating
        # all source shards, while subsequent refreshes use actual file sizes.
        with self._manifest_lock:
            cached=getattr(self,'_files_cache',None)
            if cached and time.monotonic()-cached[0]<30:return cached[1]
            with Catalog(self.path) as c:
                result=[];stats=[];seen=set();unreadable=[];lookup={}
                categories=('fish_database','observations','molecular_support','molecular_lookup','identities','sdf','bioactivity','source_reconciliation','policy','coverage','raw')
                for category in categories:
                    path=c.paths.get(category)
                    if not path or not path.exists():continue
                    path=path.resolve();single=path.is_file();files=[path] if single else sorted(p for p in path.rglob('*') if p.is_file())
                    if category=='source_reconciliation':
                        files=[p for p in files if p.suffix in ('.sqlite3','.json','.csv','.md','.txt') and not any(part in ('integrated_v1','__pycache__','vendor','audit') for part in p.relative_to(path).parts)]
                    stat={'category':category,'files':0,'bytes':0}
                    for p in files:
                        resolved=p.resolve()
                        if not single and not resolved.is_relative_to(path):
                            unreadable.append({'category':category,'path':str(p),'reason':'link outside catalog directory'});continue
                        key=str(resolved).casefold()
                        if key in seen:continue
                        try:size=p.stat().st_size
                        except OSError as error:
                            unreadable.append({'category':category,'path':str(p),'reason':str(error)});continue
                        seen.add(key);rel='' if single else p.relative_to(path).as_posix();file_id=category+':'+rel
                        result.append({'category':category,'name':p.name,'relative_path':rel,'bytes':size,'file_id':file_id})
                        lookup[file_id]=resolved;stat['files']+=1;stat['bytes']+=size
                    stats.append(stat)
                organized=sum(s['bytes'] for s in stats if s['category']!='raw');raw=sum(s['bytes'] for s in stats if s['category']=='raw')
                data={'catalog_version':c.config['version'],'files':result,'raw_sources':str(c.paths['raw']),
                      'storage':{'categories':stats,'organized_bytes':organized,'raw_bytes':raw,
                                 'total_bytes':organized+raw,'unique_files':len(result),
                                 'measured_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                                 'unreadable':unreadable}}
                self._files_lookup=lookup;self._files_cache=(time.monotonic(),data)
                return data

    def file_path(self, file_id):
        self.files()
        path=self._files_lookup.get(file_id)
        if path is None or not path.is_file():raise ValueError('Unknown catalog file')
        return path

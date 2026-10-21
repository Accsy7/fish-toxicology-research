"""Shared read-only classification and filters for CLI, browser and CSV exports."""
from pathlib import Path
from query_runtime import current_runtime
from functools import lru_cache
from global_sort import validate_sort, text as sort_text, order_by, molecular_order, cached_prefix, cache_key, slice_prefix, response_sort, sorted_identities, prepare_sqlite, page_start
import importlib.util
from catalog_quality import local_identifiers, attach_context, diagnostics
import argparse,json,sqlite3,sys,re,zlib,hashlib,math,shutil,time,unicodedata
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime'))
try:import duckdb
except ImportError:duckdb=None

def rows(c,sql,params=()):return [dict(r) for r in c.execute(sql,params)]
def ro(p):
 c=sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');return c
def page(c,sql,args,limit,offset):
 r=rows(c,sql+' LIMIT ? OFFSET ?',(*args,limit+1,offset));return {'matches':r[:limit],'returned':min(len(r),limit),'offset':offset,'has_more':len(r)>limit}

def filter_values(value,separator=','):
 if value is None:return []
 values=value if isinstance(value,(list,tuple)) else str(value).split(separator)
 return list(dict.fromkeys(str(x).strip() for x in values if x is not None and str(x).strip()))

def normalize_query(arguments):
 """An omitted/null filter means all; an explicit empty array means none."""
 out=dict(arguments);empty=list(out.get('_empty_filters',[]))
 for key in ('family','species','support','endpoint'):
  value=out.get(key)
  if value is None:out.pop(key,None)
  elif isinstance(value,(list,tuple)):
   values=filter_values(value)
   if not values:empty.append(key)
   out[key]=('||' if key=='endpoint' else ',').join(values)
 if empty:out['_empty_filters']=list(dict.fromkeys(empty))
 return out

@lru_cache(maxsize=4)
def reconciliation_reader(root):
 path=Path(root)/'reconciliation_queries.py'
 spec=importlib.util.spec_from_file_location('catalog_source_reconciliation',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module

class Catalog:
 def __init__(self,path=None):
  self.manifest=Path(path or ROOT/'catalog.json').resolve();self.config=json.loads(self.manifest.read_text('utf-8'));base=self.manifest.parent
  self.paths={k:(base/v).resolve() for k,v in self.config['paths'].items()}
  self.policy=json.loads(self.paths['policy'].read_text('utf-8'))
  self.identifier_cache={}
  self.fish=ro(self.paths['fish_database']);self.observations=ro(self.paths['observations'])
  prepare_sqlite(self.fish);prepare_sqlite(self.observations)
  self.fish.execute('ATTACH DATABASE ? AS support',(self.paths['molecular_support'].as_uri()+'?mode=ro',))
  self.go=ro(self.paths['molecular_support'])
  self.has_existence=bool(self.go.execute("SELECT 1 FROM sqlite_master WHERE name='existence'").fetchone())
  self.has_lookup=bool(self.paths.get('molecular_lookup') and self.paths['molecular_lookup'].with_suffix('.json').exists())
  if self.has_lookup:self.fish.execute('ATTACH DATABASE ? AS lookup',(self.paths['molecular_lookup'].as_uri()+'?mode=ro&immutable=1',))
  self.d=duckdb.connect() if duckdb else None
  if self.d:self.d.execute("SET memory_limit='1GB'");self.d.execute('SET threads=2')
  self.query_runtime=current_runtime()
  if self.query_runtime:
   for connection in (self.fish,self.go,self.observations,self.d):self.query_runtime.register(connection)
 def __enter__(self):return self
 def __exit__(self,*args):
  if self.query_runtime:
   for connection in (self.fish,self.go,self.observations,self.d):self.query_runtime.unregister(connection)
  self.fish.close();self.go.close();self.observations.close()
  if self.d:self.d.close()
 def enrich_records(self,records):
  root=self.paths.get('source_reconciliation')
  if not root:return records
  ids=[r['record_id'] for r in records if r.get('record_id')]
  if not ids:return records
  additions=reconciliation_reader(str(root)).get_enrichments(ids,root)
  raw_records={r['record_id']:r.get('original_record') for r in records if r.get('original_record')}
  missing=[rid for rid in ids if rid not in raw_records]
  if missing:
   for source in rows(self.observations,'SELECT record_id,raw_zlib FROM observations WHERE record_id IN (SELECT value FROM json_each(?))',[json.dumps(missing)]):
    raw_records[source['record_id']]=json.loads(zlib.decompress(source['raw_zlib']))
  need_identifiers=[r['record_id'] for r in records if r.get('record_id') and not r.get('identifiers')]
  by_id={rid:[] for rid in need_identifiers}
  if need_identifiers:
   for item in rows(self.observations,'SELECT record_id,namespace,identifier FROM identifiers WHERE record_id IN (SELECT value FROM json_each(?)) ORDER BY namespace,identifier',[json.dumps(need_identifiers)]):
    by_id[item.pop('record_id')].append(item)
  for record in records:
   extra=additions.get(record.get('record_id'))
   if extra and any(extra.get(k) for k in ('context','references','proposed_corrections','related_source_material','source_annotations')):
    record['source_enrichment']=extra
   if record.get('record_id') in by_id:record['identifiers']=by_id[record['record_id']]
   source=raw_records.get(record.get('record_id'),{})
   context=(extra or {}).get('context',{})
   chemical=context.get('toxref_chemical',{})
   name=source.get('chemical_name') or source.get('chemical_names') or context.get('chemical_name') or chemical.get('chemical_name') or chemical.get('name')
   if name:
    record['chemical_name']=name
    record['chemical_name_source']='original observation source'
   elif record.get('identifiers'):
    cas=[i['identifier'] for i in record['identifiers'] if i['namespace']=='CAS']
    record['chemical_name']=', '.join(cas) or record['record_id']
    record['chemical_name_source']='source identifier; name not supplied in this observation'
  return records
 def source_material(self,namespace,identifier,offset=0,limit=50,source_set='primary'):
  root=self.paths.get('source_reconciliation')
  if not root:return {'total':0,'rows':[],'offset':offset,'limit':limit}
  reader=reconciliation_reader(str(root))
  if source_set=='secondary':return reader.search_secondary_material(namespace,identifier,root,offset=offset,limit=limit)
  if source_set=='echa':return reader.get_echa_endpoints(identifier,root,offset=offset,limit=limit)
  return reader.search_source_material(namespace,identifier,root,offset=offset,limit=limit)
 def types(self,kind,support):
  if support in (None,'','default'):return self.policy['default_support'].get(kind,['experimental','inferred_annotation','pending_verification'])
  if support=='all':return ['experimental','inferred_annotation','pending_verification']
  out=support.split(',')
  if any(s not in self.policy['labels'] for s in out):raise ValueError('Unknown support type')
  return out
 def resolve_paths(self,value):
  """Resolve relocated files without rewriting archived SQLite source records."""
  if isinstance(value,list):return [self.resolve_paths(v) for v in value]
  if not isinstance(value,dict):return value
  out={}
  for key,v in value.items():
   if key in ('original_record','original_source_record'):out[key]=v;continue
   if key in ('source_file','asset_path','raw_path','source_path') and isinstance(v,str):
    normalized=v.replace('\\','/')
    for move in self.config.get('path_relocations',[]):
     old=move['from'].replace('\\','/').rstrip('/')
     if normalized.casefold().startswith(old.casefold()+'/'):
      out[key+'_at_import']=v;v=str(Path(move['to'])/normalized[len(old)+1:]);break
   out[key]=self.resolve_paths(v)
  return out
 def coverage(self):
  if not self.paths['coverage'].exists():return {'status':'building','policy':self.policy}
  result=json.loads(self.paths['coverage'].read_text('utf-8'))
  base=self.paths['coverage'].parent;plan=base/'combined-download-plan.json';controller=base/'batch-controller.json'
  if not plan.exists():return result
  items=json.loads(plan.read_text('utf-8'))['files'];finished=[];partial=0
  for item in items:
   raw=self.paths['raw']/item['name'];receipt=base/'receipts'/(item['name']+'.json')
   if raw.exists() and receipt.exists():finished.append(item)
   else:
    marker=raw.with_suffix(raw.suffix+'.ranged.part.json')
    if marker.exists():
     state=json.loads(marker.read_text('utf-8'));partial+=sum(min(state['chunk'],state['bytes']-n*state['chunk']) for n in state['done'])
  imported=[json.loads(p.read_text('utf-8')) for p in self.paths['sdf'].glob('*.json')]
  progress=result['download_progress'];progress.update(complete_files=len(finished),complete_compressed_bytes=sum(i['bytes'] for i in finished),verified_partial_bytes=partial,sdf_downloaded_shards=sum(i['name'].startswith('sdf-probe/') for i in finished),sdf_imported_shards=len(imported))
  result['counts']['pubchem_sdf_compounds']=sum(i['records'] for i in imported)
  planned=progress['sdf_planned_shards'];remaining=planned-len(imported)
  for source in result['source_summary']:
   if source['source']=='PubChem SDF':source.update(records=result['counts']['pubchem_sdf_compounds'],coverage=f'{len(imported)} / {planned} 个结构分包完成入库')
  if controller.exists():result['batch_controller']=json.loads(controller.read_text('utf-8'))
  result['progress_updated_at_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
  result['disk']['D_free_bytes']=shutil.disk_usage(self.paths['raw']).free
  result['status_text']=f'结构分包：下载 {progress["sdf_downloaded_shards"]} / {planned}，入库 {len(imported)} / {planned}。磁盘当前可用 {result["disk"]["D_free_bytes"]/10**9:.2f} GB。'
  if remaining:
   result['batch_complete']=False
   result['gaps'][0]=f'PubChem 全量结构：已索引 {len(imported)} / {planned} 包，剩余 {remaining} 包继续下载、校验和索引。'
  elif result.get('gaps') and result['gaps'][0].startswith('PubChem 全量结构：'):
   result['gaps'][0]=f'PubChem 本批 {planned} 个结构分包已索引。'
  result['disk_text']=f'文件分类占用见统计快照（{result["updated_at_utc"]}）；D 盘当前可用 {result["disk"]["D_free_bytes"]/10**9:.2f} GB。'
  return result
 def species_records(self,term):
  # Resolve the small taxon directory once. One SELECT per selected taxon made
  # a 12k selection perform 12k full directory scans.
  if not hasattr(self,'_species_index'):
   self._species_index={}
   for row in rows(self.fish,'SELECT taxon_id,ncbi_taxid,scientific_name,common_name FROM taxa'):
    keys={str(row[k]).casefold() for k in ('taxon_id','ncbi_taxid','scientific_name','common_name') if row.get(k) is not None}
    for key in keys:self._species_index.setdefault(key,[]).append(row)
  found={}
  for value in filter_values(term):
   matches=self._species_index.get(value.casefold(),[])
   taxa={r['ncbi_taxid'] for r in matches if r['ncbi_taxid'] is not None}
   if len(taxa)>1:raise ValueError('Ambiguous species name; use NCBI TaxID')
   for row in matches:found[row['taxon_id']]=row
  return list(found.values())
 def species(self,term,alias):
  if not term:return '',[]
  rr=self.species_records(term)
  if not rr:return ' AND 0',[]
  return f' AND {alias}.taxon_id IN (SELECT value FROM json_each(?))',[json.dumps([r['taxon_id'] for r in rr])]
 def pq(self,filename):return self.paths['identities']/filename
 def parquet(self,path,where='',args=(),limit=100):
  if not self.d:raise RuntimeError('Chemical catalog requires duckdb; install toolkit requirements')
  if not Path(path).exists():return []
  cur=self.d.execute('SELECT * FROM read_parquet(?)'+where+' LIMIT ?',[str(path),*args,limit]);names=[x[0] for x in cur.description];return [dict(zip(names,r)) for r in cur.fetchall()]
 def identifiers(self,term):
  if term in self.identifier_cache:return self.identifier_cache[term]
  term=term.strip();out=set()
  alias_file=self.paths.get('search_aliases')
  if alias_file and alias_file.exists():
   normalized=re.sub(r'\s+','',unicodedata.normalize('NFKC',term)).casefold()
   for alias in json.loads(alias_file.read_text('utf-8'))['aliases']:
    if normalized==re.sub(r'\s+','',unicodedata.normalize('NFKC',alias['label'])).casefold():
     out.add((alias['namespace'],alias['identifier']))
  if re.fullmatch(r'\d{2,7}-\d{2}-\d',term):out.add(('CAS',term))
  if term.upper().startswith('DTXSID'):out.add(('DTXSID',term.upper()))
  direct_cid=bool(re.fullmatch(r'(?:CID:?|PubChemCID:)?\s*\d+',term,re.I))
  if direct_cid:out.add(('PubChemCID',re.sub(r'\D','',term)))
  out.update(local_identifiers(self,term))
  if not self.d:
   self.identifier_cache[term]=sorted(out)
   return self.identifier_cache[term]
  def linked_cids():
   # Identifier values are meaningful only within their source namespace.
   cas=[v for n,v in out if n=='CAS'];dtx=[v for n,v in out if n=='DTXSID']
   if not cas and not dtx:return []
   return self.parquet(self.pq('CID-Identifiers.parquet')," WHERE (namespace='CAS' AND identifier IN (SELECT unnest(?))) OR (namespace='DSSTox Substance ID' AND identifier IN (SELECT unnest(?)))",[cas,dtx],10000)
  if not direct_cid:
   for r in linked_cids():out.add(('PubChemCID',str(r['cid'])))
  seeds=[term]+[v for ns,v in out]
  ds=self.parquet(self.pq('DSSToxCCDdump.parquet'),' WHERE DTXSID IN (SELECT unnest(?)) OR CASRN IN (SELECT unnest(?)) OR lower(PREFERRED_NAME)=lower(?) OR INCHIKEY=?',[seeds,seeds,term,term],1000)
  for r in ds:
   out.add(('DTXSID',r['DTXSID']))
   if re.fullmatch(r'\d{2,7}-\d{2}-\d',r.get('CASRN') or ''):out.add(('CAS',r['CASRN']))
  if not any(ns=='PubChemCID' for ns,v in out):
   for r in linked_cids():out.add(('PubChemCID',str(r['cid'])))
  if not out and self.pq('synonym-index.json').exists():
   key=term.lower();bucket=hashlib.md5(key.encode()).hexdigest()[:2]
   for p in (self.pq('synonym-index')/('bucket='+bucket)).glob('*.parquet'):
    for r in self.parquet(p,' WHERE lookup_key=?',[key],1000):out.add(('PubChemCID',str(r['cid'])))
  # Source cross-references are navigation links, never chemical-identity merges.
  cids=[int(v) for ns,v in out if ns=='PubChemCID']
  if cids and self.pq('CID-Identifiers.parquet').exists():
   cur=self.d.execute('SELECT cid,namespace,identifier FROM read_parquet(?) WHERE cid IN (SELECT unnest(?))',[str(self.pq('CID-Identifiers.parquet')),cids])
   for cid,ns,v in cur.fetchall():
    if ns=='CAS' and re.fullmatch(r'\d{2,7}-\d{2}-\d',v):out.add(('CAS',v))
    elif ns=='DSSTox Substance ID':out.add(('DTXSID',v))
  self.identifier_cache[term]=sorted(out)
  return self.identifier_cache[term]
 def chemicals(self,term,limit,offset):
  ids=self.identifiers(term);out=[];cids=sorted(int(v) for ns,v in ids if ns=='PubChemCID');dt=sorted(v for ns,v in ids if ns=='DTXSID')
  p=self.pq('DSSToxCCDdump.parquet')
  if p.exists():
   cur=self.d.execute('SELECT DTXSID AS source_id,PREFERRED_NAME AS name,CASRN AS cas,SMILES AS smiles,INCHIKEY AS inchikey,MOLECULAR_FORMULA AS formula,AVERAGE_MASS AS molecular_weight,IDENTIFIER AS aliases FROM read_parquet(?) WHERE DTXSID IN (SELECT unnest(?)) OR PREFERRED_NAME ILIKE ? ORDER BY CASE WHEN DTXSID IN (SELECT unnest(?)) THEN 0 ELSE 1 END,DTXSID LIMIT ? OFFSET ?',[str(p),dt,'%'+term+'%',dt,limit+1,offset]);names=[x[0] for x in cur.description]
   out.extend({**dict(zip(names,r)),'provider':'DSSTox','support_type':'pending_verification','assertion_kind':'source_identity','mass_derivation':'formula/structure calculation'} for r in cur.fetchall())
  ds_count=self.d.execute('SELECT count(*) FROM read_parquet(?) WHERE DTXSID IN (SELECT unnest(?)) OR PREFERRED_NAME ILIKE ?',[str(p),dt,'%'+term+'%']).fetchone()[0] if p.exists() else 0
  for cid in cids[max(0,offset-ds_count):max(0,offset-ds_count)+max(0,limit+1-len(out))]:
   r={'source_id':'PubChemCID:'+str(cid),'cid':cid,'provider':'PubChem','support_type':'pending_verification','assertion_kind':'source_identity'}
   for name in ('CID-Title.parquet','CID-SMILES.parquet','CID-InChI-Key.parquet','CID-Mass.parquet'):
    found=self.parquet(self.pq(name),' WHERE cid=?',[cid],1)
    if found:r.update(found[0])
   r['name']=r.get('title')
   if r.get('formula'):r['mass_derivation']='source formula/structure calculation'
   for meta in self.paths['sdf'].glob('*.json'):
    j=json.loads(meta.read_text('utf-8'))
    if j['min_cid']<=cid<=j['max_cid']:
     found=self.parquet(self.paths['sdf']/j['parquet'],' WHERE cid=?',[cid],1)
     if found:r.update({k:v for k,v in found[0].items() if k not in ('offset','length')});r['structure_2d_available']=True
   out.append(r)
  return {'matches':out[:limit],'returned':min(len(out),limit),'offset':offset,'has_more':offset+limit<ds_count+len(cids),'source_identifiers':[{'namespace':n,'identifier':v} for n,v in ids]}
 def observations_query(self,kind,term,species,support,limit,offset,source='',endpoint=''):
  types=self.types(kind,support);where='domain=? AND support_type IN ('+','.join('?' for _ in types)+')';args=[kind,*types]
  if term:
   ids=self.identifiers(term)
   if not ids:return {'matches':[],'returned':0,'offset':offset,'has_more':False}
   where+=' AND record_id IN (SELECT record_id FROM identifiers WHERE '+' OR '.join('(namespace=? AND identifier=?)' for _ in ids)+')';args.extend(v for pair in ids for v in pair)
  if species:
   values=filter_values(species);taxa=self.species_records(species);names=sorted(set(values+[r['scientific_name'] for r in taxa]))
   taxids=sorted({int(v) for v in values if str(v).isdigit()}|{r['ncbi_taxid'] for r in taxa if r['ncbi_taxid'] is not None})
   where+=' AND (species IN (SELECT value FROM json_each(?)) OR taxon_id IN (SELECT value FROM json_each(?)))';args.extend([json.dumps(names),json.dumps(taxids)])
  if source:
   source=re.sub(r'^https?://(?:dx\.)?doi\.org/','',source.strip(),flags=re.I)
   where+=' AND reference=?';args.append(source)
  if endpoint:
   where+=' AND instr(lower(property_name),lower(?))>0';args.append(endpoint)
  cols='record_id,provider,domain,property_name,value,value_text,unit,qualifier,value_min,value_max,temperature_c,ph,medium,species,taxon_id,exposure_conditions,target_id,support_type,assertion_kind,source_support_code,review_status,method,derivation,reference,source_url,asset_path,source_row'
  hint=''
  out=page(self.observations,'SELECT '+cols+' FROM observations'+hint+' WHERE '+where+' ORDER BY record_id',args,limit,offset)
  for r in out['matches']:r['identifiers']=rows(self.observations,'SELECT namespace,identifier FROM identifiers WHERE record_id=?',(r['record_id'],))
  bio_dir=self.paths.get('bioactivity')
  activity_ready=bio_dir and (bio_dir/'activities.json').exists()
  if kind=='bioactivity' and activity_ready and self.d and not source and not endpoint:
   local_count=self.observations.execute('SELECT count(*) FROM observations WHERE '+where,args).fetchone()[0]
   if offset+len(out['matches'])>=local_count:
    cids=[v for ns,v in (self.identifiers(term) if term else []) if ns=='PubChemCID']
    meta=json.loads((bio_dir/'activities.json').read_text('utf-8'))
    if meta.get('dataset'):
     bucket_ids={int(v)%meta['cid_buckets'] for v in cids} if term else None
     activity_path=[str(p) for p in (bio_dir/'activities').glob('part-*/cid_bucket=*/*.parquet') if bucket_ids is None or int(p.parent.name.split('=')[1]) in bucket_ids]
    else:activity_path=str(bio_dir/'activities.parquet')
    if not activity_path:return out
    fields=[x[0] for x in self.d.execute('DESCRIBE SELECT * FROM read_parquet(?)',[activity_path]).fetchall()]
    projection=','.join('"'+name.replace('"','""')+'" AS "'+name.replace(' ','').replace('"','""')+'"' for name in fields)
    sql='SELECT * FROM (SELECT '+projection+' FROM read_parquet(?)) WHERE support_type IN (SELECT unnest(?))';ps=[activity_path,types]
    if term:sql+=' AND CID IN (SELECT unnest(?))';ps.append(cids)
    if species:
     taxids=sorted({str(r['ncbi_taxid']) for r in self.species_records(species) if r['ncbi_taxid'] is not None})
     sql+=' AND AID IN (SELECT AID FROM read_parquet(?) WHERE list_has_any(regexp_split_to_array(coalesce("Taxonomy IDs",\'\'),\'[^0-9]+\'),?))';ps.extend([str(bio_dir/'assays.parquet'),taxids])
    ordering='source_row' if 'source_row' in fields else 'AID,SID,ActivityName,ActivityValue,ActivityUnit'
    cur=self.d.execute(sql+' ORDER BY '+ordering+' LIMIT ? OFFSET ?',[*ps,max(0,limit+1-len(out['matches'])),max(0,offset-local_count)])
    names=[r[0] for r in cur.description]
    out['matches'].extend(self.activity_records([dict(zip(names,v)) for v in cur.fetchall()],meta,bio_dir))
    out['has_more']=out['has_more'] or len(out['matches'])>limit;out['matches']=out['matches'][:limit];out['returned']=len(out['matches'])
  return out
 def activity_records(self,records,meta,bio_dir):
  aids=sorted({r['AID'] for r in records})
  assays={r['AID']:r for r in self.parquet(bio_dir/'assays.parquet',' WHERE AID IN (SELECT unnest(?))',[aids],len(aids))} if aids else {}
  for r in records:
   r.update({'record_id':f'PubChemBioAssay:{meta["raw_sha256"][:16]}:{r["source_row"]}','provider':'PubChemBioAssay','domain':'bioactivity','property_name':r.get('ActivityName') or r.get('ActivityOutcome'),'value_text':r.get('ActivityValue'),'unit':r.get('ActivityUnit'),'qualifier':r.get('ActivityQualifier'),'target_taxon_id':r.get('TargetTaxID'),'target_id':r.get('ProteinAccession') or r.get('GeneID'),'reference':r.get('PMID'),'review_status':None,'source_url':'https://pubchem.ncbi.nlm.nih.gov/bioassay/'+str(r.get('AID')),'asset_path':meta.get('raw_path'),'source_asset_sha256':meta.get('raw_sha256')})
   try:value=float(r.get('ActivityValue'));r['value']=value if math.isfinite(value) else None
   except (TypeError,ValueError):r['value']=None
   r['identifiers']=[{'namespace':n,'identifier':r[k]} for n,k in [('PubChemCID','CID'),('PubChemSID','SID')] if r.get(k)]
   a=assays.get(r['AID'],{});taxa=re.findall(r'\d+',a.get('Taxonomy IDs') or '')
   r.update({'assay_name':a.get('BioAssay Name'),'assay_type':a.get('BioAssay Types'),'source_name':a.get('Source Name'),'source_date':a.get('Modify Date'),'assay_taxonomy_ids':taxa,'taxon_id':int(taxa[0]) if len(taxa)==1 else None,'species_source_scope':'source assay taxonomy annotation; target taxonomy retained separately'})
   names=[]
   for tax in taxa:
    name=self.fish.execute('SELECT scientific_name FROM taxa WHERE ncbi_taxid=? LIMIT 1',(tax,)).fetchone();names.append(name[0] if name else 'TaxID '+tax)
   r['species']='; '.join(names) or None
  return records
 def activity_source(self,term):
  match=re.fullmatch(r'PubChemBioAssay:([a-f0-9]{16}):(\d+)',term)
  if not match:raise ValueError('Invalid activity record identifier')
  bio_dir=self.paths['bioactivity'];meta=json.loads((bio_dir/'activities.json').read_text('utf-8'));row=int(match[2])
  if match[1]!=meta['raw_sha256'][:16]:raise ValueError('Activity belongs to a different source snapshot')
  for receipt in (bio_dir/'activities').glob('part-*/complete.json'):
   chunk=json.loads(receipt.read_text('utf-8'))
   if chunk['first_record']<row<=chunk['first_record']+chunk['source_rows']:
    files=[str(p) for p in receipt.parent.glob('cid_bucket=*/*.parquet')]
    cur=self.d.execute('SELECT * FROM read_parquet(?) WHERE source_row=?',[files,row]);fields=[x[0] for x in cur.description];value=cur.fetchone()
    if value is None:break
    source=dict(zip(fields,value));record={k.replace(' ',''):v for k,v in source.items()}
    result=self.activity_records([record],meta,bio_dir)[0]
    result['original_record']={k:('' if v is None else v) for k,v in source.items() if k not in ('source_row','support_type','assertion_kind','cid_bucket')}
    return result
  raise ValueError('Activity record is absent or was excluded during import')
 def molecular(self,kind,term,species,support,limit,offset,assertion,sort_field=None,sort_direction='asc'):
  types=self.types(kind,support);extra,params=self.species(species,'m');word='%'+term+'%'
  if kind=='genes':
   eid='m.gene_id';base='genes m JOIN taxa t USING(taxon_id) LEFT JOIN gene_annotations a USING(gene_id)';fields='m.*,t.scientific_name,t.ncbi_taxid,a.ncbi_geneid,a.synonyms,a.chromosome';where='(m.name LIKE ? OR m.description LIKE ? OR a.synonyms LIKE ? OR m.gene_id=? OR a.ncbi_geneid=?)';args=[word,word,word,term,term];existence="'pending_verification'"
   if ':' in term:where='m.gene_id=?';args=[term]
  else:
   eid='m.protein_id';base='proteins m JOIN taxa t USING(taxon_id) LEFT JOIN protein_annotations a USING(protein_id)';fields='m.*,t.scientific_name,t.ncbi_taxid,a.accession,a.reviewed,a.protein_existence,a.go_ids,a.gene_ids,a.source_release';where='(m.gene_label LIKE ? OR m.name LIKE ? OR m.protein_id=? OR a.accession=?)';args=[word,word,term,term]
   direct_protein=bool(term and self.fish.execute('SELECT 1 FROM proteins WHERE protein_id=?',(term,)).fetchone())
   if direct_protein:where='m.protein_id=?';args=[term]
   if self.has_lookup and term and not direct_protein:
    gx,gp=self.species(species,'g')
    genes=rows(self.fish,'''SELECT g.gene_id,gt.ncbi_taxid FROM genes g JOIN taxa gt USING(taxon_id)
     LEFT JOIN gene_annotations ga USING(gene_id)
     WHERE (g.name=? COLLATE NOCASE OR g.gene_id=? OR ga.ncbi_geneid=? OR ('|'||coalesce(ga.synonyms,'')||'|') LIKE ?)'''+gx,[term,term,term,'%|'+term+'|%',*gp])
    linked=set()
    for gene in genes:
     linked.update(x[0] for x in self.fish.execute('SELECT protein_id FROM lookup.protein_gene_links WHERE gene_id=? AND taxon_id=?',(gene['gene_id'],gene['ncbi_taxid'])))
    if linked:
     where=where[:-1]+' OR m.protein_id IN (SELECT value FROM json_each(?)))';args.append(json.dumps(sorted(linked)))
   existence="CASE a.protein_existence WHEN 'Evidence at protein level' THEN 'experimental' WHEN 'Evidence at transcript level' THEN 'inferred_annotation' WHEN 'Inferred from homology' THEN 'inferred_annotation' WHEN 'Predicted' THEN 'model_prediction' ELSE 'pending_verification' END"
  args.extend(params);where+=extra
  placeholders=','.join('?' for _ in types)
  taxids=sorted({r['ncbi_taxid'] for r in self.species_records(species) if r['ncbi_taxid'] is not None}) if species else []
  taxclause=' AND taxon_id IN ('+','.join(str(int(t)) for t in taxids if t is not None)+')' if taxids else ''
  goselect=f"SELECT entity_id FROM support.assertions WHERE entity_type='{kind[:-1]}' AND support_type IN ({placeholders})"+taxclause
  gofilter=f'{eid} IN ({goselect})'
  if kind=='proteins' and 'pending_verification' in types:
   unknown_go='''EXISTS (SELECT 1 FROM json_each('["'||replace(replace(trim(coalesce(a.go_ids,''),'; '),' ',''),';','","')||'"]') item
     WHERE item.value<>'' AND NOT EXISTS(SELECT 1 FROM support.assertions known WHERE known.entity_type='protein'
       AND known.entity_id=m.protein_id AND known.taxon_id=t.ncbi_taxid AND known.property_id=item.value))'''
   gofilter='('+gofilter+' OR '+unknown_go+')'
  if support not in ('default',None,'') or assertion!='any':
   if assertion=='function':where+=' AND '+gofilter;args.extend(types)
   elif assertion=='existence':where+=' AND '+existence+' IN ('+placeholders+')';args.extend(types)
   else:
    if kind=='proteins':
     pe=[name for name,value in self.policy['protein_existence'].items() if value['support_type'] in types]
     if 'pending_verification' in types:
      # An untyped functional annotation is independently selectable even when
      # the source marks protein existence as predicted.
      where+=' AND ('+existence+' IN ('+placeholders+') OR '+gofilter+')';args.extend(types+types)
     elif self.has_existence:
      pequery='SELECT entity_id FROM support.existence WHERE support_type IN ('+placeholders+')'+taxclause
      where+=' AND '+eid+' IN ('+pequery+' UNION '+goselect+')';args.extend(types+types)
     else:
      pequery='SELECT protein_id FROM protein_annotations WHERE protein_existence IN ('+','.join('?' for _ in pe)+')' if pe else 'SELECT protein_id FROM protein_annotations WHERE 0'
      where+=' AND '+eid+' IN ('+pequery+' UNION '+goselect+')';args.extend(pe+types)
    else:where+=' AND ('+existence+' IN ('+placeholders+') OR '+gofilter+')';args.extend(types+types)
  # Streaming readers advance by the indexed entity identifier, without
  # repeatedly walking a growing OFFSET through the same source records.
  if getattr(self,'stream_after_id',None):
   where+=' AND '+eid+'>?';args.append(self.stream_after_id)
  # Let the species index narrow the working set before sorting source IDs.
  projection=fields+','+existence+' AS existence_support_type'
  if sort_field:
   ordering=molecular_order(kind,sort_field,sort_direction,existence,types,assertion)
   start=page_start(offset,limit)
   key=cache_key(self,kind,sort_field,sort_direction,{'term':term,'species':species,'support':support,'assertion':assertion,'page_start':start})
   def load(size):
    matches=rows(self.fish,'SELECT '+eid+' AS entity_id FROM '+base+' WHERE '+where+' ORDER BY '+ordering+' LIMIT ? OFFSET ?',[*args,size+1,start])
    total=self.fish.execute('SELECT count(*) FROM '+base+' WHERE '+where,args).fetchone()[0]
    return {'matches':matches[:size],'has_more':len(matches)>size,'total':total,'_prefix_offset':start}
   out=slice_prefix(cached_prefix(key,offset-start+limit+1,load),limit,offset,sort_field,sort_direction)
   selected=[r['entity_id'] for r in out['matches']]
   records=rows(self.fish,'SELECT '+projection+' FROM '+base+' WHERE '+eid+' IN (SELECT value FROM json_each(?))',[json.dumps(selected)]) if selected else []
   by_id={r['gene_id'] if kind=='genes' else r['protein_id']:r for r in records}
   out['matches']=[by_id[rid] for rid in selected];out['returned']=len(out['matches'])
  else:out=page(self.fish,'SELECT '+projection+' FROM '+base+' WHERE '+where+' ORDER BY '+eid,args,limit,offset)
  for r in out['matches']:
   key=r.get('gene_id') if kind=='genes' else r['protein_id']
   anns=rows(self.go,'SELECT id,property_id,property_name,qualifier,support_type,assertion_kind,source_code,source_reference,with_from,assigned_by,review_status,source_date,source_file,source_row FROM assertions WHERE entity_type=? AND entity_id=? AND taxon_id=? ORDER BY property_id,source_code',(kind[:-1],key,r['ncbi_taxid']))
   r['function_annotations']=anns
   if kind=='proteins':
    r['manual_review_status']=r.pop('reviewed',None)
    r['existence_assertion']=self.policy['protein_existence'].get(r.get('protein_existence'),{'support_type':'pending_verification'})
    known={a['property_id'] for a in anns}
    r['function_annotations'] += [{'property_id':g.strip(),'support_type':'pending_verification','assertion_kind':'functional_annotation','source_code':None,'reason':'GO ID retained in source TSV; assertion evidence code not supplied'} for g in (r.get('go_ids') or '').split(';') if g.strip() and g.strip() not in known]
   else:r['description_support_type']='pending_verification'
   # Filtering applies to the particular judgment. A predicted existence claim
   # does not erase a separately sourced function or identity record.
   r['excluded_function_annotations']=sum(a['support_type'] not in types for a in r['function_annotations'])
   r['function_annotations']=[a for a in r['function_annotations'] if a['support_type'] in types]
   matched={a['support_type'] for a in r['function_annotations']}
   if assertion!='function' and r['existence_support_type'] in types:matched.add(r['existence_support_type'])
   r['support_type']=next((x for x in ['experimental','inferred_annotation','pending_verification','model_prediction'] if x in matched),'pending_verification')
   r['matched_support_types']=sorted(matched);r['assertion_kind']='molecular_entity_with_separate_assertions'
   if kind=='proteins':
    if r['existence_support_type'] not in types:
     r['excluded_existence_support_type']=r['existence_support_type'];r['existence_assertion']=None
    r['source_gene_links']=rows(self.fish,'SELECT gene_id,taxon_id FROM lookup.protein_gene_links WHERE protein_id=? AND taxon_id=?',(key,r['ncbi_taxid'])) if self.has_lookup else []
  return out
 def pathways(self,term,species,support,limit,offset,sort_field=None,sort_direction='asc'):
  types=self.types('pathways',support);extra,params=self.species(species,'a')
  expr="CASE WHEN a.provider IN ('KEGG','Reactome') THEN 'inferred_annotation' ELSE 'pending_verification' END"
  mapping={'name':"coalesce(nullif(p.name,''),p.pathway_id)",'pathway_id':'p.pathway_id','provider':'a.provider','scientific_name':'t.scientific_name','support_type':expr}
  ordering=order_by(sort_text(mapping[sort_field]),sort_direction,'p.pathway_id') if sort_field else 'p.pathway_id'
  return page(self.fish,'SELECT p.*,a.provider,a.ncbi_taxid,a.annotation_type,a.source_url,t.scientific_name,'+expr+" AS support_type,'pathway_annotation' AS assertion_kind FROM pathways p LEFT JOIN pathway_annotations a USING(pathway_id) LEFT JOIN taxa t USING(taxon_id) WHERE (p.name LIKE ? OR p.pathway_id LIKE ?)"+extra+' AND '+expr+' IN ('+','.join('?' for _ in types)+') ORDER BY '+ordering,['%'+term+'%','%'+term+'%',*params,*types],limit,offset)
 def members(self,term,support,limit,offset,sort_field=None,sort_direction='asc'):
  types=self.types('pathways',support);expr="CASE WHEN a.provider='KEGG' OR ma.annotation_code='IEA' THEN 'inferred_annotation' ELSE 'pending_verification' END"
  sql='''SELECT p.*,g.name AS gene_symbol,g.description,t.scientific_name,t.ncbi_taxid,a.provider,ma.annotation_code,
 (SELECT group_concat(l.entity_id,';') FROM pathway_member_links l WHERE l.pathway_id=p.pathway_id AND l.external_member_id=p.external_member_id AND l.entity_type='protein') AS protein_ids,'''+expr+''' AS support_type,'pathway_membership' AS assertion_kind
 FROM pathway_source_members p LEFT JOIN genes g USING(gene_id) JOIN taxa t USING(taxon_id) JOIN pathway_annotations a USING(pathway_id)
 LEFT JOIN pathway_member_annotations ma ON ma.pathway_id=p.pathway_id AND ma.external_member_id=p.external_member_id
 WHERE p.pathway_id=? AND '''+expr+' IN ('+','.join('?' for _ in types)+')'
  expression="coalesce(nullif(gene_symbol,''),nullif(gene_id,''),external_member_id)" if sort_field=='gene_symbol' else sort_field
  ordering=order_by(sort_text(expression),sort_direction,'external_member_id') if sort_field else 'external_member_id'
  sql='SELECT * FROM ('+sql+') members ORDER BY '+ordering
  return page(self.fish,sql,[term,*types],limit,offset)
 def mechanisms(self,term,support,limit,offset,sort_field=None,sort_direction='asc'):
  types=self.types('mechanisms',support);rules=json.dumps(self.policy.get('mechanism_predicates',{}))
  sql='''SELECT m.*,coalesce(json_extract(rule.value,'$.support_type'),
   CASE evidence_kind WHEN 'observed' THEN 'experimental' ELSE 'pending_verification' END) AS support_type,
   coalesce(json_extract(rule.value,'$.assertion_kind'),CASE evidence_kind WHEN 'observed' THEN 'experimental_observation' ELSE 'inference_attribution_unverified' END) AS assertion_kind
   FROM mechanism_evidence m LEFT JOIN json_each(?) rule ON rule.key=m.predicate
   WHERE (subject LIKE ? OR object LIKE ?)'''
  ordering=order_by(sort_text(sort_field),sort_direction,'mechanism_id') if sort_field else 'mechanism_id'
  return page(self.fish,'SELECT * FROM ('+sql+') WHERE support_type IN ('+','.join('?' for _ in types)+') ORDER BY '+ordering,[rules,'%'+term+'%','%'+term+'%',*types],limit,offset)
 def compound_relations(self,term,limit,offset):
  cids=[int(v) for ns,v in self.identifiers(term) if ns=='PubChemCID'];result=[]
  for cid in cids:
   for filename,field,predicate in [('CID-Parent.parquet','parent_cid','has_parent'),('CID-Component.parquet','component_cids','has_component'),('CID-MeSH.parquet','mesh','source_mesh_annotation')]:
    for r in self.parquet(self.pq(filename),' WHERE cid=?',[cid],100):
     value=r[field];value=json.loads(value) if isinstance(value,str) and value.startswith('[') else value
     result.append({'cid':cid,'predicate':predicate,'object':value,'provider':'PubChem','support_type':'pending_verification','assertion_kind':'source_structure_or_index_annotation','source_file':filename})
  page_rows=result[offset:offset+limit]
  return {'matches':page_rows,'returned':len(page_rows),'offset':offset,'has_more':offset+limit<len(result)}
 def entity_pathways(self,term,support,limit,offset):
  if 'inferred_annotation' not in self.types('pathways',support):return {'matches':[],'returned':0,'offset':offset,'has_more':False}
  table='lookup.entity_pathways' if self.has_lookup else 'pathway_member_links'
  return page(self.fish,"SELECT DISTINCT p.pathway_id,p.name,a.provider,a.ncbi_taxid,'inferred_annotation' AS support_type FROM "+table+" l JOIN pathways p USING(pathway_id) JOIN pathway_annotations a USING(pathway_id) WHERE l.entity_id=? ORDER BY p.pathway_id",[term],limit,offset)
 def query(self,kind,term='',species='',support='default',limit=50,offset=0,assertion='any',sort_field=None,sort_direction='asc',source='',endpoint=''):
  sort_field,sort_direction=validate_sort(kind,sort_field,sort_direction)
  filters=normalize_query({'species':species,'support':support})
  if filters.get('_empty_filters'):
   return {'matches':[],'returned':0,'offset':offset,'has_more':False,'total':0,'applied_support_filter':[]}
  species=filters.get('species','');support=filters.get('support','default')
  if limit<1 or offset<0:raise ValueError('Invalid page')
  if kind=='coverage':return self.coverage()
  if kind in ('source-material','source-material-secondary','echa-endpoints'):
   if kind=='echa-endpoints':return self.source_material('ECHA',term,offset,limit,'echa')
   namespace,sep,identifier=term.partition(':')
   if not sep or namespace not in ('CAS','DTXSID'):raise ValueError('Use CAS:<number> or DTXSID:<number> for source-material')
   return self.source_material(namespace,identifier,offset,limit,'secondary' if kind.endswith('secondary') else 'primary')
  if kind=='chemicals':out=sorted_identities(self,term,limit,offset,sort_field,sort_direction) if sort_field else self.chemicals(term,limit,offset)
  elif kind in ('genes','proteins'):out=self.molecular(kind,term,species,support,limit,offset,assertion,sort_field,sort_direction)
  elif kind=='pathways':out=self.pathways(term,species,support,limit,offset,sort_field,sort_direction)
  elif kind=='members':out=self.members(term,support,limit,offset,sort_field,sort_direction)
  elif kind=='compound-relations':out=self.compound_relations(term,limit,offset)
  elif kind=='entity-pathways':out=self.entity_pathways(term,support,limit,offset)
  elif kind=='mechanisms':out=self.mechanisms(term,support,limit,offset,sort_field,sort_direction)
  elif kind in ('sequence','protein-record','gene-record','graph'):
   from database_queries import query as source_query
   out=source_query(self.fish,kind,term,species,limit,offset)
  elif kind=='structure':
   import indexed_gzip
   cid=int(term);out=None
   for p in self.paths['sdf'].glob('*.json'):
    j=json.loads(p.read_text('utf-8'))
    if not j['min_cid']<=cid<=j['max_cid']:continue
    match=self.parquet(self.paths['sdf']/j['parquet'],' WHERE cid=?',[cid],1)
    if not match:continue
    r=match[0]
    # Python's file handle supports Unicode Windows paths; zlib fopen does not.
    with open(j['raw_path'],'rb') as raw,indexed_gzip.IndexedGzipFile(fileobj=raw) as f:
     f.import_index(str(self.paths['sdf']/j['index']))
     f.seek(r['offset']);mol=(f.read(r['length']).decode('utf-8').split('M  END',1)[0]+'M  END\n').lstrip('\r\n')
    out={'cid':cid,'molfile':mol,'structure_type':'source 2D depiction','source_file':j['raw_path']};break
   if out is None:raise ValueError('CID has no completed local SDF shard')
  elif kind in ('properties','environment','bioactivity','toxicity'):
   if sort_field and not source and not endpoint:
    from workspace_api import WorkspaceAPI
    out=WorkspaceAPI(self.manifest).observations(self,{'kind':kind,'term':term,'species':species,'support':support,'sort_field':sort_field,'sort_direction':sort_direction},limit,offset)
   else:
    if sort_field and (source or endpoint):raise ValueError('Source/endpoint retrieval uses stable record order; omit sort_field')
    out=self.observations_query(kind,term,species,support,limit,offset,source,endpoint)
  elif kind=='observation' and term.startswith('PubChemBioAssay:'):out=self.activity_source(term)
  elif kind=='observation':
   rr=rows(self.observations,'SELECT * FROM observations WHERE record_id=?',(term,))
   if not rr:raise ValueError('Unknown observation')
   out=rr[0];out['original_record']=json.loads(zlib.decompress(out.pop('raw_zlib')))
   if out['provider']=='FishSnapshot0.3' and out['original_record'].get('raw_id'):
    original=self.fish.execute('SELECT row_json FROM raw_records WHERE raw_id=?',(out['original_record']['raw_id'],)).fetchone()
    if original:out['original_source_record']=json.loads(original[0])
  else:raise ValueError('Unknown catalog query '+kind)
  if kind in ('properties','environment','bioactivity','toxicity'):
   self.enrich_records(out.get('matches',[]));attach_context(self,out.get('matches',[]))
   diagnostics(self,out,kind,term,species,support,offset,source,endpoint)
  elif kind=='observation':
   self.enrich_records([out]);attach_context(self,[out])
  for record in out.get('matches',[]):
   if record.get('support_type'):record['support_label']=self.policy['labels'].get(record['support_type'],record['support_type'])
   if record.get('provider'):
    record['provider_label']='ECOTOX' if ':ECOTOX:' in record.get('record_id','') else {'FishSnapshot0.3':'既有鱼类资料','ECOTOX-Additional':'ECOTOX','ToxRef3.0':'ToxRefDB 3.0','ToxRef3.0-Effects':'ToxRefDB 3.0','EPA-ExperimentalRecords':'EPA 理化资料','PubChem-Annotations':'PubChem 来源注释','ToxVal9.7':'ToxValDB 9.7'}.get(record['provider'],record['provider'])
  out['support_labels']=self.policy['labels'];out['applied_support_filter']=self.types(kind,support);out['assertion_scope']=assertion
  if sort_field:out['sort_applied']=response_sort(sort_field,sort_direction)
  return self.resolve_paths(out)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path);p.add_argument('kind');p.add_argument('term',nargs='?',default='');p.add_argument('--species',default='');p.add_argument('--support',default='default');p.add_argument('--assertion',default='any',choices=['any','function','existence']);p.add_argument('--limit',type=int,default=50);p.add_argument('--offset',type=int,default=0);p.add_argument('--sort-field');p.add_argument('--sort-direction',choices=['asc','desc'],default='asc');p.add_argument('--output',type=Path);a=p.parse_args()
 with Catalog(a.catalog) as c:r=c.query(a.kind,a.term,a.species,a.support,a.limit,a.offset,a.assertion,a.sort_field,a.sort_direction)
 s=json.dumps(r,ensure_ascii=False,indent=2)
 if a.output:a.output.write_text(s+'\n','utf-8')
 else:print(s)

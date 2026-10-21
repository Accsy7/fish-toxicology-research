"""Global typed ordering for read-only catalog queries.

Sorting is performed before LIMIT/OFFSET. A bounded server-side prefix cache
reuses exact global top-N results; increasing the requested range recomputes a
larger prefix over the same full filtered source. It never truncates that scope.
"""
from collections import OrderedDict
from pathlib import Path
import copy,json,math,sqlite3,threading,zlib
from query_runtime import check_cancelled

SORT_FIELDS={
 'chemicals':('name','source_id','cas','formula','molecular_weight','provider'),
 'toxicity':('chemical_name','property_name','value','species','exposure_conditions','support_type','provider'),
 'properties':('chemical_name','property_name','value','species','exposure_conditions','support_type','provider'),
 'environment':('chemical_name','property_name','value','species','exposure_conditions','support_type','provider'),
 'bioactivity':('chemical_name','property_name','value','species','exposure_conditions','support_type','provider'),
 'pathways':('name','pathway_id','scientific_name','provider','support_type'),
 'genes':('name','gene_id','scientific_name','support_type','function_annotations'),
 'proteins':('name','protein_id','scientific_name','support_type','function_annotations'),
 'members':('gene_symbol','gene_id','protein_ids','support_type'),
 'species':('scientific_name','common_name','ncbi_taxid'),
 'sources':('title','publication_year','doi','pmid'),
 'endpoints':('property_name','domain','records'),
 'mechanisms':('subject','predicate','object','support_type','mechanism_id'),
}

def validate_sort(kind,field=None,direction='asc'):
 if not field:return None,'asc'
 if field not in SORT_FIELDS.get(kind,()):raise ValueError(f'Unsupported sort field for {kind}: {field}')
 direction=str(direction or 'asc').lower()
 if direction not in ('asc','desc'):raise ValueError('sort_direction must be asc or desc')
 return field,direction

def number(value):
 try:
  n=float(value)
  return n if math.isfinite(n) else None
 except (TypeError,ValueError,OverflowError):return None

def source_name(blob):
 if not blob:return None
 try:
  r=json.loads(zlib.decompress(blob))
  value=r.get('chemical_name') or r.get('chemical_names')
  return str(value) if value is not None else None
 except (ValueError,TypeError,zlib.error):return None

def prepare_sqlite(connection):
 connection.create_function('sort_number',1,number,deterministic=True)
 connection.create_function('sort_source_name',1,source_name,deterministic=True)
 connection.create_function('sort_text',1,lambda value:str(value).strip().lower() if value is not None and str(value).strip() else None,deterministic=True)

def text(expression,dialect='sqlite'):
 clean="NULLIF(TRIM(CAST("+expression+" AS TEXT)), '')"
 return 'sort_text('+clean+')' if dialect=='sqlite' else 'lower('+clean+')'

def order_by(expressions,direction,stable,dialect='sqlite'):
 """expressions are already typed trusted SQL, never raw request fields."""
 expressions=[expressions] if isinstance(expressions,str) else list(expressions)
 return ', '.join(f'{x} {direction.upper()} NULLS LAST' for x in expressions)+', '+stable+' ASC'

def response_sort(field,direction):
 return {'field':field,'direction':direction,'scope':'all_filtered_matches','missing':'last','tie_breaker':'stable source identifier ASC'}

def molecular_order(kind,field,direction,existence,types,assertion):
 eid='m.gene_id' if kind=='genes' else 'm.protein_id'
 if field in ('gene_id','protein_id'):expression=eid
 elif field=='name':expression="coalesce(nullif(m.name,''),"+eid+")"
 elif field=='scientific_name':expression='t.scientific_name'
 else:
  known="s.entity_type='"+kind[:-1]+"' AND s.entity_id="+eid+' AND s.taxon_id=t.ncbi_taxid'
  allowed=','.join("'"+v.replace("'","''")+"'" for v in types)
  unknown="0"
  if kind=='proteins' and 'pending_verification' in types:
   unknown='''(SELECT count(*) FROM json_each('["'||replace(replace(trim(coalesce(a.go_ids,''),'; '),' ',''),';','","')||'"]') item
    WHERE item.value<>'' AND NOT EXISTS(SELECT 1 FROM support.assertions s WHERE '''+known+''' AND s.property_id=item.value))'''
  if field=='function_annotations':
   expression='(SELECT count(*) FROM support.assertions s WHERE '+known+' AND s.support_type IN ('+allowed+')) + '+unknown
   return order_by(expression,direction,eid)
  clauses=[]
  for support in ('experimental','inferred_annotation','pending_verification','model_prediction'):
   if support not in types:continue
   condition="EXISTS(SELECT 1 FROM support.assertions s WHERE "+known+" AND s.support_type='"+support+"')"
   if support=='pending_verification' and kind=='proteins':condition+=' OR '+unknown+'>0'
   if assertion!='function':condition+=' OR '+existence+"='"+support+"'"
   clauses.append('WHEN ('+condition+") THEN '"+support+"'")
  expression='CASE '+' '.join(clauses)+" ELSE 'pending_verification' END"
 return order_by(text(expression),direction,eid)

_cache=OrderedDict()
_busy=set()
_condition=threading.Condition()
_CACHE_ENTRIES=12
_PREFIX_ROWS=4096

def page_start(offset,limit):
 # A page far into a large catalog must not allocate every preceding row.
 # The SQL cursor orders the full source, then returns this bounded window.
 return offset if offset+limit+1>_PREFIX_ROWS else 0

def fingerprint(c):
 result=[str(c.manifest),c.config.get('version')]
 for key in ('observations','fish_database','molecular_support','source_reconciliation','sdf','identities','bioactivity'):
  path=c.paths.get(key)
  if path and path.exists():
   stat=path.stat();result.extend([str(path),stat.st_size,stat.st_mtime_ns])
 return tuple(result)

def cached_prefix(key,needed,loader):
 """Return globally ordered rows. Cached rows are server data, not UI data."""
 while True:
  check_cancelled()
  with _condition:
   entry=_cache.get(key)
   if entry and (len(entry['matches'])>=needed or not entry.get('has_more')):
    _cache.move_to_end(key);return copy.deepcopy(entry)
   if key not in _busy:
    _busy.add(key);break
   _condition.wait(.2)
 try:
  size=max(512,1 << max(0,(needed-1).bit_length()))
  result=loader(size)
  check_cancelled()
  with _condition:
   _cache[key]=copy.deepcopy(result);_cache.move_to_end(key)
   while len(_cache)>_CACHE_ENTRIES:_cache.popitem(last=False)
  return result
 finally:
  with _condition:
   _busy.discard(key);_condition.notify_all()

def cache_key(c,kind,field,direction,query):
 clean={k:v for k,v in query.items() if k not in ('offset','limit','request_id')}
 return (fingerprint(c),kind,field,direction,json.dumps(clean,sort_keys=True,ensure_ascii=False,default=str))

def slice_prefix(result,limit,offset,field,direction):
 relative=offset-result.get('_prefix_offset',0)
 matches=result['matches'][relative:relative+limit]
 out={k:v for k,v in result.items() if k not in ('matches','returned','offset','has_more','_prefix_offset')}
 out.update(matches=matches,returned=len(matches),offset=offset,
   has_more=offset+len(matches)<result['total'] if result.get('total') is not None else len(result['matches'])>relative+limit or result.get('has_more',False),
   sort_applied=response_sort(field,direction))
 return out

def duck_rows(c,sql,args):
 cur=c.d.execute(sql,args);names=[x[0] for x in cur.description]
 return [dict(zip(names,r)) for r in cur.fetchall()]

def fish_identity_records(c,where='1',args=()):
 sql="""SELECT c.*,c.chemical_id AS source_id,c.preferred_name AS name,
 (SELECT identifier FROM chemical_identifiers i WHERE i.chemical_id=c.chemical_id
  AND i.namespace='CAS' ORDER BY identifier LIMIT 1) AS cas,
 NULL AS formula,NULL AS molecular_weight,'FishCatalog' AS provider,
 'pending_verification' AS support_type FROM chemicals c WHERE """+where
 return [dict(r) for r in c.fish.execute(sql,args)]

def register_rows(c,name,records,columns):
 # Small metadata/prefix tables use the existing DuckDB runtime; the portable
 # query package does not require an additional Arrow installation.
 c.d.execute('CREATE OR REPLACE TEMP TABLE '+name+' ('+','.join(k+' VARCHAR' for k in columns)+')')
 if records:c.d.executemany('INSERT INTO '+name+' VALUES ('+','.join('?' for _ in columns)+')',[[str(r[k]) if r.get(k) is not None else None for k in columns] for r in records])

def sorted_identities(c,term,limit,offset,field,direction):
 """Globally combine source identities, preserving each source identifier."""
 start=page_start(offset,limit)
 key=cache_key(c,'chemicals',field,direction,{'term':term,'page_start':start})
 def load(size):
  ids=c.identifiers(term) if term else []
  cids=sorted({int(v) for ns,v in ids if ns=='PubChemCID'})
  dtx=sorted({v for ns,v in ids if ns=='DTXSID'})
  metas=sorted((json.loads(p.read_text('utf8')) for p in c.paths['sdf'].glob('*.json')),key=lambda m:m['min_cid'])
  metas=[m for m in metas if not term or any(m['min_cid']<=cid<=m['max_cid'] for cid in cids)]
  pieces=[];params=[];total=0;counts={};fish=[]
  expressions={
   'PubChem':{'name':'name','source_id':"'PubChemCID:'||CAST(cid AS VARCHAR)",'cas':'CAST(NULL AS VARCHAR)','formula':'formula','molecular_weight':'molecular_weight','provider':"'PubChem'"},
   'DSSTox':{'name':'PREFERRED_NAME','source_id':'DTXSID','cas':"NULLIF(CASRN,'NOCAS')",'formula':'MOLECULAR_FORMULA','molecular_weight':'TRY_CAST(AVERAGE_MASS AS DOUBLE)','provider':"'DSSTox'"},
   'FishCatalog':{'name':"coalesce(nullif(name_zh,''),nullif(name,''),source_id)",'source_id':'source_id','cas':'cas','formula':'formula','molecular_weight':'TRY_CAST(molecular_weight AS DOUBLE)','provider':"'FishCatalog'"}}
  if metas:
   files=[str(c.paths['sdf']/m['parquet']) for m in metas]
   expr=expressions['PubChem'][field]
   if field=='name':expr="coalesce(nullif(name,''),'PubChemCID:'||CAST(cid AS VARCHAR))"
   sql="SELECT 'PubChemCID:'||CAST(cid AS VARCHAR) AS source_id,'PubChem' AS provider,"+expr+' AS sort_value FROM read_parquet(?, union_by_name=true)'
   params.append(files)
   if term:
    sql+=' WHERE cid IN (SELECT unnest(?))';params.append(cids)
    count=c.d.execute('SELECT count(*) FROM read_parquet(?) WHERE cid IN (SELECT unnest(?))',[files,cids]).fetchone()[0]
   else:count=sum(m['records'] for m in metas)
   pieces.append(sql);counts['PubChem']=count;total+=count
  ds=c.pq('DSSToxCCDdump.parquet')
  if ds.exists():
   where=' WHERE DTXSID IN (SELECT unnest(?)) OR PREFERRED_NAME ILIKE ?' if term else ''
   dsargs=[str(ds),dtx,'%'+term+'%'] if term else [str(ds)]
   count=c.d.execute('SELECT count(*) FROM read_parquet(?)'+where,dsargs).fetchone()[0]
   expr=expressions['DSSTox'][field]
   if field=='name':expr="coalesce(nullif(PREFERRED_NAME,''),DTXSID)"
   pieces.append("SELECT DTXSID AS source_id,'DSSTox' AS provider,"+expr+' AS sort_value FROM read_parquet(?)'+where)
   params+=dsargs;counts['DSSTox']=count;total+=count
  # The existing term search resolves DSSTox/PubChem; the unfiltered directory
  # additionally includes every original fish-catalog identity.
  if not term:
   fish=fish_identity_records(c)
   fields=['source_id','name','name_zh','cas','formula','molecular_weight','smiles','inchikey','cid','provider']
   register_rows(c,'sort_fish_identities',fish,fields)
   pieces.append("SELECT source_id,'FishCatalog' AS provider,"+expressions['FishCatalog'][field]+' AS sort_value FROM sort_fish_identities')
   counts['FishCatalog']=len(fish);total+=len(fish)
  if not pieces:return {'matches':[],'has_more':False,'total':0}
  typed='sort_value' if field=='molecular_weight' else text('sort_value','duckdb')
  ordering=order_by(typed,direction,'source_id','duckdb');query_offset=start;fetch_size=size+1
  backwards=start>total//2
  if backwards:
   ordering=typed+(' DESC' if direction=='asc' else ' ASC')+' NULLS FIRST, source_id DESC'
   fetch_size=max(0,min(size+1,total-start));query_offset=max(0,total-start-fetch_size)
  sql='SELECT source_id,provider FROM ('+' UNION ALL '.join(pieces)+') identities ORDER BY '+ordering+' LIMIT ? OFFSET ?'
  selected=duck_rows(c,sql,[*params,fetch_size,query_offset])
  if backwards:selected.reverse()
  more=len(selected)>size;selected=selected[:size]
  # Fetch display fields only for globally selected identities. Large SMILES,
  # InChIKey and structural fields do not participate in the ordering scan.
  by_id={r['source_id']:r for r in fish}
  selected_cids=[int(r['source_id'].split(':',1)[1]) for r in selected if r['provider']=='PubChem']
  if selected_cids:
   paths=[str(c.paths['sdf']/m['parquet']) for m in metas if any(m['min_cid']<=cid<=m['max_cid'] for cid in selected_cids)]
   records=duck_rows(c,"SELECT 'PubChemCID:'||CAST(cid AS VARCHAR) AS source_id,name,NULL AS name_zh,NULL AS cas,formula,molecular_weight,smiles,inchikey,cid,'PubChem' AS provider FROM read_parquet(?) WHERE cid IN (SELECT unnest(?))",[paths,selected_cids])
   by_id.update({r['source_id']:r for r in records})
  selected_dtx=[r['source_id'] for r in selected if r['provider']=='DSSTox']
  if selected_dtx:
   records=duck_rows(c,"SELECT DTXSID AS source_id,PREFERRED_NAME AS name,NULL AS name_zh,NULLIF(CASRN,'NOCAS') AS cas,MOLECULAR_FORMULA AS formula,TRY_CAST(AVERAGE_MASS AS DOUBLE) AS molecular_weight,SMILES AS smiles,INCHIKEY AS inchikey,NULL AS cid,'DSSTox' AS provider FROM read_parquet(?) WHERE DTXSID IN (SELECT unnest(?))",[str(ds),selected_dtx])
   by_id.update({r['source_id']:r for r in records})
  result=[by_id[r['source_id']] for r in selected]
  for r in result:r.update(support_type='pending_verification',structure_2d_available=r['provider']=='PubChem')
  return {'matches':result,'has_more':more,'total':total,'source_counts':counts,'count_unit':'source_identity_record','_prefix_offset':start}
 return slice_prefix(cached_prefix(key,offset-start+limit+1,load),limit,offset,field,direction)

def observation_keys(c,field,alias='o'):
 prepare_sqlite(c.observations)
 col=lambda name:alias+'.'+name
 if field=='chemical_name':
  recon=c.paths.get('source_reconciliation');context="NULL"
  if recon and (recon/'reconciliation.sqlite3').exists():
   if 'sort_recon' not in [r[1] for r in c.observations.execute('PRAGMA database_list')]:
    c.observations.execute('ATTACH DATABASE ? AS sort_recon',((recon/'reconciliation.sqlite3').as_uri()+'?mode=ro',))
   context="(SELECT coalesce(json_extract(context_json,'$.chemical_name'),json_extract(context_json,'$.toxref_chemical.chemical_name'),json_extract(context_json,'$.toxref_chemical.name')) FROM sort_recon.record_context rc WHERE rc.record_id="+col('record_id')+")"
  chemical="coalesce(sort_source_name("+col('raw_zlib')+"),"+context+",(SELECT group_concat(identifier,', ') FROM (SELECT identifier FROM identifiers ci WHERE ci.record_id="+col('record_id')+" AND namespace='CAS' ORDER BY identifier)),"+col('record_id')+")"
  expressions=text(chemical)
 elif field=='value':
  numeric='coalesce(sort_number('+col('value')+'),sort_number('+col('value_text')+'))'
  # Measured numeric results are numeric; qualitative source outcomes sort as
  # text after them. An absent value always remains last in both directions.
  exists="CASE WHEN "+numeric+" IS NOT NULL THEN 0 WHEN nullif(trim(coalesce("+col('value_text')+",'')),'') IS NOT NULL THEN 1 ELSE 2 END"
  return [exists,numeric,text(col('value_text'))]
 elif field=='exposure_conditions':
  valid='CASE WHEN json_valid('+col('exposure_conditions')+') THEN '+col('exposure_conditions')+" ELSE '{}' END"
  expressions=[]
  for name,typ in [('concentration_value','number'),('concentration_unit','text'),('duration_value','number'),('duration_unit','text'),('life_stage','text')]:
   expr="json_extract("+valid+",'$."+name+"')"
   expressions.append('sort_number('+expr+')' if typ=='number' else text(expr))
 else:expressions=text(col(field))
 return [expressions] if isinstance(expressions,str) else expressions

def observation_order(c,field,direction,alias='o'):
 expressions=observation_keys(c,field,alias)
 if field=='value':return expressions[0]+' ASC, '+order_by(expressions[1:],direction,alias+'.record_id')
 return order_by(expressions,direction,alias+'.record_id')

def sorted_observation_ids(c,a,where,args,limit,offset):
 field,direction=validate_sort(a['kind'],a.get('sort_field'),a.get('sort_direction'))
 start=page_start(offset,limit)
 key=cache_key(c,'observations:'+a['kind'],field,direction,{**a,'page_start':start})
 def load(size):
  ordering=observation_order(c,field,direction)
  result=[dict(r) for r in c.observations.execute('SELECT o.record_id FROM observations o WHERE '+where+' ORDER BY '+ordering+' LIMIT ? OFFSET ?',[*args,size+1,start])]
  total=c.observations.execute('SELECT count(*) FROM observations o WHERE '+where,args).fetchone()[0]
  return {'matches':result[:size],'has_more':len(result)>size,'total':total,'_prefix_offset':start}
 return slice_prefix(cached_prefix(key,offset-start+limit+1,load),limit,offset,field,direction)

def _record_keys(record,field):
 if field=='value':
  n=number(record.get('value'));n=number(record.get('value_text')) if n is None else n
  raw=record.get('value_text');raw=str(raw).strip() if raw is not None else None
  return [0 if n is not None else 1 if raw else 2,n,raw.lower() if raw else None]
 if field=='exposure_conditions':
  conditions=record.get('exposure_conditions') or {}
  if isinstance(conditions,str):
   try:conditions=json.loads(conditions)
   except ValueError:conditions={}
  norm=lambda v:str(v).strip().lower() if v is not None and str(v).strip() else None
  return [number(conditions.get('concentration_value')),norm(conditions.get('concentration_unit')),
          number(conditions.get('duration_value')),norm(conditions.get('duration_unit')),norm(conditions.get('life_stage'))]
 value=record.get(field)
 return [str(value).strip().lower() if value is not None and str(value).strip() else None]

def sorted_bioactivity(api,c,a,limit,offset):
 """Order the full SQLite/BioAssay union by typed keys, then hydrate a page."""
 field,direction=validate_sort('bioactivity',a.get('sort_field'),a.get('sort_direction'))
 start=page_start(offset,limit)
 key=cache_key(c,'bioactivity',field,direction,{**a,'page_start':start})
 def load(size):
  where,args=api.observation_where(c,a)
  expressions=observation_keys(c,field)
  names=['k'+str(i) for i in range(len(expressions))]
  local=[dict(r) for r in c.observations.execute('SELECT o.record_id,'+','.join(expr+' AS '+name for expr,name in zip(expressions,names))+' FROM observations o WHERE '+where,args)]
  columns=['record_id VARCHAR']+[name+(' DOUBLE' if (field=='value' and i in (0,1)) or (field=='exposure_conditions' and i in (0,2)) else ' VARCHAR') for i,name in enumerate(names)]
  c.d.execute('CREATE OR REPLACE TEMP TABLE sort_local_bio ('+','.join(columns)+')')
  if local:c.d.executemany('INSERT INTO sort_local_bio VALUES ('+','.join('?' for _ in columns)+')',[[r['record_id'],*[r[name] for name in names]] for r in local])
  pieces=['SELECT * FROM sort_local_bio'];params=[];total=len(local)
  bio=c.paths.get('bioactivity');meta=None;files=[]
  if bio and (bio/'activities.json').exists():
   meta=json.loads((bio/'activities.json').read_text('utf8'));term=a.get('term','').strip()
   cids=[v for ns,v in c.identifiers(term) if ns=='PubChemCID'] if term else []
   buckets={int(v)%meta['cid_buckets'] for v in cids} if term else None
   files=[str(p) for p in (bio/'activities').glob('part-*/cid_bucket=*/*.parquet') if buckets is None or int(p.parent.name.split('=')[1]) in buckets]
   types=c.types('bioactivity',a.get('support','default'))
   if files:
    parts=['b.support_type IN (SELECT unnest(?))'];params=[files,types]
    if term:parts.append('b.CID IN (SELECT unnest(?))');params.append(cids)
    if a.get('species'):
     taxids=sorted({str(r['ncbi_taxid']) for r in c.species_records(a['species']) if r['ncbi_taxid'] is not None})
     parts.append("b.AID IN (SELECT AID FROM read_parquet(?) WHERE list_has_any(regexp_split_to_array(coalesce(\"Taxonomy IDs\",''),'[^0-9]+'),?))")
     params.extend([str(bio/'assays.parquet'),taxids])
    base='read_parquet(?) b';prefix='PubChemBioAssay:'+meta['raw_sha256'][:16]+':'
    stable="'"+prefix+"'||CAST(b.source_row AS VARCHAR)"
    expression={'chemical_name':stable,'property_name':"coalesce(nullif(b.\"Activity Name\",''),b.\"Activity Outcome\")",
       'value':'CASE WHEN isfinite(TRY_CAST(b."Activity Value" AS DOUBLE)) THEN TRY_CAST(b."Activity Value" AS DOUBLE) ELSE NULL END',
       'species':'species_for_sort','exposure_conditions':'NULL','support_type':'b.support_type','provider':"'PubChemBioAssay'"}[field]
    if field=='species':
     species={}
     for r in c.fish.execute('SELECT ncbi_taxid,scientific_name FROM taxa WHERE ncbi_taxid IS NOT NULL'):
      species.setdefault(str(r['ncbi_taxid']),r['scientific_name'])
     register_rows(c,'sort_taxon_names',[{'taxid':k,'scientific_name':v} for k,v in species.items()],['taxid','scientific_name'])
     assay_path="'"+str(bio/'assays.parquet').replace("'","''")+"'"
     assay_sql="SELECT AID,string_agg(coalesce(n.scientific_name,'TaxID '||u.taxid),'; ' ORDER BY u.ordinality) species_for_sort FROM read_parquet("+assay_path+") a,unnest(regexp_extract_all(coalesce(a.\"Taxonomy IDs\",''),'[0-9]+')) WITH ORDINALITY u(taxid,ordinality) LEFT JOIN sort_taxon_names n ON n.taxid=u.taxid GROUP BY AID"
     c.d.execute('CREATE OR REPLACE TEMP VIEW sort_assay_species AS '+assay_sql)
     base+=' LEFT JOIN sort_assay_species s ON s.AID=b.AID'
    if field=='value':
     remote_keys=["CASE WHEN "+expression+" IS NOT NULL THEN 0 WHEN nullif(trim(coalesce(b.\"Activity Value\",'')),'') IS NOT NULL THEN 1 ELSE 2 END",expression,text('b."Activity Value"','duckdb')]
    elif field=='exposure_conditions':remote_keys=['NULL']*5
    else:remote_keys=[text(expression,'duckdb')]
    pieces.append('SELECT '+stable+' AS record_id,'+','.join(expr+' AS '+name for expr,name in zip(remote_keys,names))+' FROM '+base+' WHERE '+' AND '.join(parts))
    if not term and not a.get('species'):remote_total=sum(meta['rows_by_support'].get(t,0) for t in types)
    else:remote_total=c.d.execute('SELECT count(*) FROM read_parquet(?) b WHERE '+' AND '.join(parts),params).fetchone()[0]
    total+=remote_total
  ordering=('k0 ASC, '+order_by(names[1:],direction,'record_id','duckdb')) if field=='value' else order_by(names,direction,'record_id','duckdb')
  selected=[r[0] for r in c.d.execute('SELECT record_id FROM ('+' UNION ALL '.join(pieces)+') candidates ORDER BY '+ordering+' LIMIT ? OFFSET ?',[*params,size+1,start]).fetchall()]
  more=len(selected)>size;selected=selected[:size]
  local_ids=[rid for rid in selected if not rid.startswith('PubChemBioAssay:')]
  records=api.observation_records(c,local_ids)
  source_rows=[int(rid.rsplit(':',1)[1]) for rid in selected if rid.startswith('PubChemBioAssay:')]
  if source_rows:
   ranges={}
   for receipt in (bio/'activities').glob('part-*/complete.json'):
    item=json.loads(receipt.read_text('utf8'));ranges[receipt.parent.name]=(item['first_record'],item['first_record']+item['source_rows'])
   needed={name for name,(first,last) in ranges.items() if any(first<row<=last for row in source_rows)}
   selected_files=[path for path in files if not ranges or Path(path).parent.parent.name in needed]
   remote=duck_rows(c,'SELECT * FROM read_parquet(?) WHERE source_row IN (SELECT unnest(?))',[selected_files,source_rows])
   remote_records=c.activity_records([{k.replace(' ',''):v for k,v in row.items()} for row in remote],meta,bio)
   c.enrich_records(remote_records);records+=remote_records
  by_id={r['record_id']:r for r in records}
  return {'matches':[by_id[rid] for rid in selected],'has_more':more,'total':total,'_prefix_offset':start}
 return slice_prefix(cached_prefix(key,offset-start+limit+1,load),limit,offset,field,direction)

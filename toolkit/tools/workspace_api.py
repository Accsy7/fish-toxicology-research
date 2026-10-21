"""Read-only adapter between the approved workspace and the shared catalog.

Pagination is applied after filters. Relations retain the source record and its
support type; this module never infers a toxicological mechanism.
"""
from pathlib import Path
from functools import lru_cache
import json, re, hashlib, sqlite3
from catalog_queries import Catalog, rows, page, filter_values, normalize_query
from catalog_quality import attach_context, diagnostics
from global_sort import validate_sort, text as sort_text, order_by, prepare_sqlite, response_sort, sorted_identities, sorted_observation_ids, sorted_bioactivity

NUMERIC = ('toxicity', 'properties', 'environment', 'bioactivity')
LABELS = {'experimental':'实验结果','inferred_annotation':'推定注释',
          'model_prediction':'模型预测','pending_verification':'尚待核对'}

def text_id(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:20]

def parse_conditions(r):
    value=r.get('exposure_conditions')
    try:return json.loads(value) if isinstance(value,str) else value or {}
    except (ValueError,TypeError):return {'reported_conditions':value}

class WorkspaceAPI:
    def __init__(self, catalog):
        self.path=Path(catalog)

    @lru_cache(maxsize=1)
    def meta(self):
        with Catalog(self.path) as c:
            taxa=rows(c.fish,'SELECT ncbi_taxid,scientific_name,common_name FROM taxa ORDER BY scientific_name')
            taxa=list({str(r['ncbi_taxid'] or r['scientific_name']):r for r in taxa}.values())
            families=rows(c.fish,'SELECT * FROM chemical_categories WHERE parent_id IS NOT NULL ORDER BY label')
            endpoints=rows(c.observations,'SELECT domain,property_name,count(*) AS records FROM observations INDEXED BY observation_filter GROUP BY domain,property_name')
            coverage=c.coverage()
        return {'families':families,'taxa':taxa,'endpoints':endpoints,'support_labels':LABELS,
                'coverage':coverage,'api_version':'1.5.1-rc.1','ui_version':'independent',
                'frontend_bundled':False,'supported_independent_frontend':'1.13.1-local.1','catalog_version':c.config['version'],
                'classification_note':'家族筛选使用已收录的来源分类；尚未建立全量化合物家族分类。'}

    def family_identifiers(self,c,family):
        if not family:return []
        return sorted({r['identifier'] for r in rows(c.fish,'''SELECT i.identifier FROM chemical_identifiers i
          JOIN chemical_category_memberships m USING(chemical_id) WHERE m.category_id IN (SELECT value FROM json_each(?))''',[json.dumps(filter_values(family))])
          if re.fullmatch(r'\d{2,7}-\d{2}-\d',r['identifier'] or '')})

    def observation_where(self,c,a):
        kind=a.get('kind','toxicity');types=c.types(kind,a.get('support','default'))
        where='o.domain=? AND o.support_type IN ('+','.join('?' for _ in types)+')';args=[kind,*types]
        term=a.get('term','').strip()
        if term:
            ids=c.identifiers(term)
            if not ids:return '0',[]
            where+=' AND o.record_id IN (SELECT record_id FROM identifiers WHERE '+ ' OR '.join('(namespace=? AND identifier=?)' for _ in ids)+')'
            args.extend(v for pair in sorted(ids) for v in pair)
        family=a.get('family','')
        if family:
            ids=self.family_identifiers(c,family)
            if not ids:return '0',[]
            where+=" AND o.record_id IN (SELECT record_id FROM identifiers WHERE namespace='CAS' AND identifier IN (SELECT value FROM json_each(?)))";args.append(json.dumps(ids))
        if a.get('species'):
            values=filter_values(a['species']);names=sorted(set(values+[r['scientific_name'] for r in c.species_records(values)]))
            where+=' AND (o.species IN (SELECT value FROM json_each(?)) OR CAST(o.taxon_id AS TEXT) IN (SELECT value FROM json_each(?)))';args.extend([json.dumps(names),json.dumps(values)])
        if a.get('endpoint'):
            values=filter_values(a['endpoint'],'||');where+=' AND o.property_name IN (SELECT value FROM json_each(?))';args.append(json.dumps(values))
        if a.get('stage'):where+=" AND json_valid(o.exposure_conditions) AND json_extract(o.exposure_conditions,'$.life_stage')=?";args.append(a['stage'])
        if a.get('source'):
            source=re.sub(r'^https?://(?:dx\.)?doi\.org/','',str(a['source']).strip(),flags=re.I)
            where+=' AND o.reference=?'
            args.append(source)
        return where,args

    def observations(self,c,a,limit,offset):
        # The very large BioAssay source uses the catalog's CID-bucket reader.
        if a['kind']=='bioactivity':
            if a.get('family') or a.get('endpoint') or a.get('stage'):
                raise ValueError('生物活性查询请使用物质名称或编号、物种和资料类型筛选。')
            if a.get('sort_field'):return sorted_bioactivity(self,c,a,limit,offset)
            return c.query('bioactivity',a.get('term',''),a.get('species',''),a.get('support','default'),limit,offset)
        where,args=self.observation_where(c,a)
        # Select identifiers before materializing large source condition fields.
        # With multiple support types SQLite otherwise sorts millions of full
        # records to return a short page, despite a covering identifier index.
        if a.get('sort_field'):
            selection=sorted_observation_ids(c,a,where,args,limit,offset)
            out={**selection,'matches':self.observation_records(c,[r['record_id'] for r in selection['matches']])}
            return diagnostics(c,out,a['kind'],a.get('term',''),a.get('species',''),a.get('support','default'),offset,a.get('source',''),a.get('endpoint',''))
        selected=rows(c.observations,'SELECT o.record_id FROM observations o WHERE '+where+' ORDER BY record_id LIMIT ? OFFSET ?',[*args,limit+1,offset])
        ids=[r['record_id'] for r in selected[:limit]]
        records=self.observation_records(c,ids)
        out={'matches':records,'returned':len(records),'offset':offset,'has_more':len(selected)>limit}
        return diagnostics(c,out,a['kind'],a.get('term',''),a.get('species',''),a.get('support','default'),offset,a.get('source',''),a.get('endpoint',''))

    def observation_records(self,c,ids):
        cols='record_id,provider,domain,property_name,value,value_text,unit,qualifier,value_min,value_max,temperature_c,ph,medium,species,taxon_id,exposure_conditions,target_id,support_type,assertion_kind,source_support_code,review_status,method,derivation,reference,source_url,asset_path,source_row'
        records=rows(c.observations,'SELECT '+cols+' FROM observations o WHERE record_id IN (SELECT value FROM json_each(?))',[json.dumps(ids)]) if ids else []
        by_id={r['record_id']:r for r in records};records=[by_id[rid] for rid in ids if rid in by_id]
        for r in records:
            r['identifiers']=rows(c.observations,'SELECT namespace,identifier FROM identifiers WHERE record_id=? ORDER BY namespace,identifier',[r['record_id']])
            cas=[i['identifier'] for i in r['identifiers'] if i['namespace']=='CAS']
            r['chemical_name']=', '.join(cas) or r['record_id']
        c.enrich_records(records)
        return attach_context(c,records)

    def scoped_chemicals(self,c,a,limit,offset):
        where=[];params=[];term=a.get('term','')
        if a.get('family'):
            values=filter_values(a['family']);where.append('c.chemical_id IN (SELECT chemical_id FROM chemical_category_memberships WHERE category_id IN (SELECT value FROM json_each(?)))');params.append(json.dumps(values))
        if term:
            identifiers=[v for ns,v in c.identifiers(term) if ns=='CAS']
            clause='(c.preferred_name LIKE ? OR c.name_zh LIKE ? OR c.chemical_id IN (SELECT chemical_id FROM chemical_identifiers WHERE identifier=? COLLATE NOCASE)'
            params.extend(['%'+term+'%','%'+term+'%',term])
            if identifiers:
                clause+=' OR c.chemical_id IN (SELECT chemical_id FROM chemical_identifiers WHERE namespace=\'CAS\' AND identifier IN (SELECT value FROM json_each(?)))';params.append(json.dumps(identifiers))
            where.append(clause+')')
        if a.get('species'):
            oa={**a,'kind':'toxicity','family':'','term':''};w,p=self.observation_where(c,oa)
            c.fish.execute('ATTACH DATABASE ? AS obs',(c.paths['observations'].as_uri()+'?mode=ro',))
            w=w.replace('SELECT record_id FROM identifiers','SELECT record_id FROM obs.identifiers')
            where.append("c.chemical_id IN (SELECT ci.chemical_id FROM chemical_identifiers ci JOIN obs.identifiers i ON i.namespace='CAS' AND i.identifier=ci.identifier JOIN obs.observations o ON o.record_id=i.record_id WHERE "+w+')');params.extend(p)
        ordering='c.chemical_id'
        if a.get('sort_field'):
            field,direction=validate_sort('chemicals',a['sort_field'],a.get('sort_direction'))
            expr={'name':"coalesce(nullif(c.name_zh,''),c.preferred_name)",'source_id':'c.chemical_id',
                'cas':"(SELECT identifier FROM chemical_identifiers i WHERE i.chemical_id=c.chemical_id AND namespace='CAS' ORDER BY identifier LIMIT 1)",
                'formula':'NULL','molecular_weight':'NULL','provider':"'FishCatalog'"}[field]
            ordering=order_by(expr if field=='molecular_weight' else sort_text(expr),direction,'c.chemical_id')
        sql="SELECT c.*,c.chemical_id AS source_id,'FishCatalog' AS provider,'pending_verification' AS support_type FROM chemicals c WHERE "+(' AND '.join(where) or '1')+' ORDER BY '+ordering
        out=page(c.fish,sql,params,limit,offset)
        if a.get('sort_field'):
            out['total']=c.fish.execute('SELECT count(*) FROM chemicals c WHERE '+(' AND '.join(where) or '1'),params).fetchone()[0]
            out['sort_applied']=response_sort(field,direction)
        for r in out['matches']:
            r['identifiers']=rows(c.fish,'SELECT namespace,identifier FROM chemical_identifiers WHERE chemical_id=?',[r['chemical_id']])
            r['cas']=next((x['identifier'] for x in r['identifiers'] if re.fullmatch(r'\d{2,7}-\d{2}-\d',x['identifier'] or '')),None);r['name']=r['preferred_name']
        return out

    def search(self,a):
        a=normalize_query(a);kind=a.get('kind','chemicals');limit=int(a.get('limit',50));offset=int(a.get('offset',0))
        field,direction=validate_sort(kind,a.get('sort_field'),a.get('sort_direction'))
        if not 1<=limit<=500 or offset<0:raise ValueError('Page size must be 1..500 and offset nonnegative')
        if a.get('_empty_filters'):return {'matches':[],'returned':0,'total':0,'offset':offset,'has_more':False,'query':a,'applied_support_filter':[]}
        with Catalog(self.path) as c:
            if kind=='chemicals':
                if a.get('family') or a.get('species'):out=self.scoped_chemicals(c,a,limit,offset)
                elif field:out=sorted_identities(c,a.get('term','').strip(),limit,offset,field,direction)
                elif not a.get('term','').strip():
                    # Read one indexed SDF range at a time, rather than loading 125M rows.
                    metas=sorted((json.loads(p.read_text('utf8')) for p in c.paths['sdf'].glob('*.json')),key=lambda x:x['min_cid'])
                    remain=offset;outrows=[];total=sum(x['records'] for x in metas)
                    for m in metas:
                        if remain>=m['records']:remain-=m['records'];continue
                        rs=c.parquet(c.paths['sdf']/m['parquet'],' ORDER BY cid OFFSET ?',[remain],limit+1-len(outrows));remain=0
                        for r in rs:r.update(source_id='PubChemCID:'+str(r['cid']),name=r.get('name') or r.get('iupac_name'),provider='PubChem',support_type='pending_verification',structure_2d_available=True)
                        outrows.extend(rs)
                        if len(outrows)>limit:break
                    out={'matches':outrows[:limit],'returned':min(len(outrows),limit),'has_more':offset+limit<total,'offset':offset,'total':total}
                else:out=c.query('chemicals',a.get('term',''),limit=limit,offset=offset)
            elif kind in NUMERIC:out=self.observations(c,{**a,'kind':kind},limit,offset)
            elif kind=='species':
                term=a.get('term','');ordering='scientific_name,taxon_id'
                if field:ordering=order_by(field if field=='ncbi_taxid' else sort_text(field),direction,'taxon_id')
                out=page(c.fish,'SELECT * FROM taxa WHERE scientific_name LIKE ? OR common_name LIKE ? OR CAST(ncbi_taxid AS TEXT)=? ORDER BY '+ordering,['%'+term+'%','%'+term+'%',term],limit,offset)
            elif kind=='sources':
                term=a.get('term','');ordering='source_id'
                if field:
                    prepare_sqlite(c.fish)
                    expression="coalesce(nullif(title,''),nullif(doi,''),source_id)" if field=='title' else field
                    ordering=order_by('sort_number('+expression+')' if field in ('publication_year','pmid') else sort_text(expression),direction,'source_id')
                out=page(c.fish,'SELECT * FROM sources'+(' WHERE title LIKE ? OR doi LIKE ? OR pmid=?' if term else '')+' ORDER BY '+ordering,['%'+term+'%','%'+term+'%',term] if term else [],limit,offset)
            elif kind=='endpoints':
                records=[r for r in self.meta()['endpoints'] if a.get('term','').lower() in r['property_name'].lower()]
                if field:
                    with sqlite3.connect(':memory:') as meta:
                        meta.row_factory=sqlite3.Row
                        prepare_sqlite(meta)
                        meta.execute('CREATE TABLE endpoints(property_name TEXT,domain TEXT,records INTEGER)')
                        meta.executemany('INSERT INTO endpoints VALUES(?,?,?)',[(r['property_name'],r['domain'],r['records']) for r in records])
                        ordering=order_by(field if field=='records' else sort_text(field),direction,"domain||':'||property_name")
                        out=page(meta,'SELECT * FROM endpoints ORDER BY '+ordering,[],limit,offset)
                        out['total']=len(records)
                else:
                    out={'matches':records[offset:offset+limit],'offset':offset,'returned':len(records[offset:offset+limit]),'has_more':offset+limit<len(records)}
            else:out=c.query(kind,a.get('term',''),a.get('species',''),a.get('support','default'),limit,offset,a.get('assertion','any'),sort_field=field,sort_direction=direction)
            if field:out['sort_applied']=response_sort(field,direction)
            for r in out.get('matches',[]):r['support_label']=LABELS.get(r.get('support_type'),r.get('support_type'))
            out['applied_support_filter']=c.types(kind,a.get('support','default'))
            out=c.resolve_paths(out)
        out['query']={**a,'kind':kind,'limit':limit,'offset':offset};out['catalog_version']=c.config['version']
        return out

    def source_material(self,a):
        namespace=a.get('namespace','CAS')
        source_set=a.get('source_set','primary')
        if source_set not in ('primary','secondary','echa'):raise ValueError('Unsupported source material set')
        if namespace not in ('CAS','DTXSID','ECHA'):raise ValueError('Unsupported source material identifier')
        limit=None if a.get('limit')=='all' else max(1,int(a.get('limit',25)))
        with Catalog(self.path) as c:
            return c.source_material(namespace,a.get('identifier',''),max(0,int(a.get('offset',0))),limit,source_set)

    def detail(self,a):
        a=normalize_query(a)
        if a.get('_empty_filters'):raise ValueError('No records match the empty filter selection')
        kind=a.get('kind');key=a.get('id','');support=a.get('support','default')
        with Catalog(self.path) as c:
            if kind=='chemicals':
                result=c.query('chemicals',key,limit=200)
                exact=next((r for r in result['matches'] if str(r.get('source_id'))==key),None)
                if not exact and key.startswith('ECOTOX:'):
                    found=rows(c.fish,'SELECT * FROM chemicals WHERE chemical_id=?',[key])
                    exact=found[0] if found else None
                if not exact:
                    fish=rows(c.fish,'SELECT * FROM chemicals WHERE chemical_id=?',[key])
                    if fish:exact=fish[0];exact['source_id']=key;exact['name']=exact['preferred_name']
                exact=exact or (result['matches'][0] if result['matches'] else None)
                if exact is None:raise ValueError('Unknown compound')
                ids=c.identifiers(key)
                related=[r for r in result['matches'] if str(r.get('source_id'))!=key]
                if not exact.get('smiles'):
                    match=next((r for r in related if r.get('smiles')),None)
                    if match:exact={**match,**{k:v for k,v in exact.items() if v is not None}}
                counts={}
                for domain in NUMERIC[:-1]:
                    w,p=self.observation_where(c,{'kind':domain,'term':key,'support':support})
                    counts[domain]=c.observations.execute('SELECT count(*) FROM observations o WHERE '+w,p).fetchone()[0]
                cas=[v for ns,v in ids if ns=='CAS']
                if not exact.get('cas'):
                    same_structure=[r for r in related if r.get('cas') and r.get('inchikey') and r.get('inchikey')==exact.get('inchikey')]
                    preferred=sorted({r['cas'] for r in same_structure})
                    if len(preferred)==1:
                        exact['cas']=preferred[0];exact['cas_source']=[r['source_id'] for r in same_structure]
                    elif len(cas)==1:exact['cas']=cas[0]
                families=rows(c.fish,'SELECT DISTINCT cc.* FROM chemical_categories cc JOIN chemical_category_memberships m USING(category_id) JOIN chemical_identifiers i USING(chemical_id) WHERE i.identifier IN ('+','.join('?' for _ in cas)+')',cas) if cas else []
                return {'record':exact,'linked_identities':related,'identifiers':[{'namespace':n,'identifier':v} for n,v in sorted(ids)],'counts':counts,'families':families,'query':a}
            if kind in NUMERIC or kind=='observation':return {'record':c.query('observation',key),'query':a}
            if kind in ('genes','proteins'):
                rs=c.query(kind,key,a.get('species',''),support,50,0,a.get('assertion','any'))['matches'];r=next((r for r in rs if key in (r.get('gene_id'),r.get('protein_id'),r.get('accession'))),None)
                if r is None:raise ValueError('No record under the current support filter')
                return {'record':r,'pathways':c.entity_pathways(key,support,100,0),'query':a}
            if kind=='pathways':
                rs=c.query('pathways',key,a.get('species',''),support,100)['matches'];r=next((x for x in rs if x['pathway_id']==key),None)
                if r is None:raise ValueError('No pathway under the current filter')
                graph=c.fish.execute("SELECT 1 FROM pathway_graphs g JOIN pathway_annotations a ON g.reference_id='ko'||substr(a.reference_id,-5) WHERE a.pathway_id=?",[key]).fetchone()
                return {'record':r,'members':c.members(key,support,50,0),'reference_graph_available':bool(graph),'query':a}
            if kind=='sources':
                rs=rows(c.fish,'SELECT * FROM sources WHERE source_id=?',[key]);return {'record':rs[0] if rs else {},'query':a}
            if kind=='species':
                namespace=a.get('namespace')
                field='ncbi_taxid' if namespace=='NCBITaxID' else 'scientific_name' if namespace=='scientific_name' else 'taxon_id'
                rs=rows(c.fish,'SELECT * FROM taxa WHERE '+field+'=?',[key]);return {'record':rs[0] if rs else {},'query':a}
            if kind=='members':
                from network_queries import member_records,digest
                path=a.get('pathway_id');external=a.get('external_member_id') or key
                if not path or not external:raise ValueError('Pathway and external member identifiers are required')
                record=next(member_records(c,[path],support=support,external_member_id=external),None)
                if record is None:raise ValueError('No pathway member under the current filter')
                record['record_id']='pathway-membership:'+digest([path,external]);record['assertion_kind']='pathway_membership'
                record['source_member_links']=json.loads(record.pop('member_links_json','[]') or '[]')
                record['support_label']=LABELS.get(record['support_type'])
                return {'record':record,'query':a}
            if kind=='mechanisms':
                record=c.fish.execute('SELECT * FROM mechanism_evidence WHERE mechanism_id=?',[key]).fetchone()
                if record is None:raise ValueError('Unknown mechanism record')
                record=dict(record);rule=c.policy.get('mechanism_predicates',{}).get(record.get('predicate'),{})
                record['support_type']=rule.get('support_type','experimental' if record.get('evidence_kind')=='observed' else 'pending_verification')
                if record['support_type'] not in c.types('mechanisms',support):raise ValueError('No mechanism under the current filter')
                record['assertion_kind']=rule.get('assertion_kind','experimental_observation' if record.get('evidence_kind')=='observed' else 'inference_attribution_unverified')
                record['support_label']=LABELS.get(record['support_type']);record['record_id']=key
                return {'record':record,'query':a}
        raise ValueError('Unsupported detail kind')

    def network(self,a):
        from network_queries import build_network
        a=normalize_query(a)
        if a.get('_empty_filters'):
            return {'nodes':[],'edges':[],'records':[],'returned':0,'related_record_count':0,'has_more':False,'offset':int(a.get('offset',0)),'query':a,'scope_note':'当前筛选未选择任何条目。','relationship_kind':a.get('kind','toxicity')}
        return build_network(self,a)

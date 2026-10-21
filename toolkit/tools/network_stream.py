"""Incremental graph projection: small transport chunks, unrestricted scope."""
import hashlib
import json
from itertools import islice

from catalog_queries import Catalog, rows, filter_values, normalize_query
from network_queries import (Graph, NUMERIC, NETWORK_OBSERVATION_COLUMNS, digest,
                             member_records, source_observations, scope_observations)
from query_runtime import check_cancelled


def chunks(iterator, size=64):
    iterator = iter(iterator)
    while True:
        check_cancelled()
        block = list(islice(iterator, size))
        if not block:return
        yield block


def decorate_observations(catalog, records):
    names = {}
    for record in records:
        check_cancelled()
        record['identifiers'] = rows(catalog.observations,
            'SELECT namespace,identifier FROM identifiers WHERE record_id=? ORDER BY namespace,identifier',
            [record['record_id']])
        cas = tuple(i['identifier'] for i in record['identifiers'] if i['namespace']=='CAS')
        if cas:
            if cas not in names:
                found = rows(catalog.fish, '''SELECT DISTINCT preferred_name,name_zh FROM chemicals
                    JOIN chemical_identifiers USING(chemical_id) WHERE namespace='CAS'
                    AND identifier IN (SELECT value FROM json_each(?))''', [json.dumps(cas)])
                names[cas] = ' / '.join(sorted({r['name_zh'] or r['preferred_name'] for r in found})) or ', '.join(cas)
            record['chemical_name'] = names[cas]
        record['support_label'] = catalog.policy['labels'].get(record.get('support_type'))
        yield catalog.resolve_paths(record)


def activity_rows(catalog, args):
    directory = catalog.paths.get('bioactivity')
    if not directory or not (directory/'activities.json').exists():return
    metadata = json.loads((directory/'activities.json').read_text('utf-8'))
    term = args.get('term','')
    cids = [v for ns,v in catalog.identifiers(term) if ns=='PubChemCID'] if term else []
    if term and not cids:return
    buckets = {int(v)%metadata['cid_buckets'] for v in cids} if term and metadata.get('dataset') else None
    paths = sorted(p for p in (directory/'activities').glob('part-*/cid_bucket=*/*.parquet')
                   if buckets is None or int(p.parent.name.split('=')[1]) in buckets) if metadata.get('dataset') else [directory/'activities.parquet']
    types = catalog.types('bioactivity',args.get('support','default'))
    taxids = sorted({str(r['ncbi_taxid']) for r in catalog.species_records(args['species']) if r['ncbi_taxid'] is not None}) if args.get('species') else None
    # A separate cursor allows activity_records to consult assay metadata while
    # this sequential source scan remains open. No global sort or growing OFFSET.
    connection = catalog.d.cursor()
    runtime = catalog.query_runtime
    if runtime:runtime.register(connection)
    try:
        for path in paths:
            check_cancelled()
            fields = [r[0] for r in connection.execute('DESCRIBE SELECT * FROM read_parquet(?)',[str(path)]).fetchall()]
            projection = ','.join('"'+name.replace('"','""')+'" AS "'+name.replace(' ','').replace('"','""')+'"' for name in fields)
            sql = 'SELECT * FROM (SELECT '+projection+' FROM read_parquet(?)) WHERE support_type IN (SELECT unnest(?))'
            params = [str(path),types]
            if term:sql+=' AND CID IN (SELECT unnest(?))';params.append(cids)
            if taxids is not None:
                if not taxids:return
                sql+=' AND AID IN (SELECT AID FROM read_parquet(?) WHERE list_has_any(regexp_split_to_array(coalesce("Taxonomy IDs",\'\'),\'[^0-9]+\'),?))'
                params.extend([str(directory/'assays.parquet'),taxids])
            cursor = connection.execute(sql,params)
            names = [r[0] for r in cursor.description]
            while True:
                values = cursor.fetchmany(64)
                if not values:break
                for record in catalog.activity_records([dict(zip(names,value)) for value in values],metadata,directory):
                    check_cancelled()
                    record['support_label']=catalog.policy['labels'].get(record.get('support_type'))
                    yield catalog.resolve_paths(record)
    finally:
        if runtime:runtime.unregister(connection)
        connection.close()


def selected_rows(api, catalog, args):
    kind = args['kind']
    entity = args.get('entity_id')
    if args.get('_empty_filters'):return
    if entity:
        if kind in NUMERIC:
            record = catalog.query('observation',entity)
            if record.get('support_type') in catalog.types(kind,args.get('support','default')):
                if not entity.startswith('PubChemBioAssay:'):
                    yield from decorate_observations(catalog,[record])
                else:yield record
            return
        if kind in ('sources','species','pathways','genes','proteins'):
            table,key={'sources':('sources','source_id'),'species':('taxa','taxon_id'),
                       'pathways':('pathways','pathway_id'),'genes':('genes','gene_id'),
                       'proteins':('proteins','protein_id')}[kind]
            yield from rows(catalog.fish,'SELECT * FROM '+table+' WHERE '+key+'=?',[entity])
            return
    if kind in NUMERIC:
        where,parameters = api.observation_where(catalog,args)
        # This order follows observation_page; the source remains open across
        # transport chunks rather than re-reading and sorting each previous page.
        sql = 'SELECT '+NETWORK_OBSERVATION_COLUMNS+' FROM observations o WHERE '+where+' ORDER BY o.support_type,o.record_id'
        yield from decorate_observations(catalog,(dict(row) for row in catalog.observations.execute(sql,parameters)))
        if kind=='bioactivity':yield from activity_rows(catalog,args)
        return
    if kind in ('sources','species'):
        term=args.get('term','')
        if kind=='sources':
            sql='SELECT * FROM sources'+(' WHERE title LIKE ? OR doi LIKE ? OR pmid=?' if term else '')+' ORDER BY source_id'
            params=['%'+term+'%','%'+term+'%',term] if term else []
        else:
            sql='SELECT t.* FROM taxa t WHERE (scientific_name LIKE ? OR common_name LIKE ? OR CAST(ncbi_taxid AS TEXT)=?)'
            params=['%'+term+'%','%'+term+'%',term]
            extra,values=catalog.species(args.get('species'),'t');sql+=extra+' ORDER BY taxon_id';params.extend(values)
        for row in catalog.fish.execute(sql,params):check_cancelled();yield dict(row)
        return
    if kind=='endpoints':
        # Network nodes need the distinct metric names, not a fresh whole-store
        # COUNT plus all coverage metadata before the first node can be sent.
        sql='SELECT DISTINCT domain,property_name FROM observations INDEXED BY observation_filter WHERE property_name LIKE ?'
        for row in catalog.observations.execute(sql,['%'+args.get('term','')+'%']):
            check_cancelled();yield dict(row)
        return
    offset=0
    try:
        while True:
            check_cancelled()
            if kind in ('genes','proteins'):
                part=catalog.query(kind,args.get('term',''),args.get('species',''),args.get('support','default'),128,0,args.get('assertion','any'))
            else:part=api.search({**args,'limit':128,'offset':offset})
            selected=part.get('matches',[])
            yield from selected
            if not part.get('has_more') or not selected:return
            offset+=len(selected)
            if kind in ('genes','proteins'):catalog.stream_after_id=selected[-1]['gene_id' if kind=='genes' else 'protein_id']
    finally:
        catalog.stream_after_id=None


def directory_node(graph,kind,record):
    if kind=='sources':graph.node(record['source_id'],'study',record.get('title') or record['source_id'],record,'sources')
    elif kind=='species':
        key='taxon:'+str(record['ncbi_taxid']) if record.get('ncbi_taxid') else 'species:'+str(record['scientific_name'])
        graph.node(key,'organism',record['scientific_name'],record,'species')
    elif kind=='endpoints':graph.node('endpoint:'+digest([record['domain'],record['property_name']]),'endpoint',record['property_name'],record)
    elif kind in ('pathways','members'):graph.node(record['pathway_id'],'role',record.get('name') or record['pathway_id'],record,'pathways')
    elif kind in ('genes','proteins'):
        key=record['gene_id' if kind=='genes' else 'protein_id'];graph.node(key,'gene' if kind=='genes' else 'protein',record.get('name') or key,record,kind)


HEADER_FIELDS=('record_id','source_id','gene_id','protein_id','pathway_id','external_member_id',
               'mechanism_id','taxon_id','ncbi_taxid','domain','provider','support_type','support_label',
               'assertion_kind','source_url','name','preferred_name','name_zh','scientific_name',
               'property_name','reference','accession','source_measurement_id','linked_source_id')


def detail_reference(record, kind=None, key=None):
    if not isinstance(record,dict):record={}
    if record.get('domain') in NUMERIC and record.get('record_id'):
        return {'kind':record['domain'],'id':record['record_id']}
    if record.get('pathway_id') and record.get('external_member_id'):
        return {'kind':'members','id':record['external_member_id'],'pathway_id':record['pathway_id'],
                'external_member_id':record['external_member_id']}
    if record.get('mechanism_id'):return {'kind':'mechanisms','id':record['mechanism_id']}
    for field,collection in (('gene_id','genes'),('protein_id','proteins'),('pathway_id','pathways')):
        if record.get(field):return {'kind':collection,'id':record[field]}
    if record.get('source_id'):return {'kind':kind or 'chemicals','id':record['source_id']}
    if kind=='species' and record.get('taxon_id'):return {'kind':'species','id':record['taxon_id']}
    if kind=='organism' and key:
        if key.startswith('taxon:'):return {'kind':'species','id':key[6:],'namespace':'NCBITaxID'}
        if key.startswith('species:'):return {'kind':'species','id':key[8:],'namespace':'scientific_name'}
    return None


def header(record,kind=None,key=None):
    if not isinstance(record,dict):return record
    result={name:record[name] for name in HEADER_FIELDS if name in record}
    ref=detail_reference(record,kind,key)
    if ref:result['detail_ref']=ref
    return result


def compact(graph, selected, collection=None):
    lookup={}
    def reference(record):
        if not isinstance(record,dict) or not record.get('record_id'):return record,None
        key=record['record_id'];lookup[key]=header(record,collection)
        return {'record_id':key},key
    nodes=[];edges=[]
    for node in graph.nodes.values():
        row=dict(node);ref=detail_reference(row.get('record'),row.get('detail_kind') or row.get('kind'),row['id'])
        row['record'],key=reference(row.get('record'))
        if row.get('display_name')==row.get('label'):row.pop('display_name',None)
        if key:
            row['record_ref']=key;row.pop('record',None)
        else:row['record']=header(row.get('record'),row.get('detail_kind'),row['id'])
        if ref and not key:row['detail_ref']=ref
        nodes.append(row)
    for edge in graph.edges.values():
        row=dict(edge)
        ref=detail_reference(row.get('record'))
        row['record'],key=reference(row.get('record'))
        if key:
            row['record_ref']=key;row.pop('record',None);row.pop('source_url',None)
        else:row['record']=header(row.get('record'))
        if ref and not key:row['detail_ref']=ref
        edges.append(row)
    records=[]
    for record in selected:
        row,key=reference(record)
        records.append({**row,'record_ref':key} if key else header(row,collection))
    return {'nodes':nodes,'edges':edges,'records':records,'record_lookup':lookup,
            'related_record_count':len(graph.related_records)}


def iter_network(api, arguments):
    args=normalize_query(arguments)
    kinds=filter_values(args.pop('kinds',args.get('kind','chemicals')))
    cap=args.pop('take','all');cap=None if cap in ('all','unlimited','0','',None) else int(cap)
    if cap is not None and cap<1:raise ValueError('Record count must be positive, or all')
    total=0;related_total=0
    for selected_kind in kinds:
        if selected_kind not in (*NUMERIC,'chemicals','species','sources','endpoints','pathways','members','genes','proteins','mechanisms'):
            raise ValueError('Unknown collection')
        kind='toxicity' if selected_kind=='chemicals' else selected_kind
        q={**args,'kind':kind}
        if kind=='bioactivity':
            for field in ('family','endpoint','stage'):q.pop(field,None)
        if selected_kind=='chemicals' and q.get('entity_id'):q['term']=q.pop('entity_id')
        count=0
        scope={'chemicals':'毒性实验记录中的关系','sources':'通过来源编号关联的实验记录。',
               'species':'观察资料库中按原记录物种关联的实验资料。','endpoints':'观察资料库中按原记录指标关联的资料。',
               'pathways':'所选通路的全部已收录成员注释。','genes':'所选基因的已收录通路成员注释。',
               'proteins':'所选蛋白的已收录通路成员注释。'}.get(selected_kind,'当前资料记录中的关系。')

        def packet(graph, selected=(), complete=False):
            nonlocal total,count,related_total
            offset=count;count+=len(selected);total+=len(selected);related_total+=len(graph.related_records)
            batch={**compact(graph,selected,kind),'returned':len(selected),'offset':offset,'has_more':not complete,
                   'query':{**q,'relationship_kind':kind},'selected_collection':selected_kind,
                   'relationship_kind':kind,'scope_note':scope}
            return {'kind':selected_kind,'batch':batch,'loaded':total,'kind_loaded':count,
                    'related_loaded':related_total,'kind_complete':complete,'limited':False,'delta':True}

        yield {'type':'progress','phase':'querying','kind':selected_kind,'loaded':total,'related_loaded':related_total}
        more=False
        with Catalog(api.path) as catalog:
            selected_iterator=selected_rows(api,catalog,q)
            records=selected_iterator
            if cap is not None:records=islice(records,cap)
            all_directory=[]
            for block in chunks(records,32 if kind in NUMERIC else 8 if kind=='endpoints' else 128):
                graph=Graph()
                if kind in NUMERIC:
                    for record in block:graph.observation(record)
                    yield packet(graph,block)
                    continue
                if kind=='mechanisms':
                    for record in block:
                        record={**record,'record_id':record.get('record_id') or record.get('mechanism_id')}
                        source=graph.node(record.get('subject'),'mechanism',record.get('subject'))
                        target=graph.node(record.get('object'),'mechanism',record.get('object'))
                        graph.edge(source,target,record.get('predicate'),record,'mechanism_observation' if record.get('support_type')=='experimental' else 'source_interpretation')
                    yield packet(graph,block);continue
                for record in block:directory_node(graph,kind,record)
                yield packet(graph,block)
                if kind in ('sources','species','endpoints'):
                    all_directory.extend(block);continue
                if kind in ('pathways','members'):
                    paths=list(dict.fromkeys(r['pathway_id'] for r in block))
                    members=member_records(catalog,paths,support=q.get('support','default'))
                    if kind=='members':
                        keys={(r['pathway_id'],r['external_member_id']) for r in block}
                        members=(r for r in members if (r['pathway_id'],r['external_member_id']) in keys)
                else:
                    field='gene_id' if kind=='genes' else 'protein_id'
                    entities=[r[field] for r in block]
                    members=member_records(catalog,entity_ids=entities,support=q.get('support','default'))
                    table='lookup.entity_pathways' if catalog.has_lookup else 'pathway_member_links'
                    focuses={}
                    for link in rows(catalog.fish,'SELECT pathway_id,external_member_id,entity_id FROM '+table+' WHERE entity_id IN (SELECT value FROM json_each(?))',[json.dumps(entities)]):
                        focuses.setdefault((link['pathway_id'],link['external_member_id']),set()).add(link['entity_id'])
                for member_block in chunks(members):
                    graph=Graph()
                    for record in member_block:
                        if kind in ('genes','proteins'):
                            for focus in focuses.get((record['pathway_id'],record['external_member_id']),()):graph.member(record,focus,kind)
                        else:graph.member(record)
                    yield packet(graph)
            relations=()
            source_records={}
            if all_directory:
                if kind=='sources':
                    source_records={r['source_id']:r for r in all_directory}
                    relations=source_observations(catalog,list(source_records),q.get('support','default'),api,q,light=True)
                elif kind=='species':relations=scope_observations(catalog,api,q,taxa=all_directory,light=True)
                elif kind=='endpoints':relations=scope_observations(catalog,api,q,endpoints=all_directory,light=True)
            for block in chunks(relations,32):
                graph=Graph()
                for record in block:
                    observation=graph.observation(record)
                    if kind=='sources':
                        source=record['linked_source_id']
                        source_record=source_records.get(source,{'source_id':source})
                        graph.node(source,'study',source_record.get('title') or source,source_record,'sources')
                        graph.edge(source,observation,'来源中的实验记录',record,'source_measurement_foreign_key')
                yield packet(graph)
            if cap is not None and count>=cap:more=next(selected_iterator,None) is not None
            selected_iterator.close()
        final=packet(Graph(),complete=not more)
        final['limited']=more
        yield final

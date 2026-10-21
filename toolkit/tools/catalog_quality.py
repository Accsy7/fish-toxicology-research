"""Identity navigation, condition preservation and bounded retrieval diagnostics."""
import json, hashlib, re

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def has_table(c,name):return bool(c.execute('SELECT 1 FROM sqlite_master WHERE name=?',(name,)).fetchone())
def local_identifiers(c,term):
    if has_table(c.observations,'repair_identity_aliases'):
        rr=c.observations.execute('SELECT DISTINCT namespace,identifier FROM repair_identity_aliases WHERE alias=? COLLATE NOCASE',(term,)).fetchall()
        if rr:return {(r[0],r[1]) for r in rr}
    # Legacy catalog compatibility. Names/IDs are resolved even when the input is a CAS.
    rr=c.fish.execute('''SELECT ci.chemical_id,ci.namespace,ci.identifier FROM chemical_identifiers ci
    WHERE ci.chemical_id IN (SELECT chemical_id FROM chemicals WHERE preferred_name=? COLLATE NOCASE OR name_zh=? OR chemical_id=?
    UNION SELECT chemical_id FROM chemical_identifiers WHERE identifier=? COLLATE NOCASE)''',(term,term,term,term)).fetchall()
    out=set()
    for cid,ns,value in rr:
        out.add(('FishChemicalID',cid))
        if ns.lower() in ('cas','casrn') and re.fullmatch(r'\d{2,7}-\d{2}-\d',value):out.add(('CAS',value))
        elif ns.lower() in ('dtxsid','dsstox'):out.add(('DTXSID',value))
        elif ns.lower() in ('pubchem','pubchemcid','pubchem_cid'):out.add(('PubChemCID',value))
    return out

def attach_context(c,records):
    ids=[r['record_id'] for r in records if r.get('record_id')]
    if not ids:return records
    source={r['record_id']:dict(r) for r in c.observations.execute('SELECT record_id,source_key,raw_sha256 FROM observations WHERE record_id IN (SELECT value FROM json_each(?))',(json.dumps(ids),))}
    for r in records:
        if r.get('record_id') not in source:continue
        context=r.get('exposure_conditions')
        if isinstance(context,str):
            try:context=json.loads(context)
            except ValueError:context={'unparsed_original':context}
        context=context or {}
        r['experimental_context']=context
        s=source[r['record_id']]
        # Each source measurement remains a separate record. Same numeric values do not mean duplicates.
        evidence={'record_id':r['record_id'],'source_key':s['source_key'],'raw_sha256':s['raw_sha256'],
                  'conditions_sha256':digest(context),'source_reference':r.get('reference'),
                  'value':r.get('value'),'unit':r.get('unit'),'qualifier':r.get('qualifier'),
                  'endpoint':r.get('property_name'),'species':r.get('species'),'taxon_id':r.get('taxon_id'),
                  'identifiers':r.get('identifiers',[]),'conditions':context}
        r['evidence_binding']={'schema_version':'1.0','sha256':digest(evidence),'observation':evidence}
        r['condition_status']='source_fields_preserved' if 'source_links' in context else 'available_fields_only'
    return records

def diagnostics(c,out,kind,term,species,support,offset,source,endpoint):
    resolved=c.identifiers(term) if term else []
    taxa=c.species_records(species) if species else []
    reason='matches'
    if not out.get('returned',len(out.get('matches',[]))):
        reason='page_exhausted' if offset else 'no_matches_for_filters'
        if term and not resolved:reason='chemical_identity_unresolved'
        if species and not taxa and not str(species).isdigit():reason='species_not_resolved'
    counts=[]
    if has_table(c.observations,'repair_coverage'):
        names=[r['scientific_name'] for r in taxa]
        sql='SELECT domain,support_type,sum(record_count) AS record_count FROM repair_coverage'
        args=[]
        if species:
            sql+=' WHERE species IN (SELECT value FROM json_each(?)) OR CAST(taxon_id AS TEXT)=?';args=[json.dumps(names+[species]),str(species)]
        sql+=' GROUP BY domain,support_type'
        counts=[dict(r) for r in c.observations.execute(sql,args)]
    out['retrieval_diagnostics']={'status':reason,'query_scope':'catalog_snapshot_only','absence_in_literature_established':False,
        'requested':{'domain':kind,'term':term,'species':species,'support':support,'source':source,'endpoint':endpoint,'offset':offset},
        'resolved_identifiers':[{'namespace':n,'identifier':v} for n,v in resolved],
        'multiple_local_entities':len({v for n,v in resolved if n=='FishChemicalID'})>1,
        'resolved_species':taxa,'species_catalog_counts_before_chemical_and_endpoint_filters':counts,
        'identity_runtime':'local_and_parquet' if c.d else 'local_sqlite_only',
        'unavailable_identity_sources':[] if c.d else ['parquet_catalog'],
        'fallbacks':['query by source DOI with --source','query species without chemical/endpoint filters','source-record by observation ID'] if reason!='matches' else []}
    return out

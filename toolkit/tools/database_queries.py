"""Read-only, paginated access to the fish database. No scientific ranking rules."""
from pathlib import Path
import argparse,json,sqlite3,zlib

def rows(c,sql,args=()):return [dict(r) for r in c.execute(sql,args)]
def connect(path):
 c=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');return c
def taxa(c,species):
 if not species:return []
 return rows(c,'SELECT * FROM taxa WHERE scientific_name=? COLLATE NOCASE OR common_name=? OR CAST(ncbi_taxid AS TEXT)=?',(species,species,species))
def scope(c,species,alias):
 found=taxa(c,species)
 if not species:return '',[]
 if not found:return ' AND 0',[]
 distinct={r['ncbi_taxid'] for r in found if r['ncbi_taxid'] is not None}
 if len(distinct)>1:raise ValueError('该名称对应多个来源物种编号，请用 NCBI TaxID 查询：'+', '.join(map(str,sorted(distinct))))
 ids=[r['taxon_id'] for r in found]
 return f' AND {alias}.taxon_id IN ({",".join("?" for _ in ids)})',ids
def page(c,sql,args,limit,offset):
 limit=int(limit);offset=int(offset)
 if limit<1 or offset<0:raise ValueError('limit must be positive and offset non-negative')
 found=rows(c,sql+' LIMIT ? OFFSET ?',(*args,limit+1,offset))
 return {'matches':found[:limit],'returned':min(len(found),limit),'offset':offset,'has_more':len(found)>limit}
def molecular(c,kind,term='',species='',limit=100,offset=0):
 extra,params=scope(c,species,'m');word='%'+term+'%'
 if kind=='genes':
  sql='''SELECT m.*,t.scientific_name,t.ncbi_taxid,a.ncbi_geneid,a.synonyms,a.chromosome,a.modified_date FROM genes m JOIN taxa t USING(taxon_id) LEFT JOIN gene_annotations a USING(gene_id) WHERE (m.name LIKE ? OR m.description LIKE ? OR m.gene_id=? OR a.synonyms LIKE ? OR a.ncbi_geneid=?)'''+extra+' ORDER BY m.gene_id'
  args=[word,word,term,word,term,*params]
 else:
  sql='''SELECT m.*,t.scientific_name,t.ncbi_taxid,a.accession,a.reviewed,a.protein_existence,a.annotation_score,a.go_ids,a.gene_ids,a.source_release FROM proteins m JOIN taxa t USING(taxon_id) LEFT JOIN protein_annotations a USING(protein_id) WHERE (m.gene_label LIKE ? OR m.name LIKE ? OR m.protein_id=? OR a.accession=?)'''+extra+' ORDER BY m.protein_id'
  args=[word,word,term,term,*params]
 return page(c,sql,args,limit,offset)
def pathways(c,term='',species='',limit=100,offset=0):
 extra,params=scope(c,species,'a');word='%'+term+'%'
 sql='''SELECT p.*,a.provider,a.provider_id,a.reference_id,a.ncbi_taxid,a.annotation_type,a.source_url,t.scientific_name FROM pathways p LEFT JOIN pathway_annotations a USING(pathway_id) LEFT JOIN taxa t USING(taxon_id) WHERE (p.name LIKE ? OR p.pathway_id LIKE ?)'''+extra+' ORDER BY p.pathway_id'
 return page(c,sql,[word,word,*params],limit,offset)
def members(c,pathway,limit=100,offset=0):
 sql='''SELECT p.pathway_id,p.external_member_id,p.gene_id,g.name AS gene_symbol,g.description AS gene_description,t.scientific_name,t.ncbi_taxid,
 (SELECT group_concat(l.entity_id,';') FROM pathway_member_links l WHERE l.pathway_id=p.pathway_id AND l.external_member_id=p.external_member_id AND l.entity_type='protein') AS protein_ids
 FROM pathway_source_members p JOIN taxa t USING(taxon_id) LEFT JOIN genes g USING(gene_id) WHERE p.pathway_id=? ORDER BY p.external_member_id'''
 out=page(c,sql,[pathway],limit,offset)
 out['total_members']=c.execute('SELECT count(*) FROM pathway_source_members WHERE pathway_id=?',(pathway,)).fetchone()[0];return out
def source_record(c,key,kind='protein'):
 prefix='UniProt:' if kind=='protein' else 'NCBIGene:'
 eid=key if ':' in key else prefix+key
 result=c.execute('SELECT * FROM molecular_records WHERE entity_type=? AND entity_id=?',(kind,eid)).fetchone()
 if not result:raise ValueError('No imported source row for '+eid)
 r=dict(result);line=zlib.decompress(r.pop('row_zlib')).decode('utf-8');header=json.loads(c.execute('SELECT columns_json FROM bulk_headers WHERE provider=?',(r['provider'],)).fetchone()[0]);r['record']=dict(zip(header,line.split('\t')))
 r['source_asset']=dict(c.execute('SELECT * FROM source_assets WHERE asset_id=?',(r['asset_id'],)).fetchone());return r
def chemical_ids(c,term):
 if not term:return []
 return [r[0] for r in c.execute('''SELECT chemical_id FROM chemicals WHERE preferred_name LIKE ? OR name_zh LIKE ? OR chemical_id=? UNION SELECT chemical_id FROM chemical_identifiers WHERE identifier=? COLLATE NOCASE''',('%'+term+'%','%'+term+'%',term,term))]
def toxicity(c,term='',species='',limit=100,offset=0):
 extra,params=scope(c,species,'b');ids=chemical_ids(c,term)
 if term and not ids:return {'matches':[],'returned':0,'offset':offset,'has_more':False}
 if ids:
  extra+=' AND g.sample_id IN (SELECT sample_id FROM sample_components WHERE chemical_id IN ('+','.join('?' for _ in ids)+'))';params.extend(ids)
 sql='''SELECT m.measurement_id,m.value_kind,m.value,m.value_text,m.value_operator,m.unit,m.time_value,m.time_unit,m.effect_status,m.significance,m.record_layer,m.locator,m.review_status,m.raw_id,e.label AS endpoint,e.domain,e.anatomical_site,t.scientific_name,t.ncbi_taxid,b.life_stage,s.doi,s.title,s.url,g.source_group_key,sa.sample_name,sa.reagent_cas,x.medium,x.duration_value,x.duration_unit,x.dose_basis
 FROM measurements m JOIN endpoints e USING(endpoint_id) JOIN experimental_groups g USING(group_id) JOIN biological_materials b USING(material_id) JOIN taxa t USING(taxon_id) JOIN sources s USING(source_id) LEFT JOIN samples sa USING(sample_id) LEFT JOIN exposures x ON x.exposure_id=m.exposure_id WHERE 1=1'''+extra
 return page(c,sql,params,limit,offset)
def coverage(c):
 row=c.execute("SELECT value FROM metadata WHERE key='coverage_json'").fetchone()
 if row:return json.loads(row[0])
 return {'database_version':'building','counts':{t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['chemicals','measurements','genes','proteins','pathways']}}
def graph(c,pathway):
 p=c.execute('SELECT * FROM pathway_annotations WHERE pathway_id=?',(pathway,)).fetchone()
 if not p or p['provider']!='KEGG':raise ValueError('No KEGG reference graph for '+pathway)
 reference='ko'+p['reference_id'][-5:]
 row=c.execute('SELECT * FROM pathway_graphs WHERE reference_id=?',(reference,)).fetchone()
 if not row:raise ValueError('Reference graph unavailable: '+reference)
 return {**dict(row),'species_pathway_id':pathway,'ncbi_taxid':p['ncbi_taxid'],'gene_orthologs':rows(c,'SELECT k.external_gene_id,k.ko_id FROM kegg_gene_orthologs k JOIN pathway_source_members p ON p.external_member_id=k.external_gene_id AND p.taxon_id=k.taxon_id WHERE p.pathway_id=?',(pathway,))}
def query(c,kind,term='',species='',limit=100,offset=0):
 if kind=='coverage':return coverage(c)
 if kind in ('genes','proteins'):return molecular(c,kind,term,species,limit,offset)
 if kind=='pathways':return pathways(c,term,species,limit,offset)
 if kind=='members':return members(c,term,limit,offset)
 if kind=='graph':return graph(c,term)
 if kind=='raw-record':
  r=c.execute('SELECT * FROM raw_records WHERE raw_id=?',(term,)).fetchone()
  if not r:raise ValueError('Source row unavailable: '+term)
  out=dict(r);out['record']=json.loads(out.pop('row_json'));return out
 if kind=='toxicity':return toxicity(c,term,species,limit,offset)
 if kind in ('sequence','protein-record','gene-record'):
  out=source_record(c,term,'gene' if kind=='gene-record' else 'protein')
  if kind=='sequence':return {'accession':out['external_id'],'sequence':out['record']['Sequence'],'length':int(out['record']['Length']),'species':out['record']['Organism'],'source_release':out['source_asset']['batch_id']}
  return out
 raise ValueError('Unknown query kind '+kind)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True);p.add_argument('kind',choices=['coverage','genes','proteins','pathways','members','graph','toxicity','sequence','protein-record','gene-record','raw-record']);p.add_argument('term',nargs='?',default='');p.add_argument('--species',default='');p.add_argument('--limit',type=int,default=100);p.add_argument('--offset',type=int,default=0);p.add_argument('--output',type=Path)
 a=p.parse_args()
 with connect(a.database) as c:result=query(c,a.kind,a.term,a.species,a.limit,a.offset)
 text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text,'utf-8')
 else:print(text)
if __name__=='__main__':main()

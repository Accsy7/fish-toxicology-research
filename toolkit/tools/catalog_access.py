"""Project binding for the classified data catalog."""
from pathlib import Path
import sys,json,hashlib,datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor/catalog-runtime'))
from catalog_queries import Catalog

def open_catalog(root,config):
 path=(config.get('database') or {}).get('catalog')
 if not path:raise ValueError('该项目未绑定分类资料目录。')
 return Catalog((Path(root)/path).resolve())

def extract_catalog(root,config,terms,output,include_history=False,support='default'):
 output=Path(output).resolve()
 if output.exists():raise ValueError('提取目录已存在，请另存一版。')
 packets=[]
 with open_catalog(root,config) as c:
  c.observations.execute('BEGIN');c.fish.execute('BEGIN');c.go.execute('BEGIN')
  for term in terms:
   packet={'query':term,'identity':c.query('chemicals',term,limit=500),'datasets':{}}
   for kind in ('properties','environment','bioactivity','toxicity'):
    records=[];offset=0
    while True:
     page=c.query(kind,term,support=support,limit=500,offset=offset);records.extend(page['matches'])
     if not page['has_more']:break
     offset+=500
    packet['datasets'][kind]={'applied_support_filter':page['applied_support_filter'],'retrieval_diagnostics':page.get('retrieval_diagnostics'),'records':records,'record_grain':'source observation; conditions and evidence_binding retained'}
   packets.append(packet)
  catalog_version=c.config['version'];policy=c.policy
 output.mkdir(parents=True);files={}
 for i,packet in enumerate(packets,1):
  path=output/f'chemical-{i:03d}.json';path.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n','utf-8');files[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
 manifest={'catalog_version':catalog_version,'query':terms,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'support_policy':policy,'files':files,'historical_predictions_included':False}
 if include_history:
  # Existing historical extraction retains the original project scope and sources.
  import research
  con,_,_=research.connect(root)
  try:
   hist={}
   for term in terms:
    try:cid=research.resolve(con,term)
    except ValueError:continue
    hist[cid]=research.evidence(con,cid,True).get('historical_predictions_not_current',[])
   (output/'history.json').write_text(json.dumps(hist,ensure_ascii=False,indent=2),'utf-8');manifest['historical_predictions_included']=True
  finally:con.close()
 (output/'evidence_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
 return {'output':str(output),'chemicals':len(packets),'catalog_version':catalog_version,'files':files,'support_filter':support}

"""Copy query evidence into an analysis input fragment without retyping conditions."""
from pathlib import Path
import argparse,json,os
from quality_contract import packet_observations,file_sha,load,digest

def from_extraction(extraction,output):
    """Wrap actual paper extraction with its source file; does not read or interpret the paper."""
    extraction=Path(extraction).resolve();output=Path(output).resolve();data=load(extraction)
    if output.exists():raise ValueError('Output exists; use a new version')
    bound=[];ids=set()
    for row in data.get('observations',[]):
        row=dict(row);material=dict(row.get('source_material',{}));p=(extraction.parent/str(material.get('path',''))).resolve()
        if not row.get('record_id') or row['record_id'] in ids:raise ValueError('Unique observation IDs required')
        ids.add(row['record_id'])
        if not material.get('locator') or file_sha(p)!=material.get('sha256'):raise ValueError('Original file hash and exact source locator required')
        if not row.get('source_reference') or not isinstance(row.get('conditions'),dict):raise ValueError('Source reference and structured conditions required')
        if not all(k in row for k in ('species','endpoint','value','unit','qualifier')):raise ValueError('Explicit experimental fields required; unknown values may be null')
        material['path']=os.path.relpath(p,output.parent);row['source_material']=material
        row['extraction_method']='model_or_human_source_extraction_not_program_inference'
        bound.append({'evidence_binding':{'schema_version':'1.0','sha256':digest(row),'observation':row}})
    if not bound:raise ValueError('No source observations supplied')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps({'matches':bound,'source_extraction':True},ensure_ascii=False,indent=2)+'\n','utf-8')
    return {'output':str(output),'source_observations':len(bound),'scientific_review_performed':False}

def create(packets,output):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Output exists; preserve the previous evidence contract')
    inputs=[];records=[];seen={}
    for n,p in enumerate(packets,1):
        p=Path(p).resolve();key=f'I{n}'
        inputs.append({'id':key,'path':os.path.relpath(p,output.parent),'sha256':file_sha(p)})
        for rid,obs in packet_observations(load(p)).items():
            if rid in seen:
                if seen[rid]!=obs:raise ValueError('Conflicting copies of '+rid)
                continue
            seen[rid]=obs
            records.append({'id':f'EV{len(records)+1}','input_id':key,'record_id':rid,'observation':obs})
    if not records:raise ValueError('No source-bound observation was found; do not fabricate evidence')
    fragment={'evidence_inputs':inputs,'evidence_records':records,'scientific_judgments_created':False}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(fragment,ensure_ascii=False,indent=2)+'\n','utf-8')
    return {'output':str(output),'source_observations':len(records),'scientific_judgments_created':False}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--packet',type=Path,action='append');g.add_argument('--extraction',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(from_extraction(a.extraction,a.output) if a.extraction else create(a.packet,a.output),ensure_ascii=False))

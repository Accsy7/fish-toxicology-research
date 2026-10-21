"""Validate inspectable evidence/conditions/completion claims, never infer scientific merit."""
from pathlib import Path
import hashlib,json,copy

def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def file_sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text('utf-8-sig'))
def resolve(data,path):
    if not isinstance(path,str) or not path.startswith('/'):raise ValueError('Use an analysis JSON pointer')
    value=data
    for key in path[1:].split('/'):
        key=key.replace('~1','/').replace('~0','~')
        if isinstance(value,list):
            items=[x for x in value if isinstance(x,dict) and x.get('id')==key]
            value=items[0] if len(items)==1 else value[int(key)]
        else:value=value[key]
    return value

def review_errors(record):
    errors=[]
    if record.get('review_mode') not in ('self_review','independent_ai','independent_human'):
        errors.append('REVIEW_MODE_REQUIRED: identify self-review or actual independent reviewer')
    if record.get('open_blockers')!=[]:errors.append('OPEN_REVIEW_BLOCKERS')
    bad={'not_accepted','rejected','changes_requested','blocked','failed'}
    for key in ('external_review_outcome','independent_review_outcome'):
        item=record.get(key)
        if isinstance(item,dict):item=item.get('status',item.get('decision'))
        if item in bad:errors.append('UNACCEPTED_EXTERNAL_REVIEW: '+key)
    for f in record.get('findings',[]):
        if not isinstance(f,dict) or not all(f.get(k) for k in ('id','severity','status','basis')):
            errors.append('STRUCTURED_REVIEW_FINDING_REQUIRED');continue
        if f['status'] not in ('resolved','open','not_applicable'):errors.append('UNKNOWN_FINDING_STATUS: '+f['id'])
        if f['severity'] in ('blocking','major') and f['status']=='open':errors.append('UNRESOLVED_MAJOR_FINDING: '+f['id'])
        if f['status']=='resolved' and not f.get('resolution'):errors.append('FINDING_RESOLUTION_REQUIRED: '+f['id'])
    return errors

def packet_observations(value):
    """Find structured source bindings in either one query response or an extraction packet."""
    found={}
    def visit(v):
        if isinstance(v,dict):
            binding=v.get('evidence_binding')
            if binding:
                obs=binding.get('observation',{})
                if binding.get('sha256')!=digest(obs):raise ValueError('Source packet evidence hash mismatch')
                rid=obs.get('record_id')
                if not rid:raise ValueError('Source observation ID missing')
                if rid in found and found[rid]!=obs:raise ValueError('Conflicting source observation '+rid)
                found[rid]=obs
            for k,x in v.items():
                if k!='evidence_binding':visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(value);return found

def validate_analysis(data,base,project=None,required=True):
    """The contract is mandatory for new reviewed delivery; old analyses remain readable."""
    errors=[];base=Path(base)
    contract=data.get('research_completion')
    if not contract:
        return ['RESEARCH_COMPLETION_REQUIRED: new reviewed delivery needs explicit complete/partial scope'] if required else []
    if contract.get('schema_version')!='1.0':errors.append('UNKNOWN_RESEARCH_COMPLETION_SCHEMA')
    status=contract.get('objective_status')
    if status not in ('complete','partial'):errors.append('OBJECTIVE_STATUS_REQUIRED')
    if not contract.get('research_question') or not contract.get('comparison_conditions'):errors.append('RESEARCH_CONTEXT_REQUIRED')
    if project:
        if contract.get('research_question')!=project.get('research_question'):errors.append('RESEARCH_QUESTION_MISMATCH')
        if contract.get('comparison_conditions')!=project.get('comparison_conditions'):errors.append('COMPARISON_CONDITIONS_MISMATCH')
    inputs={};evidence={};record_keys=set()
    for inp in data.get('evidence_inputs',[]):
        key=inp.get('id');p=base/str(inp.get('path',''))
        if not key or key in inputs:errors.append('DUPLICATE_EVIDENCE_INPUT');continue
        try:
            if file_sha(p)!=inp.get('sha256'):raise ValueError('Input file changed')
            inputs[key]=packet_observations(load(p))
            for obs in inputs[key].values():
                material=obs.get('source_material')
                if material:
                    if not material.get('locator') or file_sha(p.parent/material['path'])!=material.get('sha256'):
                        raise ValueError('Original source material or locator differs')
        except (OSError,ValueError,TypeError,KeyError) as exc:errors.append('INVALID_EVIDENCE_INPUT: '+str(key)+': '+str(exc))
    for item in data.get('evidence_records',[]):
        key=item.get('id');pair=(item.get('input_id'),item.get('record_id'))
        if not key or key in evidence or pair in record_keys:errors.append('DUPLICATE_EVIDENCE_RECORD: '+str(key));continue
        source=inputs.get(pair[0],{}).get(pair[1]);actual=item.get('observation')
        if not source or source!=actual:errors.append('SOURCE_CONDITIONS_OR_VALUE_CHANGED: '+str(key))
        evidence[key]=actual or {};record_keys.add(pair)
    for e in data.get('experiments',[]):
        ids=e.get('evidence_ids',[])
        if not ids or any(i not in evidence for i in ids):errors.append('EXPERIMENT_EVIDENCE_REQUIRED: '+str(e.get('id')));continue
        if len(ids)!=1 and e.get('record_kind')!='source_summary':errors.append('EXPERIMENT_GRAIN_MERGED: '+str(e.get('id')))
        if e.get('record_kind')=='source_summary':
            variants=[{'evidence_id':i,'endpoint':evidence[i].get('endpoint'),'conditions':evidence[i].get('conditions')} for i in ids]
            if e.get('condition_variants')!=variants:errors.append('SUMMARY_CONDITION_VARIANTS_REQUIRED: '+str(e.get('id')))
        # Rendering uses the complete source context; prose cannot silently erase it.
        expected=[evidence[i].get('conditions') for i in ids]
        if e.get('preserved_conditions')!=expected:errors.append('EXPERIMENT_CONDITIONS_DROPPED: '+str(e.get('id')))
        if len(e.get('chemical_ids',[]))>1 and len(ids)==1:
            if expected[0].get('identity_attribution')!='mixture_or_formulation':errors.append('MULTI_CHEMICAL_SINGLE_OBSERVATION: '+str(e.get('id')))
    default_fields=['species','endpoint','conditions.source_links.study_id','conditions.duration_value','conditions.duration_unit','conditions.time_value','conditions.time_unit','conditions.time_basis','conditions.dose_basis','conditions.medium','conditions.source_group_key']
    def field(obj,path):
        for k in path.split('.'):
            if not isinstance(obj,dict):return None
            obj=obj.get(k)
        return obj
    for comp in data.get('comparisons',[]):
        if comp.get('type') not in ('same_condition_potency','same_system_dose_response'):continue
        ids=comp.get('evidence_ids',[])
        if len(ids)<2 or any(i not in evidence for i in ids):errors.append('COMPARISON_EVIDENCE_REQUIRED: '+str(comp.get('id')));continue
        for f in set(default_fields)|set(comp.get('matching_fields',[])):
            # Different treatment groups are necessary for dose/compound comparisons. Their control/study identity is required instead.
            if f=='conditions.source_group_key':f='conditions.control_group_id'
            values=[field(evidence[i],f) for i in ids]
            unavailable=all(v in (None,'') for v in values)
            if unavailable:
                notes=comp.get('unknown_conditions',{})
                if not notes.get(f):errors.append('COMPARISON_CONDITION_UNCONFIRMED: '+str(comp.get('id'))+': '+f)
            elif any(v in (None,'') for v in values) or any(v!=values[0] for v in values[1:]):errors.append('COMPARISON_CONDITION_DIFFERS: '+str(comp.get('id'))+': '+f)
        if comp.get('unknown_conditions') and comp.get('equivalence')=='confirmed':errors.append('UNKNOWN_CONDITIONS_CANNOT_CONFIRM_EQUIVALENCE: '+str(comp.get('id')))
    candidates={c.get('id') for c in data.get('chemicals',[])}
    if project and candidates!=set(project.get('scope',{}).get('candidates',[])):errors.append('CANDIDATE_SCOPE_MISMATCH')
    judged=set()
    for j in contract.get('candidate_judgments',[]):
        cid=j.get('chemical_id')
        if cid in judged or cid not in candidates:errors.append('INVALID_JUDGMENT_SCOPE: '+str(cid))
        judged.add(cid)
        for f in ('prediction_ref','basis_ref','counterevidence_ref'):
            try:
                if not resolve(data,j.get(f)):raise ValueError('Empty referenced judgment')
            except (ValueError,KeyError,IndexError,TypeError):errors.append('JUDGMENT_CONTENT_MISSING: '+str(cid)+': '+f)
    if judged!=candidates:errors.append('JUDGMENTS_DO_NOT_COVER_CANDIDATES')
    covered=set();informative=0
    for relation in contract.get('risk_relations',[]):
        members=relation.get('members',[]);rel=relation.get('relation')
        if len(set(members))<2 or not set(members)<=candidates:errors.append('INVALID_RISK_COMPARISON_SCOPE')
        if rel not in ('higher','lower','indistinguishable_under_conditions','unresolved'):errors.append('RISK_RELATION_REQUIRED')
        if rel!='unresolved':
            informative+=1;covered.update(members)
        if relation.get('purpose')!='relative_target_endpoint_risk' or not relation.get('conditions') or not relation.get('target_endpoint'):errors.append('RISK_SCOPE_REQUIRED: experiment priority is not risk order')
        for f in ('judgment_ref','basis_ref'):
            try:
                if not resolve(data,relation.get(f)):raise ValueError('Empty comparison')
            except (ValueError,KeyError,IndexError,TypeError):errors.append('RISK_COMPARISON_CONTENT_MISSING: '+f)
    if status=='complete' and len(candidates)>1 and (not informative or covered!=candidates):errors.append('RELATIVE_RISK_OBJECTIVE_INCOMPLETE')
    if status=='partial' and not contract.get('unresolved_impact'):errors.append('PARTIAL_RESULT_IMPACT_REQUIRED')
    return errors

def assert_analysis(data,base,project=None):
    errors=validate_analysis(data,base,project)
    if errors:raise ValueError('\n'.join(errors))

def presentation_data(data):
    """Pure formatting of bound fields, shared by XLSX and HTML; no new inference."""
    out=copy.deepcopy(data)
    evidence={r['id']:r.get('observation',{}) for r in out.get('evidence_records',[])}
    def value(v):return canonical(v) if isinstance(v,(dict,list)) else str(v)
    def units(c,k,u):
        return None if c.get(k) is None else str(c[k])+(' '+str(c[u]) if c.get(u) else '')
    for e in out.get('experiments',[]):
        contexts=[];results=[]
        for eid in e.get('evidence_ids',[]):
            obs=evidence.get(eid,{})
            if not obs:continue
            c=obs.get('conditions',{});bits=[]
            pairs=[('暴露浓度',units(c,'concentration_value','concentration_unit')),('浓度限定',c.get('concentration_operator')),
                ('暴露时长',units(c,'duration_value','duration_unit')),('测量时间',units(c,'time_value','time_unit')),
                ('时间口径',c.get('time_basis')),('剂量口径',c.get('dose_basis')),('物种',obs.get('species')),
                ('阶段',c.get('life_stage')),('品系',c.get('strain')),('性别',c.get('sex')),('介质',c.get('medium')),
                ('起点',units(c,'start_value','start_unit')),('终点',units(c,'end_value','end_unit')),
                ('对照组',c.get('control_group_id')),('试剂形态',c.get('formulation')),('来源位置',c.get('locator'))]
            for label,v in pairs:
                if v not in (None,''):bits.append(label+'：'+value(v))
            contexts.append(eid+' · '+'；'.join(bits))
            rr=[]
            for label,v in [('终点',obs.get('endpoint')),('原始值',str(obs.get('value'))+' '+str(obs.get('unit') or '') if obs.get('value') is not None else None),
                            ('结果限定',obs.get('qualifier')),('对照值',c.get('control_value')),('误差类型',c.get('error_type')),
                            ('统计显著性',c.get('significance')),('效应标记',c.get('effect_status'))]:
                if v not in (None,''):rr.append(label+'：'+value(v))
            if c.get('significance') in (None,''):rr.append('统计显著性：该字段未提供')
            results.append(eid+' · '+'；'.join(rr))
        for key,extra in [('condition',contexts),('result',results)]:
            if extra:
                original=e.get(key,'');e[key]=str(original or '')+'\n'+'\n'.join(extra)
    return out

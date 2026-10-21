"""Check explicit completion dependencies; never grant scientific validity or wet-lab approval."""
from pathlib import Path
import argparse, json, hashlib, sys
script=Path(__file__).resolve()
tool_candidates=[script.parents[2]/'tools']+[p/'.fish-toxicology/tools' for p in script.parents]+[Path.cwd()/'.fish-toxicology/tools']
tool_home=next((p for p in tool_candidates if (p/'quality_contract.py').is_file()),None)
if tool_home is None:raise SystemExit('缺少同版本工具目录，请从完整工作包安装后运行完成检查。')
sys.path.insert(0,str(tool_home))
from quality_contract import validate_analysis, review_errors
from analysis_checks import materialize

def check(project, record, root):
    errors=[]
    def fail(code, detail): errors.append({'code':code,'detail':detail})
    def exists(value): return isinstance(value,str) and bool(value.strip()) and (root/value).is_file()
    def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    analysis={}
    if record.get('schema_version')!='2.0.0':fail('COMPLETION_SCHEMA_REQUIRED','旧完成记录保留；新交付需 2.0.0 的研究目标状态与来源条件核验。')
    binding=record.get('analysis',{})
    if exists(binding.get('path')):
        p=root/binding['path']
        try: analysis=json.loads(p.read_text('utf-8-sig'))
        except (ValueError,OSError): fail('INVALID_ANALYSIS','正式分析需要可读取的 JSON')
        if binding.get('sha256')!=sha(p): fail('ANALYSIS_CHANGED','正式分析与本次完成记录不一致')
    else: fail('MISSING_ANALYSIS_BINDING','完成记录需指向本次正式分析并记录 sha256')
    publication=hashlib.sha256(json.dumps(analysis,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def review_file(entry,kind,check_name=None):
        if not exists(entry.get('record_file')): return
        p=root/entry['record_file']
        try: actual=json.loads(p.read_text('utf-8-sig'))
        except (ValueError,OSError): fail('UNREADABLE_REVIEW',str(p));return
        if entry.get('sha256')!=sha(p): fail('REVIEW_CHANGED',str(p))
        expected={'record_type':kind,'project_id':analysis.get('project_id'),'analysis_version':analysis.get('analysis_version'),'publication_sha256':publication}
        for key,value in expected.items():
            if value is None or actual.get(key)!=value: fail('UNBOUND_REVIEW',f'{p.name}: {key}')
        if not actual.get('reviewer') or not actual.get('findings'): fail('EMPTY_REVIEW',p.name)
        if kind=='publication_review':
            for error in review_errors(actual):fail('REVIEW_CONTENT_CONFLICT',error)
            if actual.get('decision') not in ('accepted','accepted_with_stated_limits'): fail('UNACCEPTED_REVIEW',p.name)
            if set(actual.get('chemical_ids',[]))!={c['id'] for c in analysis.get('chemicals',[])}: fail('REVIEW_COVERAGE_MISMATCH',p.name)
            if entry.get('reviewer')!=actual.get('reviewer'): fail('REVIEWER_MISMATCH',p.name)
        if check_name and check_name not in actual.get('checks',[]): fail('CHECK_NOT_RECORDED',check_name)
    if project.get('status')!='configured':fail('PROJECT_NOT_CONFIGURED','研究问题与范围尚未固定')
    if not project.get('research_question') or not project.get('comparison_conditions'):
        fail('MISSING_RESEARCH_CONTEXT','问题和比较条件必须明确；未知参数可单列')
    analysis_base=(root/binding['path']).parent if binding.get('path') else root
    try:
        for error in validate_analysis(materialize(analysis),analysis_base,project):fail('SCIENTIFIC_DELIVERY_CONTRACT',error)
    except (ValueError,KeyError,TypeError,IndexError) as exc:fail('INVALID_ANALYSIS_REFERENCE',str(exc))
    objective=analysis.get('research_completion',{}).get('objective_status')
    if record.get('objective_status')!=objective:fail('OBJECTIVE_STATUS_MISMATCH','完成记录与正式分析中的 complete/partial 状态不同')
    expected=project.get('scope',{})
    if not expected.get('candidates'):fail('EMPTY_CANDIDATE_SCOPE','不能把空白课题标为完成')
    rows=record.get('scope_dispositions',[])
    keys=[(r.get('category'),r.get('id')) for r in rows]
    if len(set(keys))!=len(keys):fail('DUPLICATE_SCOPE_REVIEW','同一范围记录重复')
    wanted={(category,i) for category,ids in expected.items() for i in ids}
    if set(keys)!=wanted:fail('INCOMPLETE_SCOPE',str(sorted(wanted-set(keys)))+' / unexpected '+str(sorted(set(keys)-wanted)))
    for r in rows:
        key=str((r.get('category'),r.get('id')));status=r.get('status')
        if status not in ['completed','blocked_after_attempt','not_applicable']:
            fail('UNFINISHED_ANALYSIS',key);continue
        if not r.get('contribution'):fail('NO_ANALYSIS_CONTRIBUTION',key)
        files=r.get('evidence_files',[])
        if not files or not all(exists(f) for f in files):fail('MISSING_EXECUTION_OR_SOURCE_RECORD',key)
        if status=='blocked_after_attempt' and not all(r.get(k) for k in ['attempted','obstacle','alternative','impact']):
            fail('UNEXPLAINED_BLOCK',key)
        if status=='not_applicable' and not all(r.get(k) for k in ['reason','alternative','impact']):
            fail('UNEXPLAINED_INAPPLICABILITY',key)
        if r.get('category')=='candidates' and status!='completed' and objective=='complete':
            fail('CANDIDATE_JUDGMENT_UNFINISHED',key+'；受阻方法不免除条件判断或并列')
    for key in ['candidate_predictions','risk_order_or_groups','representative_decisions','unresolved_items_and_impacts']:
        output=record.get('scientific_outputs',{}).get(key)
        if not exists(output):fail('MISSING_SCIENTIFIC_OUTPUT',key)
        elif binding.get('path') and (root/output).resolve()!=(root/binding['path']).resolve():
            fail('UNBOUND_SCIENTIFIC_OUTPUT',key+'；新完成记录的科学内容指向同一正式分析，不能用无关文件占位。')
    review=record.get('content_review',{})
    review_file(review,'publication_review')
    if review.get('status')!='reviewed_with_stated_limits' or not review.get('reviewer') or not exists(review.get('record_file')):
        fail('MISSING_CONTENT_REVIEW','实际身份、范围与审核文件不可由导出器生成')
    for category,ids in expected.items():
        if set(review.get('coverage',{}).get(category,[]))!=set(ids):fail('INCOMPLETE_REVIEW_SCOPE',category)
    if record.get('blocking_errors'):fail('OPEN_BLOCKING_ERRORS',str(record['blocking_errors']))
    for key in ['explicit_contradictions','negative_delivery_cases','expression_and_falsification','final_artifact_reading']:
        c=record.get('checks',{}).get(key,{})
        if c.get('status')!='passed' or not exists(c.get('record_file')):fail('UNVERIFIED_DELIVERY',key)
        review_file(c,'validation_record',key)
    unconfirmed=[x.get('name') for x in record.get('experimental_parameters',[]) if x.get('status')!='confirmed']
    return {'status':'rejected' if errors else ('partial_delivery_checks_passed' if objective=='partial' else 'explicit_checks_passed'), 'errors':errors,
            'objective_status':objective,'completion_claim_consistent_with_bound_records':not errors,
            'scientific_review_performed_by_program':False,'experiment_execution_authorized':False,
            'unconfirmed_experimental_parameters':unconfirmed,
            'meaning':'核对来源条件、比较口径、目标状态和实际审核记录的一致性；不替代科学复核，也不把未知操作参数变成已确认。'}

def main():
    p=argparse.ArgumentParser();p.add_argument('project',type=Path);p.add_argument('record',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args();load=lambda f:json.loads(f.read_text('utf-8-sig'))
    result=check(load(a.project),load(a.record),a.record.resolve().parent)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(bool(result['errors']))
if __name__=='__main__':main()

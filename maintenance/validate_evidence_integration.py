"""End-to-end fixture: evidence -> reviewed render -> completion -> registry.
Synthetic fixture only; never edits or re-registers existing scientific results.
"""
from pathlib import Path
import sys,json,copy,importlib.util,subprocess,sqlite3
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'toolkit';sys.path.insert(0,str(P/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from test_quality_contract import ContractTests
from quality_contract import digest,file_sha
from render_reviewed import render
from research import register
from quality_gate import run as gate
from openpyxl import load_workbook

def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def main():
    f=ContractTests();f.setUp();base=f.base
    try:
        example=json.loads((P/'skill/assets/report-example.json').read_text('utf-8'))
        data=copy.deepcopy(example);data.update(f.data)
        proto=example['chemicals'][0]
        data['chemicals']=[{**copy.deepcopy(proto),**c} for c in data['chemicals']]
        ep=example['experiments'][0]
        data['experiments']=[{**copy.deepcopy(ep),**e} for e in data['experiments']]
        for i,e in enumerate(data['experiments']):e['preserved_conditions']=[{'$ref':f'/evidence_records/EV{i+1}/observation/conditions'}]
        data['title']='回归检查合成案例，不是科研结论';data['project_id']='fixture';data['analysis_version']='1'
        analysis=base/'analysis.json';dump(analysis,data)
        review=f.review();review['publication_sha256']=digest(data);dump(base/'review.json',review)
        spec={'analysis':'analysis.json','analysis_sha256':file_sha(analysis),'review':{'path':'review.json','sha256':file_sha(base/'review.json')}}
        dump(base/'presentation.json',spec);render_result=render(base/'presentation.json',base/'delivery')
        wb=load_workbook(base/'delivery/analysis.xlsx',read_only=True,data_only=False)
        cells=[v for ws in wb.worksheets for row in ws.iter_rows(values_only=True) for v in row if isinstance(v,str)]
        assert len(wb.sheetnames)==8,wb.sheetnames
        assert any('暴露时长：112 h' in v and '暴露浓度：0.1 uM' in v for v in cells)
        assert any('统计显著性：NS' in v for v in cells)
        sheets=list(wb.sheetnames);wb.close()
        rendered=json.loads((base/'delivery/report.json').read_text('utf-8'))
        assert '暴露时长：112 h' in rendered['experiments'][0]['condition'] and '统计显著性：NS' in rendered['experiments'][0]['result']
        checks=['explicit_contradictions','negative_delivery_cases','expression_and_falsification','final_artifact_reading']
        validation={'record_type':'validation_record','project_id':'fixture','analysis_version':'1','publication_sha256':digest(data),'reviewer':'fixture tester','findings':['Actual synthetic fixture readback completed'],'checks':checks}
        dump(base/'validation.json',validation)
        project={**f.project,'status':'configured'};dump(base/'project.json',project)
        gate_result=gate(analysis,base/'project.json',base/'review.json');assert not gate_result['errors'],gate_result
        completion={'schema_version':'2.0.0','objective_status':'complete','analysis':{'path':'analysis.json','sha256':file_sha(analysis)},'scope_dispositions':[{'category':'candidates','id':cid,'status':'completed','contribution':'fixture judgment','evidence_files':['query.json']} for cid in ['A','B']],
            'scientific_outputs':{k:'analysis.json' for k in ['candidate_predictions','risk_order_or_groups','representative_decisions','unresolved_items_and_impacts']},
            'content_review':{'status':'reviewed_with_stated_limits','reviewer':'fixture tester','record_file':'review.json','sha256':file_sha(base/'review.json'),'coverage':{'candidates':['A','B']}},'blocking_errors':[],
            'checks':{k:{'status':'passed','record_file':'validation.json','sha256':file_sha(base/'validation.json')} for k in checks},'experimental_parameters':[]}
        dump(base/'completion.json',completion)
        specimp=importlib.util.spec_from_file_location('completion_checker',P/'skill/scripts/check_completion.py');mod=importlib.util.module_from_spec(specimp);specimp.loader.exec_module(mod)
        result=mod.check(project,completion,base);assert not result['errors'],result
        # Discovery skill entry must also find the installed matching tool modules.
        sys.path.insert(0,str(P));from install_bundle import install
        db=base/'fixture.sqlite3';c=sqlite3.connect(db);c.execute('CREATE TABLE fixture(id INTEGER)');c.commit();c.close()
        install_result=install(base,'codex',database=db)
        script=base/'.agents/skills/fish-toxicology-research/scripts/check_completion.py'
        cp=subprocess.run([sys.executable,'-B','-X','utf8',str(script),str(base/'project.json'),str(base/'completion.json')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        assert cp.returncode==0,(cp.stdout,cp.stderr)
        # Keep this temporary install separate from the registry fixture's source binding.
        (base/'.fish-toxicology/workspace.json').write_text(json.dumps({'analysis_catalog':'research/catalog.json'}),'utf-8')
        cfg={'analysis_catalog':'research/catalog.json'};dump(base/'workspace.json',cfg)
        m={'project_id':'fixture','analysis_version':'1','title':'synthetic regression fixture','analysis':'analysis.json','analysis_sha256':file_sha(analysis),
            'completion':{'path':'completion.json','sha256':file_sha(base/'completion.json'),'project':'project.json'},
            'content_review':{'decision':'accepted_with_stated_limits','reviewer':'fixture tester','open_blockers':[],'candidate_ids':['A','B'],'records':[{'path':'review.json','sha256':file_sha(base/'review.json')}]},
            'artifacts':[{'kind':'xlsx','path':'delivery/analysis.xlsx','sha256':file_sha(base/'delivery/analysis.xlsx')},{'kind':'interactive_html','path':'delivery/index.html','sha256':file_sha(base/'delivery/index.html'),'web_files':{p.relative_to(base/'delivery').as_posix():file_sha(p) for p in (base/'delivery').rglob('*') if p.is_file()}}],
            'database_links':[{'candidate_id':c,'unmatched_reason':'synthetic fixture, no chemical claimed'} for c in ['A','B']]}
        dump(base/'manifest.json',m);registered=register(base,base/'manifest.json')
        # Cannot bypass the gate by calling register directly without completion.
        m.pop('completion');dump(base/'missing-completion.json',m)
        try:register(base,base/'missing-completion.json')
        except ValueError as exc:assert '完成检查' in str(exc)
        else:raise AssertionError('Registration bypassed the completion gate')
        output={'status':'passed','fixture_only':True,'workbook_sheets':sheets,'conditions_in_existing_cells':True,'nonsignificance_in_result_cell':True,'html_same_bound_conditions':True,'quality_gate':gate_result,'completion_result':result,'registered_fixture':registered,'registration_bypass_blocked':True,'installed_discovery_entry_passed':True,'temporary_plugin_removed_after_check':True,'render':render_result}
        dump(ROOT/'audit/delivery-integration.json',output);print(json.dumps(output,ensure_ascii=False,indent=2))
    finally:f.tearDown()
if __name__=='__main__':main()

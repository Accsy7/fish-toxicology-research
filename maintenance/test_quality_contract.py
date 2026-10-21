"""Negative regression fixtures, not research results or new scientific conclusions."""
from pathlib import Path
import sys,unittest,copy,json,tempfile,importlib.util
ROOT=Path(__file__).resolve().parents[1];TOOLS=ROOT/'toolkit/tools';sys.path.insert(0,str(TOOLS))
from quality_contract import digest,file_sha,validate_analysis,review_errors
from render_reviewed import check_review
from evidence_contract import create,from_extraction

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.project={'research_question':'fixture relative risk','comparison_conditions':'fixture matched conditions','scope':{'candidates':['A','B']}}
        cond={'source_links':{'study_id':'study1'},'duration_value':112,'duration_unit':'h','time_value':112,'time_unit':'h','time_basis':'exposure_duration','dose_basis':'nominal','medium':'freshwater','control_group_id':'control1','significance':'NS','concentration_value':0.1,'concentration_unit':'uM'}
        obs=[]
        for cid in ['A','B']:
            o={'record_id':'fixture:'+cid,'source_key':cid,'raw_sha256':'0'*64,'source_reference':'fixture-only','species':'fixture species','endpoint':'skeletal morphology','conditions':copy.deepcopy(cond),'value':1,'unit':'%','qualifier':None}
            obs.append({'evidence_binding':{'sha256':digest(o),'observation':o}})
        packet=self.base/'query.json';packet.write_text(json.dumps({'matches':obs}),'utf-8')
        out=self.base/'evidence.json';create([packet],out);fragment=json.loads(out.read_text('utf-8'))
        self.data={**fragment,'project_id':'fixture','analysis_version':'1','chemicals':[{'id':c,'prediction':'fixture-only','basis':'fixture-only','doubt':'fixture uncertainty'} for c in ['A','B']],
            'experiments':[{'id':'E'+str(i+1),'chemical_ids':[c],'evidence_ids':['EV'+str(i+1)],'preserved_conditions':[copy.deepcopy(cond)]} for i,c in enumerate(['A','B'])],
            'comparisons':[{'id':'C1','type':'same_condition_potency','evidence_ids':['EV1','EV2'],'equivalence':'confirmed'}],
            'research_completion':{'schema_version':'1.0','objective_status':'complete',**{k:self.project[k] for k in ('research_question','comparison_conditions')},'candidate_judgments':[{'chemical_id':c,'prediction_ref':'/chemicals/'+c+'/prediction','basis_ref':'/chemicals/'+c+'/basis','counterevidence_ref':'/chemicals/'+c+'/doubt'} for c in ['A','B']],
            'risk_relations':[{'members':['A','B'],'relation':'indistinguishable_under_conditions','purpose':'relative_target_endpoint_risk','conditions':'fixture matched conditions','target_endpoint':'fixture skeleton','judgment_ref':'/chemicals/A/prediction','basis_ref':'/chemicals/A/basis'}]}}
    def tearDown(self):self.temp.cleanup()
    def errors(self):return validate_analysis(self.data,self.base,self.project)
    def test_complete_consistent_fixture(self):self.assertEqual(self.errors(),[])
    def test_condition_value_rewrite_rejected(self):
        self.data['evidence_records'][0]['observation']['conditions']['concentration_value']=1
        self.assertTrue(any('SOURCE_CONDITIONS_OR_VALUE_CHANGED' in x for x in self.errors()))
    def test_nonsignificance_removed_rejected(self):
        self.data['experiments'][0]['preserved_conditions'][0].pop('significance')
        self.assertTrue(any('EXPERIMENT_CONDITIONS_DROPPED' in x for x in self.errors()))
    def test_join_fanout_rejected(self):
        item=copy.deepcopy(self.data['evidence_records'][0]);item['id']='EV3';self.data['evidence_records'].append(item)
        self.assertTrue(any('DUPLICATE_EVIDENCE_RECORD' in x for x in self.errors()))
    def test_multi_substance_single_observation_rejected(self):
        self.data['experiments'][0]['chemical_ids']=['A','B']
        self.assertTrue(any('MULTI_CHEMICAL_SINGLE_OBSERVATION' in x for x in self.errors()))
    def test_summary_cannot_hide_condition_variants(self):
        e=self.data['experiments'][0];e.update(record_kind='source_summary',evidence_ids=['EV1','EV2'],condition_variants=[{'note':'combined'}])
        self.assertTrue(any('SUMMARY_CONDITION_VARIANTS_REQUIRED' in x for x in self.errors()))
    def test_manual_paper_source_remains_usable(self):
        source=self.base/'source.txt';source.write_text('Synthetic primary-source fixture: raw area lower; normalized area NS.','utf-8')
        obs=copy.deepcopy(self.data['evidence_records'][0]['observation']);obs['source_material']={'path':'source.txt','sha256':file_sha(source),'locator':'fixture paragraph 1'}
        inp=self.base/'manual.json';inp.write_text(json.dumps({'observations':[obs]}),'utf-8')
        wrapped=self.base/'manual-packet.json';from_extraction(inp,wrapped)
        fragment=self.base/'manual-contract.json';create([wrapped],fragment)
        parsed=json.loads(fragment.read_text('utf-8'));self.assertEqual(parsed['evidence_records'][0]['observation']['conditions']['significance'],'NS')
        self.data.update(parsed);self.data['experiments']=self.data['experiments'][:1];self.data['comparisons']=[]
        self.assertEqual(self.errors(),[])
        source.write_text('changed','utf-8')
        self.assertTrue(any('INVALID_EVIDENCE_INPUT' in x for x in self.errors()))
    def test_different_duration_cannot_be_same_conditions(self):
        # Rewrite the packet as a different real experimental condition, with all hashes valid.
        p=self.base/'query.json';q=json.loads(p.read_text('utf-8'));q['matches'][1]['evidence_binding']['observation']['conditions']['duration_value']=96
        q['matches'][1]['evidence_binding']['sha256']=digest(q['matches'][1]['evidence_binding']['observation']);p.write_text(json.dumps(q),'utf-8')
        self.data['evidence_inputs'][0]['sha256']=file_sha(p)
        self.data['evidence_records'][1]['observation']=copy.deepcopy(q['matches'][1]['evidence_binding']['observation'])
        self.data['experiments'][1]['preserved_conditions']=[copy.deepcopy(q['matches'][1]['evidence_binding']['observation']['conditions'])]
        self.assertTrue(any('COMPARISON_CONDITION_DIFFERS' in x for x in self.errors()))
    def test_unknowns_cannot_be_marked_complete(self):
        self.data['research_completion']['risk_relations'][0]['relation']='unresolved'
        self.assertIn('RELATIVE_RISK_OBJECTIVE_INCOMPLETE',self.errors())
    def test_partial_is_allowed_without_fabricating_order(self):
        c=self.data['research_completion'];c['objective_status']='partial';c['risk_relations'][0]['relation']='unresolved';c['unresolved_impact']='Fixture: relative order remains unestablished'
        self.assertEqual(self.errors(),[])
    def test_experiment_priority_cannot_replace_risk(self):
        self.data['research_completion']['risk_relations'][0]['purpose']='experiment_priority'
        self.assertTrue(any('RISK_SCOPE_REQUIRED' in x for x in self.errors()))
    def test_cross_topic_completion_rejected(self):
        self.project['research_question']='a different study'
        self.assertIn('RESEARCH_QUESTION_MISMATCH',self.errors())
    def test_changed_packet_rejected(self):
        (self.base/'query.json').write_text('{}','utf-8')
        self.assertTrue(any('INVALID_EVIDENCE_INPUT' in x for x in self.errors()))
    def test_legacy_completion_not_silently_promoted(self):
        self.data.pop('research_completion')
        self.assertTrue(any('RESEARCH_COMPLETION_REQUIRED' in x for x in self.errors()))
    def review(self):return {'record_type':'publication_review','project_id':'fixture','analysis_version':'1','publication_sha256':digest(self.data),'reviewer':'fixture tester','review_mode':'self_review','decision':'accepted_with_stated_limits','open_blockers':[],'chemical_ids':['A','B'],'findings':[{'id':'F1','severity':'minor','status':'open','basis':'fixture limitation'}]}
    def test_self_review_explicitly_allowed(self):self.assertEqual(review_errors(self.review()),[])
    def test_unresolved_major_finding_rejected(self):
        r=self.review();r['findings'][0]['severity']='major';self.assertTrue(review_errors(r))
    def test_external_rejection_cannot_be_overridden(self):
        r=self.review();r['external_review_outcome']='not_accepted';self.assertTrue(any('UNACCEPTED_EXTERNAL_REVIEW' in e for e in review_errors(r)))
        p=self.base/'review.json';p.write_text(json.dumps(r),'utf-8')
        with self.assertRaises(ValueError):check_review({'path':p.name,'sha256':file_sha(p)},self.data,self.base)

if __name__=='__main__':unittest.main(verbosity=2)

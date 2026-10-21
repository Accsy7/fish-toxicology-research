"""One explicit gate for source-bound portable analyses; not a scientific reviewer."""
from pathlib import Path
import argparse,json
from analysis_checks import materialize,check
from quality_contract import load,validate_analysis
from render_reviewed import check_review

def run(analysis,project=None,review=None):
    path=Path(analysis).resolve();raw=load(path);data=materialize(raw)
    errors=check(data)+validate_analysis(data,path.parent,load(project) if project else None)
    if review:
        from quality_contract import file_sha
        p=Path(review).resolve()
        try:check_review({'path':str(p),'sha256':file_sha(p)},raw,path.parent)
        except (ValueError,OSError,KeyError) as exc:errors.append(str(exc))
    return {'status':'rejected' if errors else 'explicit_checks_passed','errors':errors,
            'objective_status':data.get('research_completion',{}).get('objective_status'),
            'project_binding_checked':bool(project),'review_record_checked':bool(review),
            'scientific_review_performed_by_program':False}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('analysis',type=Path);p.add_argument('--project',type=Path);p.add_argument('--review',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args();result=run(a.analysis,a.project,a.review)
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:a.output.write_text(text,'utf-8')
    print(text);raise SystemExit(bool(result['errors']))

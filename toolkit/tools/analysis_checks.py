"""Optional checks for explicitly recorded identities, comparisons and calculations."""
import argparse
import json
import math
from pathlib import Path


def resolve(data, path):
    value=data
    for key in path.strip('/').split('/'):
        key=key.replace('~1','/').replace('~0','~')
        if isinstance(value,list):
            matches=[x for x in value if isinstance(x,dict) and x.get('id')==key]
            value=matches[0] if len(matches)==1 else value[int(key)]
        else: value=value[key]
    return value


def materialize(data):
    """References keep derived text tied to its owning record; cycles are errors."""
    def visit(value,seen=()):
        if isinstance(value,dict) and set(value)=={'$ref'}:
            ref=value['$ref']
            if ref in seen: raise ValueError('Cyclic report reference: '+ref)
            return visit(resolve(data,ref),seen+(ref,))
        if isinstance(value,dict): return {k:visit(v,seen) for k,v in value.items()}
        if isinstance(value,list): return [visit(v,seen) for v in value]
        return value
    return visit(data)


def check(data, taxon_lookup=None):
    errors=[]
    for item in data.get('identities',[]):
        expected=item.get('reference')
        if taxon_lookup:
            matches=taxon_lookup(item['scientific_name'])
            if matches and not any(str(x['ncbi_taxid'])==str(item['taxid']) for x in matches):
                errors.append('identity '+item['id']+': species name and taxid differ from database')
        if expected and (item['scientific_name'].casefold()!=expected['scientific_name'].casefold() or str(item['taxid'])!=str(expected['taxid'])):
            errors.append('identity '+item['id']+': name/taxid differs from reference')
    for c in data.get('comparisons',[]):
        if c.get('type')!='same_system_dose_response': continue
        records=[resolve(data,'experiments/'+rid) for rid in c['experiment_ids']]
        fields=c.get('matching_fields',['object','endpoint','duration','protocol'])
        for f in fields:
            values=[r.get(f) for r in records]
            if any(v in (None,'') for v in values): errors.append(c['id']+': comparison field missing: '+f)
            elif any(v!=values[0] for v in values[1:]): errors.append(c['id']+': dose-only comparison changes '+f)
    operations={'sum':sum,'mean':lambda a:sum(a)/len(a),
                'geometric_mean':lambda a:math.exp(sum(math.log(v) for v in a)/len(a)),
                'ratio':lambda a:a[0]/a[1], 'product':math.prod}
    for c in data.get('numeric_checks',[]):
        if c['operation'] not in operations: raise ValueError('Unknown check operation: '+c['operation'])
        inputs=[resolve(data,v['$ref']) if isinstance(v,dict) else v for v in c['inputs']]
        observed=resolve(data,c['result_ref'])
        expected=operations[c['operation']](inputs)
        if not math.isfinite(observed) or not math.isclose(observed,expected,rel_tol=c.get('rtol',1e-6),abs_tol=c.get('atol',1e-12)):
            errors.append(f"{c['id']}: result {observed} differs from calculated {expected}")
    scope=data.get('expected_chemical_ids')
    if scope is not None:
        actual={c['id'] for c in data['chemicals']}
        if actual!=set(scope): errors.append('Chemical scope differs: '+str(sorted(actual.symmetric_difference(scope))))
    return errors


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('analysis',type=Path);p.add_argument('--workspace',type=Path)
    a=p.parse_args();data=json.loads(a.analysis.read_text('utf-8-sig'));connection=None
    try:
        lookup=None
        if a.workspace:
            from research import connect,rows
            connection,_,_=connect(a.workspace)
            lookup=lambda name:rows(connection,'SELECT * FROM taxa WHERE lower(scientific_name)=lower(?)',(name,))
        resolved=materialize(data)
        issues=check(resolved,lookup)
        from quality_contract import validate_analysis
        issues+=validate_analysis(resolved,a.analysis.resolve().parent)
        print(json.dumps({'errors':issues,'checks':'declared identity, comparison, numeric and scope checks'},ensure_ascii=False,indent=2))
        raise SystemExit(bool(issues))
    finally:
        if connection: connection.close()

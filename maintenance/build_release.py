"""Build software-only portable artifacts from this source tree and pure Python dependencies."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.5.1-rc.1'
NAME = 'fish-toxicology-research'
SKIP = {'.git', '__pycache__', 'audit', 'vendor', '.venv', '.fish-toxicology'}
FORBIDDEN = {'.sqlite', '.sqlite3', '.duckdb', '.parquet', '.pyd', '.dll'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', 'utf-8', newline='\n')


def manifest(toolkit, include_vendor):
    dependency = json.loads((toolkit/'data-components.json').read_text('utf-8'))
    result = {'schema_version': '1.0', 'version': VERSION,
              'components': {'skill': VERSION, 'tools': VERSION},
              'external_components': {'data': dependency['data'], 'frontend': dependency['frontend']},
              'files': {}}
    folders = ['skill', 'tools'] + (['vendor'] if include_vendor else [])
    for folder in folders:
        for path in sorted((toolkit/folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                result['files'][path.relative_to(toolkit).as_posix()] = sha(path)
    for name in ['install.py', 'install_bundle.py', 'INSTALL.md', 'data-components.json']:
        result['files'][name] = sha(toolkit/name)
    for path in sorted(toolkit.glob('requirements*.txt')):
        result['files'][path.name] = sha(path)
    dump(toolkit/'bundle.json', result)
    return result


def zip_tree(root, path, prefix):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for source in sorted(root.rglob('*')):
            if not source.is_file() or '__pycache__' in source.parts or source.suffix == '.pyc':
                continue
            if source.suffix.lower() in FORBIDDEN or 'database_frontend' in source.parts:
                raise ValueError('Forbidden software-package component: '+str(source))
            info = zipfile.ZipInfo(prefix+'/'+source.relative_to(root).as_posix(), (2026,10,21,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError('ZIP CRC failure: '+str(path))


def copy_source(target):
    if target.exists():
        raise ValueError('Use a new build directory: '+str(target))
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if not path.is_file() or any(part in SKIP for part in rel.parts) or path.suffix == '.pyc':
            continue
        destination = target/rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def build(output, vendor_source=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest(ROOT/'toolkit', False)
    import package_skills
    package_skills.build(ROOT)
    source = output/(NAME+'-source-'+VERSION)
    copy_source(source)
    software = output/(NAME+'-'+VERSION)
    shutil.copytree(source, software)
    if vendor_source:
        vendor_source = Path(vendor_source).resolve()
        for name in ['python', 'licenses']:
            if not (vendor_source/name).is_dir():
                raise ValueError('Missing pure Python dependency input: '+name)
            shutil.copytree(vendor_source/name, software/'toolkit/vendor'/name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    else:
        raise ValueError('The portable release requires the licensed pure Python Excel dependencies.')
    # Check the actual dependency versions; compiled catalog dependencies are deliberately absent.
    openpyxl = software/'toolkit/vendor/python/openpyxl/_constants.py'
    if "3.1.5" not in openpyxl.read_text('utf-8'):
        raise ValueError('Unexpected openpyxl version')
    manifest(software/'toolkit', True)
    files = []
    for kind, directory in [('software', software), ('source', source)]:
        path = output/(NAME+'-'+kind+'-'+VERSION+'.zip')
        zip_tree(directory, path, directory.name)
        files.append(path)
    for client in ['claude', 'workbuddy']:
        path = output/(NAME+'-'+client+'-'+VERSION+'.zip')
        shutil.copy2(ROOT/'adapters'/client/(NAME+'.zip'), path)
        files.append(path)
    path = output/'data-components.json'
    shutil.copy2(ROOT/'toolkit/data-components.json', path)
    files.append(path)
    sums = output/'SHA256SUMS.txt'
    sums.write_text(''.join(sha(path)+'  '+path.name+'\n' for path in files), 'utf-8', newline='\n')
    files.append(sums)
    receipt = {'version': VERSION, 'release_type': 'prerelease', 'sqlite_included': False,
               'database_frontend_included': False,
               'artifacts': [{'name':path.name,'bytes':path.stat().st_size,'sha256':sha(path)} for path in files],
               'scientific_validation_performed': False}
    dump(output/'build-receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--vendor-source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.vendor_source), ensure_ascii=False, indent=2))

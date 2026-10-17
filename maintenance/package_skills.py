"""Create client upload archives from the same scientific workflow."""
from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'fish-toxicology-research'
EXCLUDED = {'approved-workbook-example.xlsx', 'accepted-preview.png'}


def build(root=ROOT):
    skill = root / 'toolkit/skill'
    text = (skill / 'SKILL.md').read_text('utf-8-sig')
    header, body = text.split('---', 2)[1:]
    description = next(line.split(':', 1)[1].strip() for line in header.splitlines()
                       if line.startswith('description:'))
    version = next(line.split(':', 1)[1].strip() for line in header.splitlines()
                   if line.strip().startswith('version:'))
    buddy_header = '\n'.join([
        'name: ' + NAME, 'description: ' + json.dumps(description, ensure_ascii=False),
        'description_zh: ' + json.dumps(description, ensure_ascii=False),
        'description_en: "Fish toxicology research, candidate comparison and experiment selection."',
        'version: ' + json.dumps(version), 'author: "Fish toxicology research toolkit"'])
    result = []
    for client in ('claude', 'workbuddy'):
        output = root / 'adapters' / client / (NAME + '.zip')
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted(skill.rglob('*')):
                if not p.is_file() or p.name in EXCLUDED or '__pycache__' in p.parts or p.suffix == '.pyc':
                    continue
                data = p.read_bytes()
                if p.name == 'SKILL.md':
                    data = text.encode('utf8')
                if p.name == 'SKILL.md' and client == 'workbuddy':
                    data = ('---\n' + buddy_header + '\n---' + body).encode('utf8')
                info = zipfile.ZipInfo(NAME + '/' + p.relative_to(skill).as_posix(), (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        with zipfile.ZipFile(output) as z:
            if z.testzip(): raise ValueError('Archive check failed: ' + str(output))
        result.append(str(output))
    return result


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))

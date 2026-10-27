"""Vendor text only from a pinned Agency Agents archive; never execute its tools."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'workflows/agency-agents'
CATEGORIES = dict(academic='دانشگاهی', design='طراحی و تجربهٔ کاربری', engineering='مهندسی نرم‌افزار',
    finance='مالی', **{'game-development': 'توسعهٔ بازی', 'gis': 'اطلاعات مکانی',
    'healthcare': 'سلامت', 'marketing': 'بازاریابی', 'paid-media': 'رسانه و تبلیغات',
    'product': 'محصول', 'project-management': 'مدیریت پروژه', 'research': 'پژوهش',
    'sales': 'فروش', 'security': 'امنیت', 'spatial-computing': 'رایانش فضایی',
    'specialized': 'تخصصی', 'support': 'پشتیبانی', 'testing': 'آزمون و کیفیت'})
RECOMMENDED = {
    'product/product-manager.md': ('ایجنت تحلیل محصول', 'شفاف‌سازی نیازمندی، پرسش‌های تکمیلی و پیش‌نویس PRD'),
    'product/product-sprint-prioritizer.md': ('ایجنت اولویت‌بندی بک‌لاگ', 'پیشنهاد اولویت، وابستگی‌ها و برنامهٔ انجام'),
    'engineering/engineering-software-architect.md': ('ایجنت معماری فنی', 'طراحی راهکار و بررسی وابستگی‌ها و تصمیم‌های فنی'),
    'engineering/engineering-minimal-change-engineer.md': ('ایجنت پیاده‌سازی محدود', 'انجام تسک با تغییرات متمرکز و کنترل محدوده'),
    'engineering/engineering-code-reviewer.md': ('ایجنت بازبینی کد', 'گزارش ایرادهای کد و پیشنهاد اصلاح برای تصمیم TL'),
    'testing/testing-api-tester.md': ('ایجنت بررسی API', 'طراحی و بررسی سناریوهای آزمون API'),
    'testing/testing-test-automation-engineer.md': ('ایجنت طراحی تست و رگرسیون', 'پیشنهاد تست‌های متناسب با نیازمندی و اثرات جانبی'),
    'testing/testing-reality-checker.md': ('ایجنت بررسی شواهد پذیرش', 'مقایسهٔ نیازمندی و شواهد واقعی برای تصمیم مسئول پذیرش'),
}


def generate(archive, commit):
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('A commit SHA is required, not a moving branch')
    files = {}
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            if not member.isfile():
                continue
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or len(path.parts) < 2:
                raise ValueError('Invalid archive path')
            if path.parts[0] != 'agency-agents-' + commit:
                raise ValueError('Archive does not match the pinned commit')
            relative = '/'.join(path.parts[1:])
            if not (relative.endswith('.md') or relative in ('LICENSE', 'divisions.json')):
                continue
            if member.size > 1048576 or relative in files:
                raise ValueError('Invalid text file')
            content = source.extractfile(member).read()
            content.decode('utf-8')
            files[relative] = content
    divisions = json.loads(files['divisions.json'])['divisions']
    entries = []
    for path, raw in sorted(files.items()):
        category = path.split('/')[0]
        if category not in divisions or not path.endswith('.md'):
            continue
        text = raw.decode('utf-8')
        if not text.startswith('---\n'):
            raise ValueError(f'Missing agent metadata: {path}')
        frontmatter = yaml.safe_load(text.split('---', 2)[1])
        if not isinstance(frontmatter, dict) or not all(isinstance(frontmatter.get(k), str) and frontmatter[k].strip() for k in ('name', 'description')):
            raise ValueError(f'Invalid agent metadata: {path}')
        original_name = frontmatter['name'].strip()
        name, description = RECOMMENDED.get(path, ('ایجنت ' + original_name, frontmatter['description'].strip()))
        identity = re.sub('[^a-z0-9-]', '-', Path(path).stem.lower())[:100] + '-' + hashlib.sha256(path.encode()).hexdigest()[:8]
        entries.append(dict(id=identity, path=path, name=name[:120], original_name=original_name,
            description=description[:2000], original_description=frontmatter['description'].strip(),
            category=category, category_label=CATEGORIES.get(category, divisions[category]['label']),
            category_original_label=divisions[category]['label'],
            recommended=path in RECOMMENDED, sha256=hashlib.sha256(raw).hexdigest()))
    if not entries or set(RECOMMENDED) - {entry['path'] for entry in entries}:
        raise ValueError('Recommended catalog entries missing')
    destination = DEST / 'upstream'
    destination.mkdir(parents=True, exist_ok=True)
    existing = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    if existing - files.keys():
        raise ValueError('Old snapshot files exist; review the version change explicitly')
    for path, content in files.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    manifest = dict(schema_version=1, repository='https://github.com/msitarzewski/agency-agents', commit=commit,
        license='MIT', files={p: dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest()) for p, b in sorted(files.items())},
        templates=entries)
    (DEST / 'catalog.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(commit=commit, agents=len(entries), documents=sum(p.endswith('.md') for p in files),
        bytes=sum(map(len, files.values())), categories=len(divisions))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    generate(args.archive, args.commit)

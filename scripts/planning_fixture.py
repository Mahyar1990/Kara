"""Produce clearly synthetic planner knowledge; never real development approval."""

import hashlib
import json
from pathlib import Path

import prepare_product_knowledge as knowledge

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return json.loads((ROOT / 'fixtures/planning/empty-category-list.json').read_text())


def context():
    sources = []
    for source_id, content in sample()['source_documents'].items():
        role, path = source_id.split(':', 1)
        sha = hashlib.sha256(content.encode()).hexdigest()
        sources.append({'id': source_id, 'role': role, 'path': path, 'commit': 'synthetic-' + role,
                        'kind': 'repository_policy' if path == 'AGENTS.md' else 'documentation',
                        'sha256': sha, 'content_sha256': sha, 'content': content})
    snapshots = {role: {'head': 'synthetic-' + role, 'resolved_ref': 'synthetic-fixture'} for role in ('backend', 'client', 'newman', 'playwright')}
    navigation = [{'source': {'id': role + ':PROJECT_MAP.md', 'role': role, 'path': 'PROJECT_MAP.md',
                             'commit': 'synthetic-' + role, 'sha256': 'synthetic', 'content_sha256': 'synthetic'},
                   'outline': ['## نمای ساختگی'], 'introduction': 'نمونهٔ ساختگی؛ به سورس واقعی نسبت داده نشود.',
                   'sections': [{'heading': 'نمای ساختگی', 'content': 'مسیرهای واقعی فایل و روش اجرای تست هنوز ارائه نشده‌اند.'}]} for role in ('backend', 'client')]
    value = {'schema_version': '1', 'product_id': 'klassor', 'synthetic': True,
             'knowledge_id': 'knowledge:synthetic-fixture', 'technical_context_id': 'context:synthetic-fixture',
             'repository_scope': ['backend', 'client'], 'repository_snapshots': snapshots,
             'repository_policies': [s for s in sources if s['kind'] == 'repository_policy'],
             'selected_repository_workflows': [], 'project_navigation': navigation, 'documentation_indexes': [],
             'selected_documentation': [s for s in sources if s['kind'] == 'documentation'],
             'available_sources': [{key: s[key] for key in ('id', 'role', 'path', 'kind')} for s in sources],
             'source_gaps': [], 'human_data_review_required': True, 'source_code_review_required': True,
             'development_ready': False}
    return {**value, 'agent_context_id': 'agent-context:' + knowledge.digest(value)}

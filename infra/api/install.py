"""Apply narrowly scoped integration hooks inside the custom image only."""
from pathlib import Path

root = Path('/app/api')
changes = {
    'services/enterprise/rbac_service.py': [(
        '            if not dify_config.RBAC_ENABLED:\n                if len(role_ids) != 1:\n',
        '            if not dify_config.RBAC_ENABLED:\n                from company_members.access import require_role_change\n                require_role_change(tenant_id, account_id, member_account_id, role_ids, session=session)\n                if len(role_ids) != 1:\n')],
    'controllers/console/__init__.py': [(
        'RESOURCE_MODULES = (\n', 'RESOURCE_MODULES = (\n    "company_projects.controller",\n')],
    'app_factory.py': [(
        '    initialize_extensions(app)\n',
        '    initialize_extensions(app)\n    from company_projects.store import migrate\n    from extensions.ext_database import db\n    with app.app_context():\n        migrate(db.engine)\n')],
    'services/app_service.py': [(
        'class CreateAppParams(BaseModel):\n',
        'class CreateAppParams(BaseModel):\n    project_id: str | None = None\n'), (
        '        app_mode = AppMode.value_of(params.mode)\n',
        '        if params.project_id:\n            from company_projects.store import get_project\n            get_project(session.connection(), tenant_id, params.project_id)\n        app_mode = AppMode.value_of(params.mode)\n'), (
        '        # Preserve the original commit-before-signal ordering for telemetry.\n',
        '        if params.project_id:\n            from company_projects.store import assign\n            assign(session.connection(), tenant_id, params.project_id, app.id)\n\n        # Preserve the original commit-before-signal ordering for telemetry.\n')],
}
for filename, replacements in changes.items():
    target = root / filename
    content = target.read_text()
    for old, new in replacements:
        assert content.count(old) == 1, f'Pinned source integration point changed: {filename}'
        content = content.replace(old, new)
    target.write_text(content)

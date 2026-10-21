"""Apply narrowly scoped integration hooks inside the custom image only."""
from pathlib import Path

root = Path('/app/api')
changes = {
    'services/enterprise/rbac_service.py': [(
        '            if not dify_config.RBAC_ENABLED:\n                if len(role_ids) != 1:\n',
        '            if not dify_config.RBAC_ENABLED:\n                from company_members.access import require_role_change\n                require_role_change(tenant_id, account_id, member_account_id, role_ids, session=session)\n                if len(role_ids) != 1:\n'), (
        'workspace=WorkspacePermissionSnapshot(permission_keys=list(permissions.get("workspace", []))),',
        'workspace=WorkspacePermissionSnapshot(permission_keys=__import__("company_projects.access", fromlist=["filter_permissions"]).filter_permissions(session, tenant_id, account_id, permissions.get("workspace", []))),')],
    'controllers/console/__init__.py': [(
        'RESOURCE_MODULES = (\n', 'RESOURCE_MODULES = (\n    "company_projects.controller",\n    "company_projects.readiness",\n    "company_projects.catalog",\n    "company_projects.inbox",\n    "company_projects.automations",\n')],
    'app_factory.py': [(
        '    initialize_extensions(app)\n',
        '    initialize_extensions(app)\n    from company_projects.store import migrate\n    from company_projects.team_migrations import migrate as migrate_team\n    from company_projects.access import initialize, restrict_central_workspace\n    from extensions.ext_database import db\n    with app.app_context():\n        migrate(db.engine)\n        migrate_team(db.engine)\n        with db.engine.begin() as connection:\n            initialize(connection)\n    restrict_central_workspace(app)\n')],
    'services/account_service.py': [(
        '        TenantService.check_member_permission(tenant, operator, account, "remove", session=session)\n',
        '        TenantService.check_member_permission(tenant, operator, account, "remove", session=session)\n        from company_projects.team import before_member_removal\n        before_member_removal(session, tenant.id, operator.id, account.id)\n'), (
        '        """Check member permission"""\n',
        '        """Check member permission"""\n        from company_projects.access import require_member_management\n        require_member_management(session, tenant.id, operator.id, member.id if member else None, action)\n'), (
        '        """Update member role"""\n',
        '        """Update member role"""\n        from company_projects.access import forbid_native_owner_transfer\n        forbid_native_owner_transfer(session, tenant.id, new_role)\n'), (
        '        tenant_was_created.send(tenant)\n',
        '        from company_projects.access import initialize\n        initialize(session.connection())\n        session.commit()\n        tenant_was_created.send(tenant)\n')],
    'services/system_feature_service.py': [(
        '        is_allowed = dify_config.ALLOW_CREATE_WORKSPACE\n',
        '        return False  # Project creation is controlled by the product owner.\n        is_allowed = dify_config.ALLOW_CREATE_WORKSPACE\n'), (
        '        is_allowed = dify_config.ALLOW_REGISTER\n',
        '        return False  # Company accounts are created through owner invitations.\n        is_allowed = dify_config.ALLOW_REGISTER\n'), (
        '        system_features.is_allow_register = dify_config.ALLOW_REGISTER\n',
        '        system_features.is_allow_register = False\n')],
    'services/app_service.py': [(
        'class CreateAppParams(BaseModel):\n',
        'class CreateAppParams(BaseModel):\n    project_id: str | None = None\n'), (
        '        app_mode = AppMode.value_of(params.mode)\n',
        '        if params.project_id:\n            from company_projects.access import validate_app_project\n            validate_app_project(session, tenant_id, params.project_id, account.id)\n        app_mode = AppMode.value_of(params.mode)\n'), (
        '        # Preserve the original commit-before-signal ordering for telemetry.\n',
        '        if params.project_id:\n            from company_projects.access import authority\n            from company_projects.store import assign\n            assign(session.connection(), authority(session)["tenant_id"], params.project_id, app.id)\n\n        # Preserve the original commit-before-signal ordering for telemetry.\n')],
    'services/workflow_draft_variable_service.py': [(
        '        # Ensure the session is bound to a engine.\n        assert isinstance(engine, Engine)\n        session_maker = sessionmaker(bind=engine, expire_on_commit=False)\n',
        '        # Company template imports use an outer transaction around native commits.\n        from sqlalchemy import Connection\n        assert isinstance(engine, (Engine, Connection))\n        session_maker = sessionmaker(bind=engine, expire_on_commit=False, join_transaction_mode="create_savepoint")\n')],
    'core/repositories/human_input_repository.py': [(
        '            form_model = session.get(HumanInputForm, form_id)\n            if form_model is None:\n                raise FormNotFoundError(f"form not found, id={form_id}")\n\n            recipient_model = session.get(HumanInputFormRecipient, recipient_id) if recipient_id else None\n',
        '            from company_projects.approval import lock_active_form\n            form_model = lock_active_form(session, form_id)\n            if form_model is None:\n                raise FormNotFoundError(f"form not found, id={form_id}")\n\n            recipient_model = session.get(HumanInputFormRecipient, recipient_id) if recipient_id else None\n'), (
        '            form_model = session.get(HumanInputForm, form_id)\n            if form_model is None:\n                raise FormNotFoundError(f"form not found, id={form_id}")\n\n            if timeout_status not in {HumanInputFormStatus.TIMEOUT, HumanInputFormStatus.EXPIRED}:\n',
        '            form_model = session.scalar(select(HumanInputForm).where(HumanInputForm.id == form_id).with_for_update())\n            if form_model is None:\n                raise FormNotFoundError(f"form not found, id={form_id}")\n\n            if timeout_status not in {HumanInputFormStatus.TIMEOUT, HumanInputFormStatus.EXPIRED}:\n')],
}
for filename, replacements in changes.items():
    target = root / filename
    content = target.read_text()
    for old, new in replacements:
        assert content.count(old) == 1, f'Pinned source integration point changed: {filename}'
        content = content.replace(old, new)
    target.write_text(content)

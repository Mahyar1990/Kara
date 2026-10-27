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
        'RESOURCE_MODULES = (\n', 'RESOURCE_MODULES = (\n    "company_projects.controller",\n    "company_projects.team_controller",\n    "company_projects.agent_controller",\n    "company_projects.flow_controller",\n    "company_projects.request_controller",\n    "company_projects.jira_controller",\n    "company_projects.gitlab_controller",\n    "company_projects.source_controller",\n    "company_projects.model_connection_controller",\n    "company_projects.stage_controller",\n    "company_projects.readiness",\n    "company_projects.catalog",\n    "company_projects.inbox",\n    "company_projects.automations",\n')],
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
changes['services/app_service.py'].append((
    '        filters = [App.tenant_id == tenant_id, App.is_universal == False]\n',
    '        from company_projects.personal_agent_sources import catalog_filter\n        filters = [App.tenant_id == tenant_id, App.is_universal == False, catalog_filter(session)]\n'))
changes['app_factory.py'].append((
    '    return socketio_app, app\n',
    '    from company_projects.agent_execution import install_http_guard\n    install_http_guard(app)\n    return socketio_app, app\n'))
changes['services/app_service.py'].append((
    '        app_was_deleted.send(app)\n',
    '        from company_projects.agent_execution import protect_source\n        protect_source(session, app_id=app.id)\n        app_was_deleted.send(app)\n'))
changes.update({
    'controllers/service_api/wraps.py': [(
        '            if not app_model.enable_api:\n',
        '            from company_projects.agent_execution import deny_native\n            deny_native(app_model.id)\n            if not app_model.enable_api:\n')],
    'controllers/web/wraps.py': [(
        '            if app_model.enable_site is False:\n',
        '            from company_projects.agent_execution import deny_native\n            deny_native(app_model.id)\n            if app_model.enable_site is False:\n')],
    'extensions/ext_celery.py': [(
        '    imports = [\n',
        '    imports = [\n        "company_projects.agent_execution",\n'), (
        '    celery_app.conf.update(beat_schedule=beat_schedule, imports=imports)\n',
        '    beat_schedule["kara_team_agent_outbox"] = {"task": "kara.team_agent.dispatch", "schedule": timedelta(seconds=15)}\n    celery_app.conf.update(beat_schedule=beat_schedule, imports=imports)\n')],
    'services/app_generate_service.py': [(
        '        return cls._run_with_guardrails(\n',
        '        from company_projects.agent_execution import deny_native\n        deny_native(app_model.id, session=session)\n        return cls._run_with_guardrails(\n')],
    'core/app/apps/workflow/app_generator.py': [(
        '        with self._bind_file_access_scope(tenant_id=app_model.tenant_id, user=user, invoke_from=invoke_from):\n',
        '        from company_projects.agent_execution import assert_execution, native_task_id\n        assert_execution(app_model.tenant_id, app_model.id, workflow.id, user.id, workflow_run_id)\n        with self._bind_file_access_scope(tenant_id=app_model.tenant_id, user=user, invoke_from=invoke_from):\n'), (
        '        if application_generate_entity.trace_manager is None:\n',
        '        from company_projects.agent_execution import deny_native\n        deny_native(app_model.id)\n        if application_generate_entity.trace_manager is None:\n')],
    'core/workflow/workflow_entry.py': [(
        '        # check call depth\n',
        '        from company_projects.agent_execution import assert_execution\n        assert_execution(tenant_id, app_id, workflow_id, user_id)\n        # check call depth\n'), (
        '        node_config = workflow.get_node_config_by_id(node_id)\n',
        '        from company_projects.agent_execution import deny_native\n        deny_native(workflow.app_id)\n        node_config = workflow.get_node_config_by_id(node_id)\n')],
    'services/workflow_service.py': [(
        '        if environment_variable_upserts is None and deleted_environment_variable_ids:\n',
        '        from company_projects.agent_execution import native_permission\n        native_permission(session, app_model.id, account.id)\n        if environment_variable_upserts is None and deleted_environment_variable_ids:\n'), (
        '        draft_workflow_stmt = select(Workflow).where(\n',
        '        from company_projects.agent_execution import native_permission\n        native_permission(session, app_model.id, account.id, "publish_definition")\n        draft_workflow_stmt = select(Workflow).where(\n'), (
        '        # Check if workflow is a draft version\n',
        '        from company_projects.agent_execution import protect_source\n        protect_source(session, workflow_id=workflow.id)\n        # Check if workflow is a draft version\n'), (
        '        files = files or []\n',
        '        from company_projects.agent_execution import deny_native\n        deny_native(app_model.id)\n        files = files or []\n')],
    'services/workflow_collaboration_service.py': [(
        '        if not user_id or not tenant_id:\n',
        '        from company_projects.agent_execution import managed\n        if managed(session, workflow_id) is not None:\n            session.rollback()\n            return None  # Managed definitions do not use socket collaboration yet.\n        session.rollback()\n        if not user_id or not tenant_id:\n'), (
        '        workflow_id = mapping["workflow_id"]\n        user_id = mapping["user_id"]\n',
        '        workflow_id = mapping["workflow_id"]\n        from company_projects.agent_execution import deny_native\n        deny_native(workflow_id)\n        user_id = mapping["user_id"]\n')],
})
changes['core/app/apps/workflow/app_generator.py'].append((
    '            application_generate_entity = WorkflowAppGenerateEntity(\n                task_id=str(uuid.uuid4()),\n',
    '            application_generate_entity = WorkflowAppGenerateEntity(\n                task_id=native_task_id(app_model.id, workflow_run_id),\n'))
changes['services/account_service.py'].extend([
    ('        tenant_join_role = TenantAccountRole.NORMAL.value if dify_config.RBAC_ENABLED else role\n',
     '        from company_members.product import validate_invitation, is_product_workspace\n        validate_invitation(session, tenant.id, role)\n        tenant_join_role = TenantAccountRole.NORMAL.value if dify_config.RBAC_ENABLED else role\n'),
    ('        new_tenant_role = TenantAccountRole(new_role)\n',
     '        from company_members.product import validate_role\n        validate_role(session, tenant.id, new_role)\n        new_tenant_role = TenantAccountRole(new_role)\n'),
])
changes['services/account_service.py'].append((
    '            if not ta and (account.status == AccountStatus.PENDING or dify_config.RBAC_ENABLED):\n',
    '            if not ta and (account.status == AccountStatus.PENDING or dify_config.RBAC_ENABLED or is_product_workspace(session, tenant.id)):\n'))
changes['repositories/account_activation_repository.py'] = [(
    '            membership_created = membership is None\n',
    '            from company_members.product import is_product_workspace\n            if membership is None and is_product_workspace(session, tenant_id):\n                return None  # A revoked central invitation cannot restore product authority.\n            membership_created = membership is None\n')]
changes['controllers/console/workspace/rbac.py'] = [
    ('    options: svc.ListOption | None = None, *, include_owner: int = 0, billing_enabled: bool = True\n',
     '    options: svc.ListOption | None = None, *, include_owner: int = 0, billing_enabled: bool = True, role_names: tuple[str, ...] | None = None\n'),
    ('    for role_name in ("owner", "admin", "editor", "normal", "dataset_operator"):\n',
     '    for role_name in role_names or ("owner", "admin", "editor", "normal", "dataset_operator"):\n'),
    ('            result = _legacy_workspace_roles(\n                options,\n',
     '            from company_members.product import available_roles\n            result = _legacy_workspace_roles(\n                options,\n                role_names=available_roles(db.session(), tenant_id),\n'),
]

# Personal model isolation is enforced at assembly, admission and final dispatch.
changes['core/provider_manager.py'] = [
    ('        cached_configurations = self._configurations_cache.get(tenant_id)\n',
     '        from company_projects.personal_model_runtime import personal_configurations\n        return personal_configurations(self._model_runtime, tenant_id)\n\n        cached_configurations = self._configurations_cache.get(tenant_id)\n'),
    ('    def get_default_model(self, tenant_id: str, model_type: ModelType) -> DefaultModelEntity | None:\n        """\n        Get default model.\n\n        :param tenant_id: workspace id\n        :param model_type: model type\n        :return:\n        """\n',
     '    def get_default_model(self, tenant_id: str, model_type: ModelType) -> DefaultModelEntity | None:\n        """\n        Get default model.\n\n        :param tenant_id: workspace id\n        :param model_type: model type\n        :return:\n        """\n        from company_projects.personal_model_runtime import personal_default\n        return personal_default(self._model_runtime, tenant_id, model_type)\n'),
]
changes['core/plugin/impl/model_runtime.py'] = [(
    '        self.user_id = user_id\n',
    '        from company_projects.personal_model_runtime import actor\n        self.user_id = actor(tenant_id, user_id)\n')]
changes['core/plugin/impl/model.py'] = [(
    'class PluginModelClient(BasePluginClient):\n',
    'from company_projects.model_client_boundary import install_client_boundary\n\n\n@install_client_boundary\nclass PluginModelClient(BasePluginClient):\n')]
# Preserve caller-role evidence even in thread-pool/worker graph construction.
changes['core/app/llm/model_access.py'] = [(
    '    provider_manager = create_plugin_provider_manager(\n        tenant_id=run_context.tenant_id,\n        user_id=run_context.user_id,\n    )\n',
    '    from company_projects.personal_model_runtime import require_run_identity\n    require_run_identity(run_context)\n    provider_manager = create_plugin_provider_manager(\n        tenant_id=run_context.tenant_id,\n        user_id=run_context.user_id,\n    )\n')]
changes['services/app_generate_service.py'].append((
    '        return cls._run_with_guardrails(\n',
    '        from company_projects.personal_model_runtime import require_account_execution\n        require_account_execution(app_model.tenant_id, user)\n        return cls._run_with_guardrails(\n'))
changes['services/async_workflow_service.py'] = [(
    '        # 1. Validate app exists\n',
    '        from company_projects.personal_model_runtime import require_account_execution\n        require_account_execution(trigger_data.tenant_id, user)\n        # 1. Validate app exists\n')]
changes['tasks/async_workflow_tasks.py'] = [(
    '                invoke_from=InvokeFrom.SERVICE_API,\n',
    '                invoke_from=InvokeFrom.EXPLORE if isinstance(user, Account) else InvokeFrom.SERVICE_API,\n')]
changes['tasks/workflow_schedule_tasks.py'] = [(
    '        tenant_owner = ScheduleService.get_tenant_owner(schedule.tenant_id, session=session)\n',
    '        from company_projects.personal_model_runtime import schedule_account\n        tenant_owner = schedule_account(session, schedule)\n')]
changes['app_factory.py'].append((
    '    install_http_guard(app)\n',
    '    install_http_guard(app)\n    from company_projects.personal_model_runtime import install_http_guard as install_personal_models_guard\n    install_personal_models_guard(app)\n'))

# The source graph stays immutable; only each native execution receives a resolved copy.
for kind, generator_name in (('workflow', 'WorkflowAppGenerator'), ('advanced_chat', 'AdvancedChatAppGenerator')):
    generator_path = f'core/app/apps/{kind}/app_generator.py'
    changes.setdefault(generator_path, []).extend([
        (f'class {generator_name}(',
         f'from company_projects.runtime_model_boundary import install_generator_boundary\n\n\n@install_generator_boundary\nclass {generator_name}('),
        ('            **extract_trace_session_id_from_args(args),\n',
         '            **extract_trace_session_id_from_args(args),\n            **__import__("company_projects.runtime_models", fromlist=["execution_extras"]).execution_extras(args),\n'),
        ('    if isinstance(args, Mapping):\n        return extract_trace_session_id_from_args(args)\n    return extract_trace_session_id_from_args({"trace_session_id": getattr(args, "trace_session_id", None)})\n',
         '    from company_projects.runtime_models import execution_extras\n    trace = extract_trace_session_id_from_args(args if isinstance(args, Mapping) else {"trace_session_id": getattr(args, "trace_session_id", None)})\n    return {**trace, **execution_extras(args)}\n'),
    ])
    changes.setdefault(f'core/app/apps/{kind}/app_runner.py', []).append((
        '        app_config = self.application_generate_entity.app_config\n',
        '        from company_projects.runtime_models import bind_runner\n        bind_runner(self)\n        app_config = self.application_generate_entity.app_config\n'))
changes['services/workflow_service.py'].extend([
    ('            try:\n                # Extract and validate credentials based on node type\n',
     '            from company_projects.runtime_models import policy\n            if node_type == "llm" and policy(graph_dict) is not None:\n                continue  # Personal model is selected and validated by each executor.\n            try:\n                # Extract and validate credentials based on node type\n'),
    ('        files = files or []\n\n        with Session(bind=db.engine, expire_on_commit=False) as session, session.begin():\n',
     '        files = files or []\n        from company_projects.runtime_models import prepare\n        if draft_workflow.get_node_config_by_id(node_id).get("data", {}).get("type") == "llm":\n            draft_workflow, user_inputs, _ = prepare(draft_workflow, account, dict(user_inputs))\n\n        with Session(bind=db.engine, expire_on_commit=False) as session, session.begin():\n'),
])
changes['models/workflow.py'] = [(
    '        variables: list[Any] = start_node.get("data", {}).get("variables", [])\n',
    '        variables: list[Any] = start_node.get("data", {}).get("variables", [])\n        from company_projects.runtime_models import form_variables\n        variables = form_variables(graph_dict, variables)\n')]
changes['services/app_dsl_service.py'] = [(
    '                    case BuiltinNodeTypes.LLM:\n                        llm_entity = LLMNodeData.model_validate(node["data"])\n',
    '                    case BuiltinNodeTypes.LLM:\n                        from company_projects.runtime_models import policy\n                        if policy(graph) is not None:\n                            continue  # Each executor supplies an installed personal provider.\n                        llm_entity = LLMNodeData.model_validate(node["data"])\n')]

# All compute paths are replaced or blocked; there is no central fallback.
changes['services/app_generate_service.py'].append((
    '        return cls._run_with_guardrails(\n',
    '        from company_projects.local_dispatch import generate as generate_locally\n        return generate_locally(app_model, user, args, invoke_from, session, streaming, root_node_id)\n        return cls._run_with_guardrails(\n'))
changes.setdefault('services/async_workflow_service.py', []).append((
    '        # 7. Reserve quota (commit after successful dispatch)\n',
    '        from company_projects.local_dispatch import enqueue_trigger\n        return enqueue_trigger(session, user, app_model, workflow, trigger_data, trigger_log)\n        # 7. Reserve quota (commit after successful dispatch)\n'))
changes['core/app/apps/workflow/app_generator.py'].append((
    '@install_generator_boundary\nclass WorkflowAppGenerator(',
    'from company_projects.local_dispatch import generator_boundary\n\n\n@generator_boundary\n@install_generator_boundary\nclass WorkflowAppGenerator('))
changes['core/workflow/workflow_entry.py'].append((
    '        # check call depth\n',
    '        from company_projects.local_dispatch import blocked\n        blocked()\n        # check call depth\n'))
# Single-node previews must also go through the device protocol rather than sandbox/model workers.
changes['services/workflow_service.py'].append((
    '        files = files or []\n',
    '        from company_projects.local_node_dispatch import run_node\n        return run_node(app_model, draft_workflow, node_id, user_inputs, account)\n        files = files or []\n'))

# Model/plugin and raw code boundaries cannot execute centrally even if a new route bypasses dispatch.
changes['core/helper/code_executor/code_executor.py'] = [(
    '        running_language = cls.code_language_to_running_language.get(language)\n',
    '        from company_projects.local_rpc import raw_code\n        return raw_code(language, preload, code)\n        running_language = cls.code_language_to_running_language.get(language)\n')]
changes['core/plugin/impl/tool.py'] = [(
    '        tool_provider_id = GenericProviderID(tool_provider)\n',
    '        from company_projects.local_dispatch import blocked\n        blocked()\n        tool_provider_id = GenericProviderID(tool_provider)\n')]

for kind, class_name in (('chat','ChatAppGenerator'),('completion','CompletionAppGenerator'),('agent_chat','AgentChatAppGenerator'),('agent_app','AgentAppGenerator'),('advanced_chat','AdvancedChatAppGenerator')):
    path=f'core/app/apps/{kind}/app_generator.py'
    anchor=(f'@install_generator_boundary\nclass {class_name}(' if kind=='advanced_chat' else f'class {class_name}(')
    replacement=(f'from company_projects.local_dispatch import block_generator\n\n\n@block_generator\n@install_generator_boundary\nclass {class_name}(' if kind=='advanced_chat' else f'from company_projects.local_dispatch import block_generator\n\n\n@block_generator\nclass {class_name}(')
    changes.setdefault(path,[]).append((anchor,replacement))
changes['core/app/apps/base_app_queue_manager.py'] = [(
    '        result: Any | None = redis_client.get(cls._generate_task_belong_cache_key(task_id))\n',
    '        from company_projects.local_dispatch import stop as stop_local\n        if stop_local(task_id, user_id):\n            return\n        result: Any | None = redis_client.get(cls._generate_task_belong_cache_key(task_id))\n')]

changes['core/workflow/workflow_entry.py'].extend([
    ('        node_config = workflow.get_node_config_by_id(node_id)\n',
     '        from company_projects.local_dispatch import blocked\n        blocked()\n        node_config = workflow.get_node_config_by_id(node_id)\n'),
    ('        # Create a minimal graph for single node execution\n',
     '        from company_projects.local_dispatch import blocked\n        blocked()\n        # Create a minimal graph for single node execution\n'),
])

changes['services/app_generate_service.py'].append((
    '        if workflow_run.status.is_ended():\n',
    '        from company_projects.local_dispatch import resume as resume_local\n        stream = resume_local(app_model, workflow_run)\n        if stream is not None:\n            return stream\n        if workflow_run.status.is_ended():\n'))

for filename, replacements in changes.items():
    target = root / filename
    content = target.read_text()
    for old, new in replacements:
        assert content.count(old) == 1, f'Pinned source integration point changed: {filename}'
        content = content.replace(old, new)
    target.write_text(content)

"""Read-only personal Runner dashboard; never expose job payloads or credentials."""
import sqlalchemy as sa
from company_projects import access, agents, local_execution as local, source_code as source
from models.model import App


def overview(s, actor):
    devices = source.devices(s, actor)['data']
    projects = {str(p['id']): dict(id=str(p['id']), name=p['name'], workspace_id=str(p['workspace_id']), binding=None)
                for p in access.list_for_account(s, actor) if p['workspace_id']}
    if not projects:
        return dict(devices=devices, projects=[], active=[], recent=[])
    bindings = local.table(s, 'execution_bindings')
    jobs = source.table(s, 'jobs')
    for row in s.execute(sa.select(bindings, jobs.c.snapshot['name'].astext.label('source_name'),
                                  jobs.c.snapshot['revision'].astext.cast(sa.Integer).label('source_revision'),
                                  jobs.c.state.label('source_state'))
                         .outerjoin(jobs, sa.and_(jobs.c.id == bindings.c.source_job_id,
                                                 jobs.c.account_id == str(actor)))
                         .where(bindings.c.account_id == str(actor), bindings.c.project_id.in_(projects))).mappings():
        projects[str(row['project_id'])]['binding'] = dict(
            device_id=str(row['device_id']), source_job_id=str(row['source_job_id']) if row['source_job_id'] else None,
            source_name=row['source_name'], source_revision=row['source_revision'], source_state=row['source_state'])

    active, recent = [], []
    now = agents.now()
    def collect(table, kind, query):
        # Select only display metadata. Secrets, inputs, model messages, code and outputs stay out.
        for pending, target, limit in ((True, active, 100), (False, recent, 20)):
            rows = s.execute(query.where(table.c.account_id == str(actor), table.c.project_id.in_(projects),
                                         table.c.state.in_(source.ACTIVE) if pending else table.c.state.not_in(source.ACTIVE))
                             .order_by(table.c.created_at.desc()).limit(limit)).mappings()
            for row in rows:
                state = row['state']
                if state == 'running' and row['lease_until'] and row['lease_until'] < now:
                    state = 'interrupted'
                title = row['title'] or 'برنامهٔ بدون نام'
                if kind == 'rpc':
                    title = {'invoke_llm': 'درخواست مدل', 'invoke_text_embedding': 'بردارسازی دانش',
                             'invoke_rerank': 'رتبه‌بندی دانش', 'get_llm_num_tokens': 'شمارش توکن',
                             'get_text_embedding_num_tokens': 'شمارش توکن دانش',
                             'validate_model_credentials': 'آزمون اتصال مدل',
                             'validate_provider_credentials': 'آزمون اتصال مدل',
                             'raw-code': 'اجرای کد', 'http': 'اتصال به سرویس'}.get(row['title'], 'فراخوانی اتصال یا مدل')
                    if row['connection_kind'] in ('jira', 'gitlab'):
                        title = 'اتصال به جیرا' if row['connection_kind'] == 'jira' else 'اتصال به گیت‌لب'
                item = dict(id=str(row['id']), kind=kind, title=title, project_id=str(row['project_id']),
                            device_id=str(row['device_id']) if row['device_id'] else None,
                            state=state, created_at=row['created_at'].isoformat())
                (recent if pending and state == 'interrupted' else target).append(item)

    columns = lambda t: (t.c.id, t.c.project_id, t.c.device_id, t.c.state, t.c.created_at, t.c.lease_until)
    executions = local.table(s, 'local_executions')
    collect(executions, 'workflow', sa.select(*columns(executions), App.name.label('title'))
            .outerjoin(App, sa.and_(App.id == executions.c.app_id, App.tenant_id == executions.c.workspace_id)))
    collect(jobs, 'source', sa.select(*columns(jobs), jobs.c.snapshot['name'].astext.label('title')))
    rpc = local.table(s, 'local_rpc')
    collect(rpc, 'rpc', sa.select(*columns(rpc), rpc.c.method.label('title'), rpc.c.connection_kind))
    return dict(devices=devices, projects=list(projects.values()),
                active=sorted(active, key=lambda r: r['created_at'], reverse=True),
                recent=sorted(recent, key=lambda r: r['created_at'], reverse=True)[:20])

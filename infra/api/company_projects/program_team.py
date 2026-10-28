"""Program-centric presentation of existing immutable team execution settings."""
import sqlalchemy as sa
from company_projects import agents, team
from models.model import App


def catalog(s, project, workspace, actor):
    team.scope(s, project, workspace, actor)
    profiles = agents.list_agents(s, project, workspace, actor)
    groups = {}
    # Members with execution grants can discover their program without receiving
    # native design access. Only the manager sees unconfigured design candidates.
    if profiles['can_manage']:
        from company_projects.controller import visible_filters
        filters = visible_filters(s, str(workspace), str(actor))
        if filters:
            for app in s.scalars(sa.select(App).where(*filters, App.tenant_id == str(workspace), App.mode == 'workflow', App.status == 'normal').order_by(App.name)):
                groups[app.id] = dict(id=app.id, name=app.name, description=app.description or '', available=True, library_adapter=False, profiles=[])
    for profile in profiles['data']:
        identity = profile['app_id']
        app = s.get(App, identity)
        if app and app.tenant_id != str(workspace):
            continue  # Scope fence even if legacy data has an invalid foreign reference.
        group = groups.setdefault(identity, dict(id=identity, name=profile['app_name'], description='',
            available=bool(app and app.status == 'normal'), library_adapter=False, profiles=[]))
        group['library_adapter'] = group['library_adapter'] or bool(profile['personal_source'])
        group['profiles'].append(profile)
    return dict(can_manage=profiles['can_manage'], programs=sorted(groups.values(), key=lambda g: (g['name'], g['id'])))

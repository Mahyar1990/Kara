"""Native definition setup for the two pinned Klassor Workflows; no model runs."""
from clasor_agents.pa04.contract import ContractError, canonical, digest
from clasor_agents.pa04 import workflow as pa04
from clasor_agents.tl_planner import workflow as tl
from .caller import Caller, uid
from .flow import contracts

PACKAGES = {'analysis':pa04, 'planning':tl}


def verify_graph(role, workflow):
    if role not in PACKAGES: raise ContractError('definition_role')
    expected=PACKAGES[role].build()['workflow']
    graph=workflow.get('graph')
    if type(graph) is not dict or {k:v for k,v in graph.items() if k!='viewport'} != {
            k:v for k,v in expected['graph'].items() if k!='viewport'}:
        raise ContractError('definition_graph_mismatch')
    for key in ('environment_variables','conversation_variables','rag_pipeline_variables'):
        if workflow.get(key)!=expected[key]: raise ContractError('definition_variables_mismatch')
    return digest(canonical({k:v for k,v in graph.items() if k!='viewport'}))


class DefinitionCaller(Caller):
    """Administrative setup is separate from Caller used by stage executors.

    Only imported/verified app IDs and registered agent IDs may be configured.
    No flow publication, intake decisions, stage execution or model settings.
    """
    def __init__(self, origin, project_id, account_id, workspace_id):
        super().__init__(origin,project_id)
        self.account_id=uid(account_id);self.workspace_id=uid(workspace_id)
        self.apps=set();self.agents=set()

    def _scope(self): return self.actor(self.account_id,self.workspace_id)

    def _allowed(self, method, path):
        if super()._allowed(method,path): return True
        if method=='POST' and path=='/apps/imports': return True
        if method=='POST' and path==self.team+'/agents': return True
        for app_id in self.apps:
            if path=='/apps/'+app_id+'/workflows/publish' and method in ('GET','POST'):return True
            if path=='/apps/'+app_id+'/workflows/draft' and method=='GET':return True
        return any(path==self.team+'/agents/'+agent_id+'/grants' and method in ('GET','PUT') for agent_id in self.agents)

    def import_definition(self, role):
        self._scope()
        if role not in PACKAGES: raise ContractError('definition_role')
        package=PACKAGES[role];export=package.build()
        result=self._request('POST','/apps/imports',dict(mode='yaml-content',yaml_content=canonical(export),
            name=export['app']['name']+' · '+package.REVISION))
        if result.get('status') not in ('completed','completed-with-warnings'):
            raise ContractError('definition_import_incomplete')
        receipt=dict(role=role,app_id=uid(result['app_id']),revision=package.REVISION)
        # Save the returned import receipt before any later operation in caller code.
        return receipt

    def verify_import(self, receipt):
        self._scope()
        role=receipt['role']
        if role not in PACKAGES or receipt['revision']!=PACKAGES[role].REVISION:
            raise ContractError('definition_revision_mismatch')
        app_id=uid(receipt['app_id']);self.apps.add(app_id)
        draft=self._request('GET','/apps/'+app_id+'/workflows/draft')
        if draft['version']!='draft':raise ContractError('definition_draft_expected')
        return verify_graph(role,draft)

    def publish_definition(self, receipt):
        graph_hash=self.verify_import(receipt)
        app_id=receipt['app_id'];path='/apps/'+app_id+'/workflows/publish'
        marker=('PA04-' if receipt['role']=='analysis' else 'TL-')+receipt['revision']
        try: published=self._request('GET',path)
        except ContractError as error:
            if str(error)!='caller_http_404':raise
            published=None
        if published is None:
            self._request('POST',path,dict(marked_name=marker,
                marked_comment='Definition setup only; no model or human-stage acceptance.'))
            published=self._request('GET',path)
        if (not published or published['version']=='draft' or published['marked_name']!=marker
                or verify_graph(receipt['role'],published)!=graph_hash):
            raise ContractError('definition_publication_mismatch')
        return dict(receipt,workflow_id=uid(published['id']),graph_sha256=graph_hash)

    def register_definition(self, receipt, key):
        self._scope();app_id=uid(receipt['app_id']);self.apps.add(app_id)
        published=self._request('GET','/apps/'+app_id+'/workflows/publish')
        if (not published or published['id']!=receipt['workflow_id']
                or verify_graph(receipt['role'],published)!=receipt['graph_sha256']):
            raise ContractError('definition_publication_mismatch')
        matches=[a for a in self._request('GET',self.team+'/agents')['data'] if a['app_id']==app_id]
        if not matches:
            package=PACKAGES[receipt['role']]
            agent=self._request('POST',self.team+'/agents',dict(app_id=app_id,workflow_id=receipt['workflow_id'],
                name=package.build()['app']['name']+' · '+package.REVISION,
                description='نسخهٔ مستقل پایلوت؛ پذیرش مدل و تصمیم انسانی هنوز انجام نشده است.',expected_revision=1),key)
        elif len(matches)==1: agent=matches[0]
        else: raise ContractError('definition_registration_conflict')
        ic,oc=contracts(PACKAGES[receipt['role']].build())
        if (agent['app_id']!=app_id or agent['workflow_id']!=receipt['workflow_id'] or agent['archived']
                or sorted(agent['input_contract'],key=lambda v:v['variable'])!=ic or agent['output_contract']!=oc):
            raise ContractError('definition_registration_mismatch')
        self.agents.add(uid(agent['id']))
        return agent

    def assign_responsible(self, agent_id, person, key):
        self._scope();agent_id=uid(agent_id)
        if agent_id not in self.agents: raise ContractError('definition_agent_unverified')
        path=self.team+'/agents/'+agent_id+'/grants'
        expected=[dict(account_id=uid(person['account_id']),membership_id=uid(person['membership_id']),
                       actions=['feedback','finalize','run','view'])]
        before=self._request('GET',path)
        if before['grants'] and before['grants']!=expected:raise ContractError('definition_grants_conflict')
        if not before['grants']:
            self._request('PUT',path,dict(expected_revision=before['revision'],grants=expected),key)
        after=self._request('GET',path)
        if after['grants']!=expected:raise ContractError('definition_grants_mismatch')
        return after

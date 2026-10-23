"""Publish one reviewed Klassor flow version; never create or execute an instance."""
from copy import deepcopy
import re
from clasor_agents.pa04.contract import ContractError, canonical, digest
from .caller import Caller, uid
from .definitions import PACKAGES, verify_graph
from .flow import bind


def verify_version(packet, version):
    """Check the immutable native snapshot against an independent review packet."""
    draft=packet['draft'];expected=packet['stages']
    if (version['flow_id']!=draft['id'] or version['source_revision']!=draft['revision']
            or version['version']!=packet['next_version'] or version['contract_version']!=1
            or version['name']!=draft['name'] or version['description']!=draft['description']
            or len(version['stage_bindings'])!=len(expected)):
        raise ContractError('flow_publication_mismatch')
    for actual,wanted in zip(version['stage_bindings'],expected):
        if (set(actual)!=set(wanted)|{'workflow_digest'} or any(actual[k]!=v for k,v in wanted.items())
                or type(actual['workflow_digest']) is not str
                or re.fullmatch('[0-9a-f]{64}',actual['workflow_digest']) is None):
            raise ContractError('flow_snapshot_mismatch')
    # Native Workflow fingerprint differs from the exported graph hash. Kara
    # checks it during compilation; include it unchanged in the snapshot digest.
    content={k:version[k] for k in ('contract_version','name','description','stage_bindings')}
    if digest(canonical(content))!=version['digest']:
        raise ContractError('flow_snapshot_digest_mismatch')
    return version


class FlowPublisher(Caller):
    def __init__(self,origin,project_id,account_id,workspace_id):
        super().__init__(origin,project_id)
        self.account_id=uid(account_id);self.workspace_id=uid(workspace_id)
        self.reviewed_flows=set()

    def _scope(self):return self.actor(self.account_id,self.workspace_id)

    def _allowed(self,method,path):
        if super()._allowed(method,path):return True
        return method=='POST' and any(path==self.team+'/flows/'+fid+'/publish' for fid in self.reviewed_flows)

    def review(self, draft, selections, receipts):
        """Read-only. Save this exact packet privately before publication."""
        self._scope()
        current=self._request('GET',self.team+'/flows/'+uid(draft['id']))
        keys=('id','name','description','revision','current_version_id','draft_stages')
        if current.get('archived') or not current.get('can_edit') or any(current[k]!=draft[k] for k in keys):
            raise ContractError('flow_review_stale')
        if set(receipts)!=set(PACKAGES):raise ContractError('flow_receipt_fields')
        options=self.options();body=bind(options,selections)
        if body['stages']!=current['draft_stages']:raise ContractError('flow_review_mapping_mismatch')
        agents=self._request('GET',self.team+'/agents')['data']
        stages=[]
        for stage in current['draft_stages']:
            key=stage['key'];receipt=receipts[key];package=PACKAGES[key]
            if (receipt['role']!=key or receipt['revision']!=package.REVISION
                    or receipt['workflow_id']!=selections[key]['workflow_id']):
                raise ContractError('flow_receipt_mismatch')
            app_id=uid(receipt['app_id'])
            # Managed-source reads require edit_definition, which stage owners
            # intentionally lack. Use the independently saved pre-registration
            # graph proof and immutable Workflow ID; native compilation checks
            # the current registered Workflow fingerprint in its transaction.
            if verify_graph(key,package.build()['workflow'])!=receipt['graph_sha256']:
                raise ContractError('flow_receipt_mismatch')
            matching=[a for a in agents if a['id']==stage['agent_id']]
            if (len(matching)!=1 or matching[0]['archived'] or matching[0]['app_id']!=app_id
                    or matching[0]['workflow_id']!=receipt['workflow_id']):
                raise ContractError('flow_review_agent_mismatch')
            agent=matching[0]
            member=next(m for m in options['members'] if m['account_id']==stage['executor_id'])
            person=dict(account_id=member['account_id'],membership_id=member['membership_id'],name=member['name'])
            stages.append(dict(key=key,title=stage['title'],agent_id=agent['id'],agent_name=agent['name'],
                agent_revision=agent['revision'],workflow_id=agent['workflow_id'],
                input_contract=deepcopy(agent['input_contract']),output_contract=deepcopy(agent['output_contract']),
                contract_version=1,executor=person,finalizer=deepcopy(person),decision_role=stage['decision_role'],
                inputs=deepcopy(stage['inputs']),depends_on=[stages[-1]['key']] if stages else []))
        return dict(draft={k:deepcopy(current[k]) for k in keys},selections=deepcopy(selections),
            receipts=deepcopy(receipts),stages=stages,
            next_version=(current['published']['version']+1 if current['published'] else 1))

    def publish_reviewed(self,packet,key):
        self._scope();uid(key)
        draft=packet['draft'];flow_id=uid(draft['id']);path=self.team+'/flows/'+flow_id
        current=self._request('GET',path)
        # Recover a prior uncertain submission by reading the exact version;
        # never issue an automatic retry or create an extra immutable version.
        if (current['revision']==draft['revision']+1 and current['current_version_id']
                and current['current_version_id']!=draft['current_version_id']):
            version=self._request('GET',path+'/versions/'+uid(current['current_version_id']))
            return verify_version(packet,version)
        if self.review(draft,packet['selections'],packet['receipts'])!=packet:
            raise ContractError('flow_review_stale')
        self.reviewed_flows.add(flow_id)
        self._request('POST',path+'/publish',dict(expected_revision=draft['revision']),key)
        current=self._request('GET',path)
        if (current['revision']!=draft['revision']+1 or not current['current_version_id']
                or current['current_version_id']==draft['current_version_id']):
            raise ContractError('flow_publication_readback_mismatch')
        version=self._request('GET',path+'/versions/'+uid(current['current_version_id']))
        return verify_version(packet,version)

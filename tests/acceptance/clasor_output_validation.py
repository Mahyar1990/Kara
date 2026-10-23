"""Specialized hooks on the master API image, synthetic provenance, real Code sandbox.

Mount the repository at /assets:ro. Run with a restored test DB and no worker.
No model or whole Workflow is executed; no genuine PO/TL acceptance is claimed.
"""
import os
if os.environ.get('DB_DATABASE') != 'kara_kp01_restore':
    raise SystemExit('Refusing test writes outside kara_kp01_restore')

import copy
import json
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = ['/app/api', '/assets']
from clasor_agents.pa04 import workflow as pa04
from clasor_agents.pa04.contract import ROOT as PA_ROOT, build_inputs as pa_inputs, canonical
from clasor_agents.tl_planner import workflow as tl
from clasor_agents.tl_planner.contract import ROOT as TL_ROOT
from clasor_agents.tl_planner.transport import build_inputs as tl_inputs
from company_projects.test_stages import StageFixture
from models.workflow import Workflow, WorkflowNodeExecutionModel, WorkflowRun
from werkzeug.exceptions import UnprocessableEntity


class HookFixture(StageFixture):
    def setUp(self):
        self.export = self.package.build()
        self.nodes = {n['id']:n['data'] for n in self.export['workflow']['graph']['nodes']}
        self.case = json.loads((self.root/'fixtures/cases.json').read_text())[0]
        if self.package is pa04:
            self.wire = pa_inputs(self.case['input'], self.case['expected_binding'])
        else:
            self.wire = tl_inputs(self.case['prepared_input'], self.case['expected_input_sha256'])
        with patch('company_projects.test_stages.feedback_graph', lambda:copy.deepcopy(self.export['workflow']['graph'])):
            super().setUp()

    def request(self, row=None, **changes):
        changes.setdefault('content', self.wire['request'])
        return super().request(row, **changes)

    def stage(self, key='analysis', agent=0, source=None):
        if source and source.get('source') == 'stage':
            source = dict(source, output=self.output)
        value = super().stage(key, agent, source)
        value['inputs'].update({name:dict(source='constant',value=text or 'هنوز بازخوردی ثبت نشده است.')
            for name,text in self.wire.items() if name != 'request'})
        return value

    def verify_specialized_hook(self):
        text = canonical(self.case['reference_output'])
        row = self.complete(output={self.output:text})
        selected = row['artifacts'][0]
        workflow = self.session.get(Workflow, row['binding']['workflow_id'])
        prepare = {}
        exec(compile(self.nodes['prepare']['code'], '<synthetic-prepare>', 'exec'), prepare)
        prepared = prepare['main'](**self.wire)
        code_inputs = dict(text=text,finish_reason='stop')
        for item in self.nodes['validate']['variables']:
            node_id, name = item['value_selector']
            if node_id == 'start': code_inputs[item['variable']] = self.wire[name]
            elif node_id == 'prepare': code_inputs[item['variable']] = prepared[name]
        self.session.add(WorkflowRun(id=selected['attempt_id'],tenant_id=self.workspace_a.id,
            app_id=workflow.app_id,workflow_id=workflow.id,type='workflow',triggered_from='app-run',
            version=workflow.version,graph=workflow.graph,inputs=json.dumps(row['preview_inputs']),
            status='succeeded',outputs=json.dumps(selected['content']),created_by_role='account',created_by=self.editor.id))
        execution = WorkflowNodeExecutionModel(tenant_id=self.workspace_a.id,app_id=workflow.app_id,
            workflow_id=workflow.id,workflow_run_id=selected['attempt_id'],triggered_from='workflow-run',
            index=1,node_id='validate',node_type='code',title='Synthetic recorded validation',status='succeeded',
            inputs=json.dumps(code_inputs),outputs=json.dumps(selected['content']),created_by_role='account',created_by=self.editor.id)
        self.session.add(execution);self.session.flush()
        invalid = copy.deepcopy(self.case['reference_output'])
        invalid['request_sha256' if self.package is pa04 else 'input_sha256'] = '0'*64
        with self.assertRaises(UnprocessableEntity):
            self.act(row,'edit_output',artifact_id=selected['id'],content={self.output:canonical(invalid)},reason='synthetic invalid edit')
        self.assertEqual(self.get(),row)
        row = self.act(row,'edit_output',artifact_id=selected['id'],content={self.output:text+'\n'},reason='synthetic valid edit')
        human = row['artifacts'][0]
        self.assertEqual(human['content'],{self.output:text})
        self.assertEqual(human['parent_id'],selected['id'])
        self.assertEqual(row['output_validation']['artifact_id'],human['id'])
        row = self.act(row,'request_decision',artifact_id=human['id'])
        for reason in (None,'length'):
            execution.inputs = json.dumps(dict(code_inputs,finish_reason=reason));self.session.flush()
            with self.subTest(reason=reason),self.assertRaises(UnprocessableEntity):
                self.act(row,'finalize',actor=self.project_owner,artifact_id=human['id'],reason='must remain blocked')
            self.assertEqual(self.get()['decisions'],[])
            self.assertEqual(self.get(self.second)['state'],'blocked')


class PA04HookTests(HookFixture):
    package, root, output = pa04, PA_ROOT, 'analysis'

    def test_pa04_human_edit_and_real_metadata_gate(self):
        self.verify_specialized_hook()


class TLHookTests(HookFixture):
    package, root, output = tl, TL_ROOT, 'plan'

    def test_tl_human_edit_and_real_metadata_gate(self):
        self.verify_specialized_hook()


if __name__ == '__main__':
    unittest.main()

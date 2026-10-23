"""Deterministic native-sandbox validation; persisted provenance, no model calls."""
import copy
import json
from unittest.mock import patch

from werkzeug.exceptions import Conflict, UnprocessableEntity

from company_projects import agents, output_validation, stages
from company_projects.test_stages import StageFixture, feedback_graph
from models.workflow import Workflow, WorkflowNodeExecutionModel, WorkflowRun

CODE = '''def main(text, original):
    if not text.startswith('valid:') or not original:
        raise ValueError('synthetic contract failure')
    return dict(answer=text.strip())
'''


def validated_graph():
    graph = feedback_graph()
    graph['nodes'].insert(1, dict(id='validate', data=dict(type='code', code_language='python3',
        code=CODE, title='Synthetic validator', kara_output_validator=dict(version=1, candidate_arguments={'text': 'answer'}),
        variables=[dict(variable='text', value_selector=['start', 'request']),
                   dict(variable='original', value_selector=['start', 'request'])],
        outputs=dict(answer=dict(type='string', children=None)))))
    graph['nodes'][-1]['data']['outputs'][0]['value_selector'] = ['validate', 'answer']
    graph['edges'] = [dict(id='one', source='start', target='validate'), dict(id='two', source='validate', target='end')]
    return graph


class OutputValidationTests(StageFixture):
    def setUp(self):
        with patch('company_projects.test_stages.feedback_graph', validated_graph):
            super().setUp()

    def recorded(self):
        row = self.complete(output={'answer': 'valid: native'})
        selected = row['artifacts'][0]
        workflow = self.session.get(Workflow, row['binding']['workflow_id'])
        self.session.add(WorkflowRun(id=selected['attempt_id'], tenant_id=self.workspace_a.id,
            app_id=workflow.app_id, workflow_id=workflow.id, type='workflow', triggered_from='app-run',
            version=workflow.version, graph=workflow.graph, inputs=json.dumps(row['preview_inputs']),
            status='succeeded', outputs=json.dumps(selected['content']), created_by_role='account', created_by=self.editor.id))
        self.execution = WorkflowNodeExecutionModel(tenant_id=self.workspace_a.id, app_id=workflow.app_id,
            workflow_id=workflow.id, workflow_run_id=selected['attempt_id'], triggered_from='workflow-run',
            index=1, node_id='validate', node_type='code', title='Synthetic validator', status='succeeded',
            inputs=json.dumps(dict(text='valid: native', original=row['preview_inputs']['request'])),
            outputs=json.dumps(selected['content']), created_by_role='account', created_by=self.editor.id)
        self.session.add(self.execution); self.session.flush()
        return row

    def test_invalid_human_edit_is_rejected_and_valid_selected_edit_is_delivered(self):
        row = self.recorded(); original = row['artifacts'][0]
        with self.assertRaises(UnprocessableEntity):
            self.act(row, 'edit_output', artifact_id=original['id'], content={'answer': 'invalid'}, reason='edit')
        self.assertEqual(self.get(), row)
        row = self.act(row, 'edit_output', artifact_id=original['id'], content={'answer': 'valid: human  '}, reason='edit')
        selected = row['artifacts'][0]
        self.assertEqual(selected['content'], {'answer': 'valid: human'})
        self.assertEqual(row['output_validation']['outcome'], 'passed')
        row = self.act(row, 'request_decision', artifact_id=selected['id'])
        row = self.act(row, 'finalize', actor=self.project_owner, artifact_id=selected['id'], reason='synthetic decision')
        self.assertEqual(row['state'], 'completed')
        self.assertEqual(self.get(self.second)['preview_inputs']['request'], 'valid: human')

    def test_finalization_rechecks_validator_and_unavailable_service_fails_closed(self):
        row = self.recorded(); selected = row['artifacts'][0]
        row = self.act(row, 'request_decision', artifact_id=selected['id'])
        with patch('core.helper.code_executor.code_executor.CodeExecutor.execute_workflow_code_template', side_effect=RuntimeError('private context')):
            with self.assertRaises(UnprocessableEntity) as error:
                self.act(row, 'finalize', actor=self.project_owner, artifact_id=selected['id'], reason='blocked')
        self.assertNotIn('private context', str(error.exception))
        self.assertEqual(self.get()['decisions'], [])
        self.assertEqual(self.get(self.second)['state'], 'blocked')

    def test_missing_or_duplicate_native_context_cannot_be_used(self):
        row = self.recorded(); selected = row['artifacts'][0]
        self.execution.inputs = '{}'; self.session.flush()
        with self.assertRaises(Conflict):
            self.act(row, 'request_decision', artifact_id=selected['id'])
        self.execution.inputs = json.dumps(dict(text='valid: native', original='source'))
        self.execution.status = 'failed'; self.session.flush()
        with self.assertRaises(Conflict):
            self.act(row, 'request_decision', artifact_id=selected['id'])
        self.execution.status = 'succeeded'
        duplicate = {column.name: getattr(self.execution, column.name)
            for column in self.execution.__table__.columns if column.name != 'id'}
        self.session.add(WorkflowNodeExecutionModel(**dict(duplicate, index=2)))
        self.session.flush()
        with self.assertRaises(Conflict):
            self.act(row, 'request_decision', artifact_id=selected['id'])

    def test_definition_rejects_unsupported_or_partial_output_validation(self):
        workflow = self.session.get(Workflow, self.get()['binding']['workflow_id'])
        graph = workflow.graph_dict
        for change in ('version', 'arguments', 'end', 'language', 'duplicate'):
            candidate = copy.deepcopy(graph)
            data = candidate['nodes'][1]['data']
            if change == 'version': data['kara_output_validator']['version'] = True
            elif change == 'arguments': data['kara_output_validator']['candidate_arguments'] = {'missing': 'answer'}
            elif change == 'end': candidate['nodes'][-1]['data']['outputs'][0]['value_selector'] = ['start', 'request']
            elif change == 'language': data['code_language'] = 'javascript'
            else: candidate['nodes'].append(copy.deepcopy(candidate['nodes'][1]))
            with self.subTest(change=change), self.assertRaises(UnprocessableEntity):
                output_validation.definition(type('Source', (), dict(graph_dict=candidate))())

    def test_only_declared_code_runs_and_context_is_not_replaced(self):
        row = self.recorded(); selected = row['artifacts'][0]
        def evaluate(language, code, inputs):
            self.assertEqual(code, CODE)
            self.assertEqual(inputs['original'], self.req['current']['content'])
            self.assertEqual(inputs['text'], 'valid: replacement')
            return {'answer': 'valid: replacement'}
        with patch('core.helper.code_executor.code_executor.CodeExecutor.execute_workflow_code_template', side_effect=evaluate):
            result = self.act(row, 'edit_output', artifact_id=selected['id'], content={'answer': 'valid: replacement'}, reason='edit')
        self.assertEqual(result['output_validation']['attempt_id'], selected['attempt_id'])

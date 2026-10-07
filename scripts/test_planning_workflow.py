import unittest
import build_klassor_planning as planning
import planning_fixture

class PlanningWorkflowTests(unittest.TestCase):
    def test_native_review_and_single_end(self):
        workflow = planning.build()
        nodes = {n['id']: n['data'] for n in workflow['workflow']['graph']['nodes']}
        self.assertEqual(sum(n['type'] == 'end' for n in nodes.values()), 1)
        self.assertEqual(nodes['human_review']['type'], 'human-input')
        self.assertIn('allow_trial=False', nodes['planning_gate']['code'])
        self.assertNotIn('agent_context_json', [v['variable'] for v in nodes['start']['variables']])
        self.assertIn('source_review', [v['output_variable_name'] for v in nodes['human_review']['inputs']])
        edges = workflow['workflow']['graph']['edges']
        self.assertEqual([(e['source'], e['sourceHandle']) for e in edges if e['target']=='planner'], [('planning_route', 'true')])

    def test_trial_is_separate_and_codes_compile(self):
        workflow = planning.build(True, planning_fixture.context())
        for node in workflow['workflow']['graph']['nodes']:
            if node['data']['type'] == 'code':
                compile(node['data']['code'], node['id'], 'exec')
        gate = next(n for n in workflow['workflow']['graph']['nodes'] if n['id']=='planning_gate')
        self.assertIn('allow_trial=True', gate['data']['code'])
        self.assertNotIn('آزمون برنامه‌ریز', planning.build()['app']['name'])

    def test_large_context_rejected(self):
        with self.assertRaises(ValueError):
            planning.build(bundle={'data':'ب'*110000})

    def test_review_display_has_only_declared_outputs(self):
        workflow = planning.build()
        node = next(n for n in workflow['workflow']['graph']['nodes'] if n['id']=='review_output')
        namespace = {}
        exec(node['data']['code'], namespace)
        data = {key:'sample' for key in planning.review.OUTPUTS}
        data.update(source_review='reviewed', reviewed_agent_context_id='private-context')
        result = namespace['main'](planning.json.dumps(data))
        self.assertEqual(set(result), set(node['data']['outputs']))
        self.assertNotIn('source_review', result)

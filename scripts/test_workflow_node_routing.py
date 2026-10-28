"""Deterministic two-device graph traversal without model or code execution."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runner'))
from kara_source_runner.workflow_runtime import WorkflowRuntime


class NodeRoutingTests(unittest.TestCase):
    def test_remote_model_receives_prior_output_and_its_result_drives_next_node(self):
        graph = dict(nodes=[
            dict(id='start', data=dict(type='start', variables=[])),
            dict(id='first', data=dict(type='llm', model=dict(mode='chat'), prompt_template=[dict(text='{{#start.query#}}')])),
            dict(id='second', data=dict(type='llm', model=dict(mode='chat'), prompt_template=[dict(text='{{#first.text#}}')])),
            dict(id='end', data=dict(type='end', outputs=[dict(variable='answer', value_selector=['second', 'text'])])),
        ], edges=[dict(source=a, target=b) for a,b in [('start','first'),('first','second'),('second','end')]])
        job = dict(id='run', graph=graph, inputs={'query':'question'}, device_id='one', routes={'first':dict(device_id='one'), 'second':dict(device_id='two')})
        calls = []
        class Model:
            def __init__(self, secret): self.name = secret['model_name']
            def chat(self, messages, params):
                calls.append((self.name, messages[0]['content']))
                return dict(text=self.name + ':' + messages[0]['content'], usage=dict(total_tokens=2))
        def delegate(identity, pool):
            self.assertNotIn('env', pool)
            remote = WorkflowRuntime(job, dict(models={'second':dict(model_name='B')}), None, None, lambda _: None, cancelled)
            remote.pool.update(pool)
            output,branch = remote.node(identity, next(n['data'] for n in graph['nodes'] if n['id']==identity))
            return dict(output=output, branch=branch, total_tokens=remote.tokens)
        cancelled = type('Cancelled', (), dict(is_set=lambda _:False))()
        events = []
        coordinator = WorkflowRuntime(job, dict(models={'first':dict(model_name='A')}, environment={'private':'hidden'}), None, None, events.append, cancelled, delegate)
        with patch('kara_source_runner.workflow_runtime.Model', Model): result = coordinator.run()
        self.assertEqual(calls, [('A','question'),('B','A:question')])
        self.assertEqual(result, dict(outputs={'answer':'B:A:question'},total_steps=4,total_tokens=4))
        self.assertEqual([event['node_id'] for event in events if event['event']=='node_finished'], ['start','first','second','end'])

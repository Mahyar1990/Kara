"""Input and timezone contract; no model, Docker or customer data needed."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('automation_schedule', Path(__file__).resolve().parents[1] / 'infra/api/company_projects/automation_schedule.py')
schedule = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schedule)


class AutomationScheduleTests(unittest.TestCase):
    def test_tehran_weekly_schedule_and_midnight_noon_conversion(self):
        value = schedule.schedule_data(dict(frequency='weekly', time='09:30', weekdays=['sat', 'sat', 'mon']))
        self.assertEqual(value['timezone'], 'Asia/Tehran')
        self.assertEqual(value['visual_config'], dict(time='9:30 AM', weekdays=['mon', 'sat']))
        self.assertEqual(schedule.schedule_data(dict(frequency='daily', time='00:15'))['visual_config']['time'], '12:15 AM')
        self.assertEqual(schedule.schedule_data(dict(frequency='monthly', time='12:00', day=31))['visual_config']['time'], '12:00 PM')

    def test_invalid_schedule_is_rejected_before_creating_an_app(self):
        for value in [None, {}, dict(frequency='daily', time='24:00'), dict(frequency='weekly', time='09:00', weekdays=[]),
                dict(frequency='hourly', minute=True), dict(frequency='monthly', time='09:00', day=32)]:
            with self.subTest(value=value), self.assertRaises(schedule.AutomationError):
                schedule.schedule_data(value)

    def test_inputs_are_data_and_source_selectors_and_graph_are_preserved(self):
        graph = dict(nodes=[dict(id='input', data=dict(type='start', variables=[dict(variable='request', type='paragraph', required=True)])),
            dict(id='end', data=dict(type='end', outputs=[dict(variable='result', value_selector=['input', 'request'])]))],
            edges=[dict(source='input', target='end')])
        text = "'\n); __import__('os').system('false')\n{{#sys.user_id#}}"
        transformed, trigger = schedule.scheduled_graph(graph, dict(frequency='daily', time='09:00'), dict(request=text))
        code = transformed['nodes'][0]['data']['code']
        namespace = {}
        exec(code, namespace)
        self.assertEqual(namespace['main'](), dict(request=text))
        self.assertEqual(graph['nodes'][0]['data']['type'], 'start')
        self.assertEqual(transformed['nodes'][1]['data']['outputs'][0]['value_selector'], ['input', 'request'])
        self.assertEqual(transformed['edges'][-1]['source'], trigger)

    def test_file_inputs_triggers_and_wrong_values_are_rejected(self):
        for field in [dict(variable='file', type='file'), dict(variable='files', type='file-list')]:
            with self.assertRaises(schedule.AutomationError):
                schedule.source_fields(dict(nodes=[dict(id='start', data=dict(type='start', variables=[field]))]))
        with self.assertRaises(schedule.AutomationError):
            schedule.fixed_inputs([dict(variable='count', type='number')], dict(count=float('nan')))
        with self.assertRaises(schedule.AutomationError):
            schedule.fixed_inputs([dict(variable='kind', type='select', options=['a'], required=True)], dict(kind='b'))
        with self.assertRaises(schedule.AutomationError):
            schedule.fixed_inputs([dict(variable='text', type='paragraph', required=True)], dict(text=' '))


if __name__ == '__main__':
    unittest.main()

"""Run inside the pinned provider venv; replay SSE through its actual parser."""
import json
import unittest

from dify_plugin.interfaces.model.openai_compatible.llm import OAICompatLargeLanguageModel


class Response:
    def __init__(self, chunks):
        self.chunks = chunks

    def iter_lines(self, **kwargs):
        yield from ('data: ' + json.dumps(chunk) for chunk in self.chunks)
        yield 'data: [DONE]'


class Receiver:
    def _wrap_thinking_by_reasoning_content(self, delta, reasoning):
        return delta.get('content', ''), False

    def _create_final_llm_result_chunk(self, **kwargs):
        return kwargs


class InstalledStreamTests(unittest.TestCase):
    def test_supplied_finish_reason_survives_usage_chunk(self):
        for reason in ('stop', 'length', 'tool_calls', None, ''):
            for empty_choices in (False, True):
                with self.subTest(reason=reason, empty_choices=empty_choices):
                    usage = dict(prompt_tokens=5, completion_tokens=1, total_tokens=6)
                    chunks = [dict(choices=[dict(delta=dict(content='OK'), finish_reason=None)]),
                              dict(choices=[dict(delta={}, finish_reason=reason)]),
                              dict(usage=usage, choices=[] if empty_choices else [dict(delta={}, finish_reason=None)])]
                    results = list(OAICompatLargeLanguageModel._handle_generate_stream_response(
                        Receiver(), 'synthetic', {}, Response(chunks), []))
                    self.assertEqual(results[-1]['finish_reason'], reason)
                    self.assertEqual(results[-1]['full_content'], 'OK')
                    self.assertEqual(results[-1]['usage'], usage)

    def test_truncated_stream_has_no_finish_reason(self):
        chunks = [dict(choices=[dict(delta=dict(content='partial'), finish_reason=None)])]
        results = list(OAICompatLargeLanguageModel._handle_generate_stream_response(
            Receiver(), 'synthetic', {}, Response(chunks), []))
        self.assertIsNone(results[-1]['finish_reason'])


if __name__ == '__main__':
    unittest.main()

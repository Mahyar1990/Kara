"""A null usage chunk must not erase a real provider termination reason."""
import unittest
from unittest.mock import patch

from model_stream import repair


class ModelStreamTests(unittest.TestCase):
    def test_patch_is_pinned_idempotent_and_rejects_drift(self):
        original = 'class Handler:\n    def collect(self, chunk_json):\n        choice = chunk_json["choices"][0]\n' + repair.OLD
        with patch.object(repair, 'ORIGINAL_SHA256', repair.digest(original)):
            result = repair.patched(original)
            self.assertEqual(repair.patched(result), result)
            with self.assertRaises(RuntimeError):
                repair.patched(original + '# drift')

    def test_actual_replacement_preserves_only_supplied_values(self):
        namespace = {}
        exec('def collect(chunks):\n    finish_reason = None\n    for choice in chunks:\n'
             + ''.join(line[8:] for line in repair.NEW.splitlines(True))
             + '    return finish_reason\n', namespace)
        collect = namespace['collect']
        for sequence, expected in [(['stop', None], 'stop'), (['length', None], 'length'),
                                   (['tool_calls', None], 'tool_calls'), ([None, None], None),
                                   ([], None), (['stop', 'length', None], 'length'), (['', None], '')]:
            with self.subTest(sequence=sequence):
                self.assertEqual(collect([dict(finish_reason=value) for value in sequence]), expected)

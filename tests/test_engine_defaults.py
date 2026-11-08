import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).resolve().parents[1] / 'src/bridge/main.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class EngineDefaultsTests(unittest.TestCase):
    def test_advertised_defaults_keep_ranges_and_choices(self):
        cases = [
            ('option name NetworkDelay type spin default 120 min 0 max 10000', 'NetworkDelay', '321',
             'option name NetworkDelay type spin default 321 min 0 max 10000'),
            ('option name USI_OwnBook type check default false', 'USI_OwnBook', 'true',
             'option name USI_OwnBook type check default true'),
            ('option name BookFile type combo default no_book var no_book var user_book1.db', 'BookFile', 'user_book1.db',
             'option name BookFile type combo default user_book1.db var no_book var user_book1.db')]
        for line, key, value, expected in cases:
            self.assertEqual(bridge.advertise_defaults(line, {key: value}), expected)
            self.assertEqual(bridge.advertise_defaults(line, {}), line)

    def test_go_and_other_protocol_lines_are_unchanged(self):
        line = 'go btime 180000 wtime 600000 binc 2000 winc 2000'
        self.assertEqual(bridge.advertise_defaults(line, {'NetworkDelay': '321'}), line)

    def test_defaults_reject_protocol_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'options.json'
            for raw in [{'BookFile': 'no_book\ngo infinite'}, {'Bad\nKey': 'x'}, {'USI_Hash': []}]:
                path.write_text(json.dumps(raw))
                with self.assertRaises(ValueError):
                    bridge.load_engine_defaults(path)
            path.write_text(json.dumps({'USI_OwnBook': True, 'NetworkDelay': 0}))
            self.assertEqual(bridge.load_engine_defaults(path), {'USI_OwnBook': 'true', 'NetworkDelay': '0'})


if __name__ == '__main__':
    unittest.main()

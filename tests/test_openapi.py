import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openapi import SPEC


class OpenApiTests(unittest.TestCase):
    def test_each_operation_only_lists_relevant_responses(self):
        expected = {
            '/api/demo/login': {'200', '400', '429'},
            '/api/join': {'200', '401', '403', '409', '429'},
            '/api/admin/draw': {'200', '403', '409'},
            '/api/ticket': {'200', '401'},
            '/api/buy': {'200', '400', '401', '403', '409', '429', '503'},
            '/api/stats': {'200'},
        }

        for path, codes in expected.items():
            with self.subTest(path=path):
                method = next(iter(SPEC['paths'][path]))
                self.assertEqual(set(SPEC['paths'][path][method]['responses']), codes)
                self.assertIn(
                    'application/json',
                    SPEC['paths'][path][method]['responses']['200']['content'],
                )
                self.assertNotIn(
                    'additionalProperties',
                    SPEC['paths'][path][method]['responses']['200']['content']['application/json']['schema'],
                )


if __name__ == '__main__':
    unittest.main(verbosity=2)

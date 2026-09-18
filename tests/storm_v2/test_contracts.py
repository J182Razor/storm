import dataclasses
import importlib.util
import unittest


class FoundationTests(unittest.TestCase):
    def test_package_exists_without_legacy_import(self):
        self.assertIsNotNone(importlib.util.find_spec('storm_v2.contracts'))

    def test_invalid_brief_and_limits(self):
        from storm_v2.contracts import Brief, Config, Limits
        for value in ('../escape', '/absolute', '', 'other-business'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Brief(value, 'A valid research question?', 'AI', 'operators')
        for field in ('max_requests', 'max_tool_calls', 'max_output_tokens', 'max_polls'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                Limits(**{field: 0})
        with self.assertRaises(ValueError):
            Config(reasoning_effort='imaginary')
        with self.assertRaises(ValueError):
            Config(background=True, store=False)

    def test_risk_cannot_be_downgraded(self):
        from storm_v2.contracts import Brief
        b = Brief('KR-HEALTH-RES-001', 'What is known about sleep?', 'health', 'adults', risk_tier='general')
        self.assertEqual(b.effective_risk, 'high')

    def test_run_contract_roundtrip(self):
        from storm_v2.contracts import Brief, Config
        brief = Brief('KR-AI-RES-001', 'Which tasks should remain human-led?', 'AI', 'consultants')
        self.assertEqual(Brief(**dataclasses.asdict(brief)), brief)
        self.assertEqual(Config.from_dict(Config().to_dict()), Config())

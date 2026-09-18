import copy
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from storm_v2.client import ResearchError, ResponsesClient, clean_response, output_text
from storm_v2.contracts import Brief, Config, Limits, SECTIONS
from storm_v2.engine import ResearchEngine
from storm_v2.fixture import FixtureTransport
from storm_v2.review import review_dossier, record_human_decision
from storm_v2.schema import PLAN, decode
from storm_v2.state import RunStore


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brief = Brief('KR-AI-RES-002', 'What are the limitations?', 'AI', 'operators')
        self.config = Config(limits=Limits(max_requests=10, max_polls=2))
        self.store = RunStore.create(self.tmp.name, self.brief, self.config, 'test', synthetic=True)

    def test_refusal_is_not_completed_text(self):
        with self.assertRaises(ResearchError):
            output_text({'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'Refused'}]}]})

    def test_empty_completed_output_is_error(self):
        with self.assertRaises(ResearchError):
            output_text({'output': []})

    def test_private_reasoning_is_not_saved(self):
        value = clean_response({'id': 'resp_t', 'status': 'completed', 'reasoning': 'private',
            'error': {'message': 'sk-secret'}, 'output': [{'type': 'reasoning', 'encrypted_content': 'secret'},
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'public', 'annotations': []}]}]})
        self.assertNotIn('secret', json.dumps(value))
        self.assertNotIn('private', json.dumps(value))

    def test_unknown_provider_status_is_not_accepted(self):
        with self.assertRaises(ResearchError):
            clean_response({'id': 'resp_t', 'status': 'invented-state', 'output': []})

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            decode('{"perspectives": [], "questions": [], "questions": ["changed"]}', PLAN)

    def test_gap_followup_research_and_coverage_are_bounded(self):
        class Followups(FixtureTransport):
            def request(self, method, path, payload=None):
                result = super().request(method, path, payload)
                stage = payload['metadata']['stage']
                if stage.startswith('coverage-'):
                    part = result['output'][-1]['content'][0]
                    value = json.loads(part['text'])
                    value['followups'] = ['Find counterevidence']
                    part['text'] = json.dumps(value)
                return result
        t = Followups()
        ResearchEngine(self.store, t, offline=True).run()
        self.assertIn('research-1', t.calls)
        self.assertNotIn('research-2', t.calls)
        self.assertEqual(len(t.calls), 7)
        self.assertEqual(self.store.read('coverage.json')['followups'], ['Find counterevidence'])

    def test_injected_unregistered_tool_is_never_executed(self):
        class Injected(FixtureTransport):
            def request(self, method, path, payload=None):
                self.test_payload = payload
                result = super().request(method, path, payload)
                result['output'].append({'type': 'function_call', 'name': 'publish', 'arguments': '{"secret":true}'})
                return result
        t = Injected()
        with patch('subprocess.run', side_effect=AssertionError('no shell execution')):
            ResearchEngine(self.store, t, offline=True).run()
        self.assertNotIn('publish', (self.store.path / 'requests.json').read_text())
        self.assertNotIn('tools', t.test_payload)

    def test_semantic_failure_separate_from_mechanical_validity(self):
        ResearchEngine(self.store, FixtureTransport(), offline=True).run()
        doc = self.store.read('dossier.json')['content']
        sources = self.store.read('sources.json')['sources']
        report = review_dossier(doc, sources, 'general', {'checks': [{'claim_id': 'CLM-001', 'status': 'unsupported', 'explanation': 'Unsupported'}]})
        self.assertTrue(report['mechanical_pass'])
        self.assertFalse(report['checks_pass'])
        self.assertEqual(report['editorial_status'], 'needs_review')

    def test_modified_dossier_invalidates_human_review(self):
        ResearchEngine(self.store, FixtureTransport(), offline=True).run()
        doc = self.store.read('dossier.json')
        doc['content']['title'] = 'changed'
        self.store.write('dossier.json', doc)
        with self.assertRaisesRegex(ValueError, 'changed'):
            record_human_decision(self.store, 'Editor', 'Reviewed', approve=False)

    def test_run_artifacts_owner_private(self):
        ResearchEngine(self.store, FixtureTransport(), offline=True).run()
        for name in ('run.json', 'requests.json', 'dossier.md', 'events.jsonl'):
            self.assertEqual((self.store.path / name).stat().st_mode & 0o077, 0)

    def test_missing_sources_prevents_synthesis(self):
        class NoSources(FixtureTransport):
            def request(self, method, path, payload=None):
                result = super().request(method, path, payload)
                if payload['metadata']['stage'].startswith('research-'):
                    result['output'] = [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Unsupported', 'annotations': []}]}]
                return result
        t = NoSources()
        with self.assertRaisesRegex(ResearchError, 'citations'):
            ResearchEngine(self.store, t, offline=True).run()
        self.assertNotIn('synthesis', t.calls)
        self.assertFalse((self.store.path / 'dossier.md').exists())

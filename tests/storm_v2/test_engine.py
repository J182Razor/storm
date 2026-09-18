import dataclasses
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from storm_v2.contracts import Brief, Config, Limits, SECTIONS
from storm_v2.state import RunStore


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brief = Brief('KR-AI-RES-001', 'Which tasks need review?', 'AI', 'solo consultants')
        self.config = Config(limits=Limits(max_polls=2))
        self.store = RunStore.create(Path(self.tmp.name), self.brief, self.config, 'fixture', synthetic=True)

    def run_fixture(self):
        from storm_v2.engine import ResearchEngine
        from storm_v2.fixture import FixtureTransport
        t = FixtureTransport()
        result = ResearchEngine(self.store, t, offline=True).run()
        return result, t

    def test_complete_fixture_exports_18_sections_and_source_links(self):
        result, t = self.run_fixture()
        self.assertEqual(result['execution_status'], 'completed')
        self.assertEqual(len(t.calls), 5)
        for filename in ('brief.json', 'plan.json', 'sources.json', 'claims.json', 'dossier.json', 'dossier.md', 'review.json', 'coverage.json', 'usage.json', 'run.json', 'events.jsonl'):
            self.assertTrue((self.store.path / filename).is_file(), filename)
        doc = self.store.read('dossier.json')
        self.assertTrue(doc['synthetic'])
        self.assertEqual(doc['editorial_status'], 'needs_review')
        self.assertEqual([s['heading'] for s in doc['content']['sections']], list(SECTIONS))
        md = (self.store.path / 'dossier.md').read_text()
        self.assertIn('SYNTHETIC', md)
        self.assertIn('https://example.com/kaizen-fixture', md)
        self.assertNotIn('DO NOT SAVE', (self.store.path / 'requests.json').read_text())

    def test_resume_completed_run_makes_no_new_provider_calls(self):
        self.run_fixture()
        result, t = self.run_fixture()
        self.assertEqual(t.calls, [])
        self.assertEqual(result['execution_status'], 'completed')

    def test_resume_refuses_changed_configuration(self):
        from storm_v2.engine import ResearchEngine
        from storm_v2.fixture import FixtureTransport
        config = self.store.read('config.json')
        config['model'] = 'gpt-6-astra-2026-09-18'
        self.store.write('config.json', config)
        with self.assertRaisesRegex(ValueError, 'configuration'):
            ResearchEngine(self.store, FixtureTransport(), offline=True).run()

    def test_synthetic_cannot_be_human_approved(self):
        from storm_v2.review import record_human_decision
        self.run_fixture()
        with self.assertRaises(ValueError):
            record_human_decision(self.store, 'Editor', 'Reviewed fixture', approve=True, qualified=True)

    def test_no_live_permission_means_no_network(self):
        from storm_v2.engine import run_live
        with self.assertRaises(ValueError):
            run_live(self.store, approved=False)

    def test_cli_dry_run_has_no_key_dependency(self):
        brief = Path(self.tmp.name) / 'brief.json'
        brief.write_text(json.dumps(dataclasses.asdict(self.brief)))
        result = subprocess.run([sys.executable, '-m', 'storm_v2', 'run', '--brief', str(brief), '--dry-run'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('no API calls', result.stdout)

    def test_import_does_not_load_legacy_or_litellm(self):
        code = 'import storm_v2.engine, sys; assert "knowledge_storm" not in sys.modules; assert "litellm" not in sys.modules'
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_markdown_treats_source_text_as_text(self):
        from storm_v2.export import escape_text
        text = escape_text('<script>x</script> ![x](javascript:evil)')
        self.assertNotIn('<script>', text)
        self.assertIn('\\[', text)

    def test_legacy_adapter_never_invents_snippets(self):
        from storm_v2.adapter import information_records, perspectives_from_storm
        self.run_fixture()
        sources = self.store.read('sources.json')['sources']
        info = information_records(sources)
        self.assertEqual(info[0]['snippets'], [])
        self.assertEqual(perspectives_from_storm(['Skeptic: check limitations']), ['Skeptic: check limitations'])

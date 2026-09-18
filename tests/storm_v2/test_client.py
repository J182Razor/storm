import dataclasses
import tempfile
import unittest
from pathlib import Path

from storm_v2.contracts import Brief, Config, Limits


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def response(status='completed', text='done', response_id='resp_test'):
    return {'id': response_id, 'status': status, 'model': 'gpt-6-astra',
            'output': [{'type': 'reasoning', 'summary': ['DO NOT SAVE']},
                       {'type': 'message', 'content': [{'type': 'output_text', 'text': text, 'annotations': []}]}],
            'usage': {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15}}


class ClientTests(unittest.TestCase):
    def setUp(self):
        from storm_v2.state import RunStore
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brief = Brief('KR-AI-RES-001', 'Which tasks benefit from human review?', 'AI', 'consultants')
        self.config = Config(limits=Limits(max_polls=2, poll_interval_seconds=.001,
                             max_estimated_cost_usd=10, estimated_cost_per_request_usd=1))
        self.store = RunStore.create(Path(self.tmp.name), self.brief, self.config, 'test-run')

    def client(self, transport, config=None):
        from storm_v2.client import ResponsesClient
        return ResponsesClient(transport, self.store, config or self.config)

    def test_payload_uses_responses_and_does_not_drop_parameters(self):
        t = Transport([response()])
        self.client(t).call('research', {'question': 'q'}, search=True)
        payload = t.calls[0][2]
        self.assertEqual(payload['model'], 'gpt-6-astra')
        self.assertEqual(payload['reasoning'], {'effort': 'xhigh'})
        self.assertEqual(payload['tools'][0]['type'], 'web_search')
        self.assertEqual(payload['max_tool_calls'], 8)
        self.assertTrue(payload['background'])
        self.assertTrue(payload['store'])
        self.assertIn('web_search_call.action.sources', payload['include'])
        saved = self.store.read('requests.json')['research']['response']
        self.assertNotIn('DO NOT SAVE', str(saved))

    def test_resume_retrieves_existing_response_without_second_post(self):
        from storm_v2.client import ResearchError
        t = Transport([response('in_progress'), TimeoutError()])
        with self.assertRaises(ResearchError):
            self.client(t).call('research', {'question': 'q'}, search=True)
        t2 = Transport([response()])
        self.client(t2).call('research', {'question': 'q'}, search=True)
        self.assertEqual(t2.calls[0][0], 'GET')
        self.assertEqual(len(t2.calls), 1)

    def test_ambiguous_submission_never_retried(self):
        from storm_v2.client import ResearchError
        t = Transport([TimeoutError()])
        with self.assertRaises(ResearchError):
            self.client(t).call('plan', {'q': 'a'})
        t2 = Transport([])
        with self.assertRaisesRegex(ResearchError, 'ambiguous'):
            self.client(t2).call('plan', {'q': 'a'})
        self.assertEqual(t2.calls, [])

    def test_budget_is_reserved_before_network(self):
        from storm_v2.client import ResearchError
        config = dataclasses.replace(self.config, limits=dataclasses.replace(self.config.limits, max_estimated_cost_usd=.5))
        t = Transport([])
        with self.assertRaisesRegex(ResearchError, 'budget'):
            self.client(t, config).call('plan', {'q': 'a'})
        self.assertEqual(t.calls, [])

    def test_terminal_failures_do_not_export_as_success(self):
        from storm_v2.client import ResearchError
        for status in ('failed', 'cancelled', 'incomplete'):
            with self.subTest(status=status), self.assertRaises(ResearchError):
                self.client(Transport([response(status)])).call(status, {'q': 'a'})

    def test_changed_request_on_resume_rejected(self):
        from storm_v2.client import ResearchError
        self.client(Transport([response()])).call('plan', {'q': 'a'})
        with self.assertRaisesRegex(ResearchError, 'changed'):
            self.client(Transport([])).call('plan', {'q': 'b'})

    def test_cancel_uses_saved_id(self):
        from storm_v2.client import ResearchError
        t = Transport([response('in_progress'), TimeoutError()])
        with self.assertRaises(ResearchError):
            self.client(t).call('research', {'q': 'a'})
        t2 = Transport([response('cancelled')])
        self.client(t2).cancel('research')
        self.assertEqual(t2.calls[0][:2], ('POST', 'responses/resp_test/cancel'))

    def test_path_traversal_and_symlink_rejected(self):
        from storm_v2.state import RunStore
        with self.assertRaises(ValueError):
            self.store.write('../secret.json', {})
        target = Path(self.tmp.name) / 'link'
        target.symlink_to(self.store.path, target_is_directory=True)
        with self.assertRaises(ValueError):
            RunStore(target)

    def test_lock_rejects_concurrent_run(self):
        from storm_v2.state import RunStore
        with self.store.lock():
            with self.assertRaises(RuntimeError):
                with RunStore(self.store.path).lock():
                    self.fail('must not acquire lock')

    def test_http_rejection_keeps_only_safe_code_and_is_not_retried(self):
        from storm_v2.client import ProviderError, ResearchError
        t = Transport([ProviderError(429)])
        with self.assertRaisesRegex(ResearchError, '429'):
            self.client(t).call('rate-limited', {'q': 'a'})
        entry = self.store.read('requests.json')['rate-limited']
        self.assertEqual(entry['error_code'], 'provider_http_429')
        with self.assertRaisesRegex(ResearchError, 'rejected'):
            self.client(Transport([])).call('rate-limited', {'q': 'a'})

    def test_live_transport_requires_explicit_paid_authorization(self):
        from storm_v2.client import OpenAITransport
        t = OpenAITransport(self.config.limits, api_key='unit-test-placeholder')
        with self.assertRaises(ValueError):
            self.client(t).call('plan', {'q': 'a'})

    def test_polling_cap_preserves_response_id(self):
        from storm_v2.client import ResearchError
        t = Transport([response('queued'), response('in_progress'), response('in_progress')])
        with self.assertRaisesRegex(ResearchError, 'Polling budget'):
            self.client(t).call('research', {'q': 'a'})
        self.assertEqual(self.store.read('requests.json')['research']['response_id'], 'resp_test')
        self.assertEqual(len(t.calls), 3)

    def test_input_limit_rejects_before_submission(self):
        from storm_v2.client import ResearchError
        config = dataclasses.replace(self.config, limits=dataclasses.replace(self.config.limits, max_input_chars=2))
        t = Transport([])
        with self.assertRaisesRegex(ResearchError, 'Input exceeds'):
            self.client(t, config).call('plan', {'question': 'too much'})
        self.assertEqual(t.calls, [])

    def test_request_count_is_global_across_stages(self):
        from storm_v2.client import ResearchError
        config = dataclasses.replace(self.config, limits=dataclasses.replace(self.config.limits, max_requests=1))
        t = Transport([response()])
        c = self.client(t, config)
        c.call('first', {'q': 'a'})
        with self.assertRaisesRegex(ResearchError, 'budget'):
            c.call('second', {'q': 'a'})
        self.assertEqual(len(t.calls), 1)

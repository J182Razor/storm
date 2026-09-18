import unittest


class EvidenceTests(unittest.TestCase):
    def test_url_normalization_and_safety(self):
        from storm_v2.evidence import normalize_url
        self.assertEqual(normalize_url('https://EXAMPLE.com/a?utm_source=x&id=4#top'), 'https://example.com/a?id=4')
        for url in ('javascript:alert(1)', 'http://localhost/a', 'https://127.0.0.1/', 'https://a.test/?api_key=secret', 'file:///etc/passwd'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_url(url)

    def test_citation_registry_preserves_access_limits_and_offsets(self):
        from storm_v2.evidence import Registry
        r = Registry()
        data = {'id': 'resp_a', 'output': [
            {'type': 'web_search_call', 'id': 'ws_a', 'status': 'completed', 'action': {'type': 'search', 'sources': [{'url': 'https://example.com/study?utm_source=x'}]}},
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Reported claim [1]', 'annotations': [
                {'type': 'url_citation', 'url': 'https://example.com/study', 'title': 'Study', 'start_index': 15, 'end_index': 18}]}]}]}
        r.ingest(data)
        self.assertEqual(len(r.sources), 1)
        source = next(iter(r.sources.values()))
        self.assertIn('provider_cited', source['access_states'])
        self.assertNotIn('full_text_inspected', source['access_states'])
        self.assertIsNone(source['published_at'])
        self.assertEqual(r.citations[0]['start_index'], 15)
        self.assertEqual(source['excerpts'], [])

    def test_invalid_offsets_are_flagged(self):
        from storm_v2.evidence import Registry
        r = Registry()
        r.ingest({'id': 'resp_a', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'short', 'annotations': [
            {'type': 'url_citation', 'url': 'https://example.com/a', 'title': 'A', 'start_index': 0, 'end_index': 99}]}]}]})
        self.assertTrue(r.issues)

    def test_structured_response_strict_validation(self):
        from storm_v2.schema import PLAN, validate
        validate({'perspectives': ['critical reader'], 'questions': ['What contradicts the claim?']}, PLAN)
        for data in ({'perspectives': [], 'questions': 'not-list'}, {'perspectives': [], 'questions': [], 'publish': True}):
            with self.assertRaises(ValueError):
                validate(data, PLAN)

    def test_missing_citations_block_mechanical_pass(self):
        from storm_v2.review import review_dossier
        report = review_dossier({'claims': [{'id': 'CLM-001', 'text': 'Claim', 'source_ids': ['SRC-missing'], 'evidence_strength': 'HIGH', 'qualification': ''}], 'sections': []}, {}, 'general')
        self.assertFalse(report['mechanical_pass'])
        self.assertEqual(report['editorial_status'], 'needs_review')

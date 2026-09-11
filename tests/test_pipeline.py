import asyncio
import json
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ['GROQ_API_KEY'] = 'test-only'
os.environ['GOOGLE_PLACES_API_KEY'] = 'test-only'
os.environ['DATABASE_URL'] = 'sqlite://'

import httpx
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from agents import crawler, extractor
from agents.analytics import run_analytics
from api import routes
from db.database import Base, get_db
from db.models import Job, JobError
from main import app

class CrawlerTests(unittest.TestCase):
    def test_google_denial_is_not_empty_success(self):
        response = Mock()
        response.json.return_value = {'status': 'REQUEST_DENIED', 'error_message': 'private details'}
        with patch.object(crawler.requests, 'get', return_value=response) as get:
            with self.assertRaisesRegex(crawler.PlacesError, 'REQUEST_DENIED') as error:
                crawler.crawl('Hyderabad', 'cafes', 'Banjara Hills')
            self.assertNotIn('private details', str(error.exception))
            self.assertEqual(get.call_args.kwargs['timeout'], (5, 20))

    def test_true_zero_results_is_empty(self):
        response = Mock()
        response.json.return_value = {'status': 'ZERO_RESULTS', 'results': []}
        with patch.object(crawler.requests, 'get', return_value=response):
            self.assertEqual(crawler.crawl('City', 'cafes', 'Locality'), [])
        analytics = run_analytics([])
        self.assertEqual(analytics['competition_density'], 'unknown')
        self.assertIsNone(analytics['underserved_price_band'])

    def test_network_failure_does_not_expose_key(self):
        with patch.object(crawler.requests, 'get', side_effect=requests.Timeout('url?key=secret')):
            with self.assertRaises(crawler.PlacesError) as error:
                crawler.crawl('City', 'cafes', 'Locality')
            self.assertNotIn('secret', str(error.exception))

class ExtractorTests(unittest.TestCase):
    def test_structured_response_and_nullable_fields(self):
        listing = {'name': 'Cafe', 'rating': None, 'review_count': None, 'price_range': 'budget',
                   'phone': None, 'address': None, 'top_complaints': [], 'tags': ['cafe']}
        response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps(listing)))])
        with patch.object(extractor.client.chat.completions, 'create', return_value=response) as create:
            self.assertEqual(extractor.extract_business(listing), listing)
            options = create.call_args.kwargs
            self.assertEqual(options['model'], 'openai/gpt-oss-120b')
            schema = options['response_format']['json_schema']
            self.assertTrue(schema['strict'])
            self.assertIn('null', schema['schema']['properties']['rating']['type'])

    def test_truncation_uses_original_listing(self):
        response = SimpleNamespace(choices=[SimpleNamespace(finish_reason='length', message=SimpleNamespace(content='{"name":'))])
        with patch.object(extractor.client.chat.completions, 'create', return_value=response):
            result = extractor.extract_business({'name': 'Original Cafe', 'rating': 4.1, 'reviews': ['Slow service']})
            self.assertEqual(result['name'], 'Original Cafe')
            self.assertEqual(result['top_complaints'], ['Slow service'])

class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + self.temp.name.replace('\\', '/') + '/test.db', connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)
        self.session_patch = patch.object(routes, 'SessionLocal', self.session)
        self.session_patch.start()
        def db_override():
            with self.session() as db:
                yield db
        app.dependency_overrides[get_db] = db_override
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        self.session_patch.stop()
        self.engine.dispose()
        self.temp.cleanup()

    async def test_denial_persists_actionable_failure(self):
        with patch.object(routes, 'crawl', side_effect=crawler.PlacesError('Google Places: REQUEST_DENIED. Check billing.')):
            response = await self.client.post('/analyze', json={'city':'City','category':'cafes','locality':'Area'})
        job_id = response.json()['job_id']
        result = (await self.client.get('/status/' + job_id)).json()
        self.assertEqual(result['status'], 'failed')
        self.assertIn('REQUEST_DENIED', result['error'])

    async def test_status_responds_while_crawler_is_busy(self):
        started, release = threading.Event(), threading.Event()
        def blocking_crawl(*args):
            started.set()
            release.wait(3)
            return []
        with patch.object(routes, 'crawl', side_effect=blocking_crawl):
            task = asyncio.create_task(self.client.post('/analyze', json={'city':'City','category':'cafes','locality':'Area'}))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                with self.session() as db:
                    job_id = db.query(Job).first().id
                response = await asyncio.wait_for(self.client.get('/status/' + job_id), timeout=1)
                self.assertEqual(response.json()['status'], 'processing')
            finally:
                release.set()
                await task
        report = (await self.client.get('/report/' + job_id)).json()
        self.assertEqual(report['businesses'], [])
        self.assertEqual(report['analytics']['competition_density'], 'unknown')

if __name__ == '__main__':
    unittest.main()

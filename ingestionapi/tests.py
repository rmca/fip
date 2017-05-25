import tempfile
import os

import ingestion_api
import list_api
import tasks

import circuitbreaker
import kombu
import pep8

import glob
import json
import unittest
from unittest.mock import patch


class BaseTests(unittest.TestCase):
    """
    Common test code.
    """

    def setUp(self):
        self.patch_redis = patch('ingestion_api.get_redis_client')
        self.mock_redis = self.patch_redis.start()
        self.patch_celery = patch('ingestion_api.enqueue_task')
        self.mock_celery = self.patch_celery.start()
        self.client = ingestion_api.app.test_client()

    def tearDown(self):
        self.patch_redis.stop()
        self.patch_celery.stop()

    def assertJSON(self, response):
        try:
            content = json.loads(response.data)
        except json.JSONDecodeError:
            raise AssertionError
        return content

    def assertHTTPErrorWithJSONResponse(self, response, http_status,
                                        error_code=None):
        self.assertEqual(response.status_code, http_status)
        content = self.assertJSON(response)
        # If our http status is in the client or server error range,
        # check the error code.
        if 400 <= http_status < 600:
            self.assertEqual(content['code'], error_code)

    def get_valid_data(self):
        return json.dumps({})

    def get_invalid_data(self):
        return '{'


class CreateDummyFailureTests(BaseTests):

    def test_post_missing(self):
        actual = self.client.post('/dummy')
        # MISSING_FIELD
        content = self.assertHTTPErrorWithJSONResponse(actual, 400, 1000)

    def test_post_invalid_json(self):
        actual = self.client.post('/dummy', data={'data': '{'})
        # INVALID_JSON
        self.assertHTTPErrorWithJSONResponse(actual, 400, 1001)

    def test_post_invalid_length(self):
        return
        actual = self.client.post('/dummy', data={'data': 'a' * 5000})
        # MAX_DATA_SIZE
        self.assertHTTPErrorWithJSONResponse(actual, 400, 1002)


class CreateDummySuccessTests(BaseTests):

    def test_post_success(self):
        dummy_data = self.get_valid_data()
        actual = self.client.post('/dummy', data={'data': dummy_data})
        self.assertHTTPErrorWithJSONResponse(actual, 202)


class CreateDummyServerErrors(BaseTests):

    def test_post_circuit_breaker(self):
        dummy_data = self.get_valid_data()
        self.mock_celery.side_effect = circuitbreaker.CircuitBreakerError(
            'blah')
        actual = self.client.post('/dummy', data={'data': dummy_data})
        # SERVICE_UNAVAILABLE
        self.assertHTTPErrorWithJSONResponse(actual, 503, 2000)

    def test_broker_exception(self):
        dummy_data = self.get_valid_data()
        self.mock_celery.side_effect = kombu.exceptions.KombuError
        actual = self.client.post('/dummy', data={'data': dummy_data})
        self.assertHTTPErrorWithJSONResponse(actual, 503, 2000)


class BaseListTests(unittest.TestCase):

    def setUp(self):
        list_api.app.config['TESTING'] = True
        with list_api.app.app_context():
            list_api.db.drop_all()
            list_api.db.create_all()
        self.client = list_api.app.test_client()

    def make_record(self, timestamp, message_id, record):
        rec = list_api.Records(timestamp=timestamp,
                               message_id=message_id,
                               record=record)
        with list_api.app.app_context():
            list_api.db.session.add(rec)
            list_api.db.session.commit()
        return {'timestamp': timestamp, 'message_id': message_id,
                'data': record}


class ListTestsEmpty(BaseListTests):

    def test_list_empty_db(self):
        recs = self.client.get('/records')
        self.assertEqual(recs.status_code, 200)
        actual = json.loads(recs.data)
        self.assertEqual(actual['count'], 0)
        self.assertEqual(actual['results'], [])
        self.assertEqual(actual['next'], None)

    def test_create_single_record_and_list(self):
        r = self.make_record(timestamp=0, message_id='test', record='foo')
        recs = self.client.get('/records')
        self.assertEqual(recs.status_code, 200)
        actual = json.loads(recs.data)
        self.assertEqual(actual['count'], 1)
        self.assertEqual(actual['results'], [r])

    def test_create_multiple_record_and_list_sequential(self):
        created = set()
        seen = set()
        for i in range(20):
            r = self.make_record(timestamp=i,
                                 message_id='test %d' % i,
                                 record='foo')
            created.add(r['message_id'])
        recs = self.client.get('/records')
        self.assertEqual(recs.status_code, 200)
        actual = json.loads(recs.data)
        self.assertEqual(actual['count'], 10)
        for r in actual['results']:
            seen.add(r['message_id'])

        recs2 = self.client.get('/records?next=%s' % actual['next'])
        self.assertEqual(recs2.status_code, 200)
        actual2 = json.loads(recs2.data)
        self.assertEqual(actual2['count'], 10)
        for r in actual2['results']:
            seen.add(r['message_id'])

        self.assertEqual(seen, created)

    def test_create_multiple_record_and_list_timestamp_static(self):
        created = set()
        seen = set()
        for i in range(20):
            r = self.make_record(timestamp=0,
                                 message_id='test %d' % i,
                                 record='foo')
            created.add(r['message_id'])
        recs = self.client.get('/records')
        self.assertEqual(recs.status_code, 200)
        actual = json.loads(recs.data)
        self.assertEqual(actual['count'], 10)

        for r in actual['results']:
            seen.add(r['message_id'])

        recs2 = self.client.get('/records?next=%s' % actual['next'])
        self.assertEqual(recs2.status_code, 200)
        actual2 = json.loads(recs2.data)
        self.assertEqual(actual2['count'], 10)
        for r in actual2['results']:
            seen.add(r['message_id'])
        self.assertEqual(seen, created)


def time_func():
    return 1


def uuid_func():
    return 'a'


class TasksTests(BaseListTests):

    def test_add_success(self):
        with list_api.app.app_context():
            self.assertIsNone(tasks.add('foo'))
            res = tasks.db.session.query(tasks.Records.record)
            results = res.all()
            for r in results:
                self.assertEqual(r.record, 'foo')
            self.assertEqual(len(results), 1)

    def test_add_dupe_only_stores_single_task(self):
        with list_api.app.app_context():
            self.assertIsNone(tasks.add('foo', timefunc=time_func,
                              uuidfunc=uuid_func))
            self.assertIsNone(tasks.add('foo', timefunc=time_func,
                              uuidfunc=uuid_func))
            res = tasks.db.session.query(tasks.Records.record)
            results = res.all()
            for r in results:
                self.assertEqual(r.record, 'foo')
            self.assertEqual(len(results), 1)


class TestCodeFormat(unittest.TestCase):

    def test_pep8_conformance(self):
        """Test that we conform to PEP8."""
        pep8style = pep8.StyleGuide(quiet=True)
        result = pep8style.check_files(glob.glob('*.py'))
        self.assertEqual(result.total_errors, 0,
                         "Found code style errors (and warnings).")

import app

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
        self.patch_redis = patch('app.get_redis_client')
        self.mock_redis = self.patch_redis.start()
        self.patch_celery = patch('app.enqueue_task')
        self.mock_celery = self.patch_celery.start()
        self.client = app.app.test_client()

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


class TestCodeFormat(unittest.TestCase):

    def test_pep8_conformance(self):
        """Test that we conform to PEP8."""
        pep8style = pep8.StyleGuide(quiet=True)
        result = pep8style.check_files(glob.glob('*.py'))
        self.assertEqual(result.total_errors, 0,
                         "Found code style errors (and warnings).")

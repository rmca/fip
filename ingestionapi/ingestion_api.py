from flask import Flask, request, make_response
from flask_autodoc import Autodoc
import kombu
import redis

import circuitbreaker
import structlog

from circuitbreaker import circuit, CircuitBreakerMonitor

from tasks import add

import json
import os
import time

app = Flask(__name__)
auto = Autodoc(app)

logger = structlog.get_logger()

# Config


class DefaultSettings(object):

    REDIS_TOPIC = os.environ.get('REDIS_TOPIC') or "blah"
    REDIS_HOST = os.environ.get('REDIS_HOST') or 'redis'
    REDIS_PORT = os.environ.get('REDIS_PORT') or 6379
    MAX_DUMMY_MSG_LENGTH = os.environ.get('MAX_DUMMY_MSG_LENGTH') or 1000

app.config.from_object('ingestion_api.DefaultSettings')

redis_clients = []


def make_redis_client():
    """
    """
    r = redis.StrictRedis(host=app.config['REDIS_HOST'],
                          port=app.config['REDIS_PORT'])
    p = r.pubsub()
    p.subscribe(app.config['REDIS_TOPIC'])
    return r


def get_redis_client():
    if len(redis_clients) == 0:
        redis_clients.append(make_redis_client())
    return redis_clients[0]


@circuit(failure_threshold=1, name='redis-task-queue')
def enqueue_task(txt):
    add.delay(txt)


# Client Errors
MISSING_FIELD = 1000
INVALID_JSON = 1001
MAX_DATA_SIZE = 1002

# Server Errors
SERVICE_UNAVAILABLE = 2000


def make_error_response(msg, code, status):
    return make_response(json.dumps(
        {'error': msg,
         'code': code}), status,
        {'Content-Type': 'application/json'})


@app.route('/dummy', methods=['POST'])
@auto.doc()
def create_dummy():
    """
    Create a dummy document. On success this will return 202 to
    indicate that the document has been accepted for processing.

    This endpoint takes a POST data field called "data", which
    is a JSON encoded document. Example request:

    create_api = 'http://127.0.0.1:6000/dummy'
    requests.post(create_api, data={'data': json.dumps({'testdatum': 'a'})})
    """
    _t_start = time.time()
    try:
        data = json.loads(request.form['data'])
        enqueue_task(request.form['data'])
    except KeyError:
        return make_error_response(
                "Missing data field", MISSING_FIELD, 400
        )
    except ValueError:
        return make_error_response(
                "Invalid JSON", INVALID_JSON, 400
        )
    except (circuitbreaker.CircuitBreakerError, kombu.exceptions.KombuError):
        return make_error_response(
                "Service Unavailable", SERVICE_UNAVAILABLE, 503
        )

    try:
        get_redis_client().publish(app.config['REDIS_TOPIC'],
                                   request.form['data'])
    except redis.exceptions.RedisError:
        # TODO: output a log here.
        # We don't care about pubsub exceptions,
        # those messages are best-effort anyway.
        pass

    logger.info("create_dummy", duration=time.time()-_t_start)
    return make_response(
            json.dumps({'success': True}), 202,
            {'Content-Type': 'application/json'})


@app.route('/documentation', methods=['GET'])
@auto.doc()
def documentation():
    """This documentation ;)"""
    return auto.html()


@app.route('/health', methods=['GET'])
@auto.doc()
def health():
    """Return some health information. For now just open circuit breakers"""
    return json.dumps(
        {x.name: 'open' for x in CircuitBreakerMonitor.get_open()}
    )

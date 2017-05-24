from flask import Flask, request, make_response
from flask_autodoc import Autodoc
import kombu
import redis

import circuitbreaker
from circuitbreaker import circuit, CircuitBreakerMonitor

from tasks import add

import json
import os

app = Flask(__name__)
auto = Autodoc(app)


# Config

class DefaultSettings(object):

    REDIS_TOPIC = os.environ.get('REDIS_TOPIC') or "blah"
    REDIS_HOST = os.environ.get('REDIS_HOST') or 'redis'
    REDIS_PORT = os.environ.get('REDIS_PORT') or 6379
    MAX_DUMMY_MSG_LENGTH = os.environ.get('MAX_DUMMY_MSG_LENGTH') or 1000

app.config.from_object('app.DefaultSettings')

redis_clients = []


def make_redis_client():
    """
    """
    r = redis.StrictRedis(host=app.config['REDIS_HOST'],
                          port=app.config['REDIS_PORT'])
    p = r.pubsub()
    p.subscribe(REDIS_TOPIC)
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


@app.route('/dummy', methods=['POST'])
@auto.doc()
def create_dummy():
    """Create a dummy document. On success this will return 202 to
    indicate that the document has been accepted for processing."""
    try:
        data = json.loads(request.form['data'])
        enqueue_task(request.form['data'])
    except KeyError:
        return make_response(json.dumps(
            {'error': "Missing data field",
             'code': MISSING_FIELD}), 400,
            {'Content-Type': 'application/json'})
    except ValueError:
        return make_response(json.dumps(
            {'error': "Invalid JSON", 'code': INVALID_JSON}), 400,
            {'Content-Type': 'application/json'})
    except (circuitbreaker.CircuitBreakerError, kombu.exceptions.KombuError):
        return make_response(
            json.dumps(
                {'error': "Service Unavailable", 'code': SERVICE_UNAVAILABLE}
            ), 503,
            {'Content-Type': 'application/json'})

    try:
        get_redis_client().publish(REDIS_TOPIC, request.form['data'])
    except redis.exceptions.RedisError:
        # TODO: output a log here.
        # We don't care about pubsub exceptions,
        # those messages are best-effort anyway.
        pass

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

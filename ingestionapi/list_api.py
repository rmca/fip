import json
import os
import time

from flask import request, make_response
from db import app, db, Records

import structlog


logger = structlog.get_logger()


COUNT_VALUE = int(os.environ.get('COUNT_VALUE', 10))


@app.route('/records', methods=['GET'])
def list_dummy_records():
    """
    List dummy records by paging through them.

    The return value is a dictionary containing:
    - results: A list of result dictionaries
    - next: A token to use to retrieve the next page
            via the "next" URL parameter
    - count: The number of results

    A result dictionary consists of:
    - timestamp: Corresponds to (roughly) when the record
                 was written to the DB
    - message_id: A UUID to uniquely identify the message
    - data: The JSON encoded message.
    """
    _t_start = time.time()
    timestamp = None
    message_id = None
    try:
        next_token = request.args.get('next')
        if next_token is not None:
            timestamp, message_id = request.args.get('next').split('_')
            timestamp = int(timestamp)
    except ValueError:
        return make_response(json.dumps(
            {"error": "Invalid next token", "code": 1100}), 400,
            {"Content-Type": 'application/json'})

    _t_start2 = time.time()
    if timestamp is not None and message_id is not None:
        records = db.session.query(Records).from_statement(
            db.text(
                "SELECT * FROM records WHERE timestamp >= :timestamp and "
                "message_id >= :message_id "
                "ORDER BY timestamp, message_id LIMIT :count"
            ).params(timestamp=timestamp, message_id=message_id,
                     count=COUNT_VALUE+1))
    else:
        records = db.session.query(Records).from_statement(
            db.text(
                "SELECT * FROM records ORDER BY "
                "timestamp, message_id LIMIT :count"
                ).params(count=COUNT_VALUE+1))

    result_set = [
            {'timestamp': r.timestamp, 'message_id': r.message_id,
             'data': r.record}
            for r in records
    ]
    logger.info("records.sql.duration", duration=time.time()-_t_start2)

    try:
        next_token = "_".join([str(result_set[-1]['timestamp']),
                               result_set[-1]['message_id']])
    except (IndexError, KeyError):
        next_token = None

    # Drop the last result from here since that's only used to compute the next
    # token.
    result_set = result_set[0:COUNT_VALUE]
    count = len(result_set)
    results = {
        'results': result_set, 'count': count, 'next': next_token
    }
    # For want of a better way, output a metric.
    logger.info("records.duration", duration=time.time()-_t_start, count=1)
    return make_response(
            json.dumps(results), 200,
            {'Content-Type': 'application/json'})

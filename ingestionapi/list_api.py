import json
import os

from flask import request, make_response
from db import app, db, Records


COUNT_VALUE = int(os.environ.get('COUNT_VALUE', 10))


@app.route('/records', methods=['GET'])
def list_dummy_records():
    """
    List dummy records by paging through them.
    TODO: better documentation.
    """
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
    return make_response(
            json.dumps(results), 200,
            {'Content-Type': 'application/json'})

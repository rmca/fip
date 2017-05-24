from celery import Celery
from db import Records, db

import json
import uuid
import os
import time


broker = os.environ.get('TASK_BROKER', 'redis://redis:6379/0')
app = Celery('tasks', broker=broker)


@app.task(ignore_result=True, task_acks_late=True)
def add(txt):
    r = Records(
            timestamp=int(time.time()),
            message_id=uuid.uuid4().hex,
            record=txt
    )
    db.session.add(r)
    db.session.commit()
